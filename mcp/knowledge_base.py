"""
RAG 知识库 —— 基于 ChromaDB 的真实检索实现。

功能：
  1. 文档导入：使用版本化的显式向量后将文本切片存入 ChromaDB
  2. 语义检索：根据 query 从知识库中检索最相关的文档片段
  3. 与 MCP 工具框架集成：作为 knowledge_search 工具的真实 handler

ChromaDB 在这里的角色：
  - memory/ 中用于存储对话记忆（情景记忆 + 用户画像）
  - 这里用于存储知识库文档（RAG 检索）
  两者是不同的 collection，互不干扰。
"""
import asyncio
import hashlib
import logging
import os
import math
from typing import Any, Dict, List, Optional

import chromadb
from .knowledge_embeddings import EMBEDDING_VERSION, embed_document, embed_query
from .rag_contract import KnowledgeDocument, build_hit

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    基于 ChromaDB 的 RAG 知识库。

    HTTP thin client 不提供默认 embedding function。演示知识库使用明确的
    字符 n-gram 向量基线，导入与查询使用同一版本；Chroma 只负责向量存取。
    """

    COLLECTION_NAME = "cartcare_demo_knowledge_chargram_v1"
    DEFAULT_MIN_SCORE = 0.35  # Heuristic for 1 - Chroma distance; not a calibrated probability.

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_path: str = "./data/chroma",
        min_score: float | None = None,
        collection_name: str | None = None,
        seed_defaults: bool = True,
    ):
        self.min_score = float(min_score if min_score is not None else os.getenv(
            "CARTCARE_RAG_MIN_SCORE", str(self.DEFAULT_MIN_SCORE)))
        if not math.isfinite(self.min_score) or not 0.0 <= self.min_score <= 1.0:
            raise ValueError("CARTCARE_RAG_MIN_SCORE must be between 0 and 1")
        # 通过 HTTP 连接独立 ChromaDB 服务；chroma_path 仅为兼容旧调用方保留，不再使用。
        try:
            # HttpClient 默认也会初始化 ChromaDB telemetry；显式关闭避免 posthog 兼容性错误日志。
            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            self._client.heartbeat()
            logger.info(f"知识库 ChromaDB 已连接: {chroma_host}:{chroma_port}")
        except Exception as exc:
            message = f"无法连接 ChromaDB Server: {chroma_host}:{chroma_port}"
            logger.error(message)
            raise ConnectionError(message) from exc

        self._collection_name = collection_name or self.COLLECTION_NAME
        self._collection = self._open_collection()

        # 如果知识库为空，导入默认文档
        if seed_defaults and self._collection.count() == 0:
            self._load_default_docs()

    def _open_collection(self):
        collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"description": "CartCare demo RAG knowledge", "dataset_kind": "demo",
                      "embedding_version": EMBEDDING_VERSION, "hnsw:space": "cosine"},
        )
        actual = collection.metadata or {}
        if actual.get("embedding_version") != EMBEDDING_VERSION or actual.get("hnsw:space") != "cosine":
            raise ValueError(f"Chroma collection {self._collection_name} has an incompatible embedding configuration")
        return collection

    # ── 文档管理 ──────────────────────────────────────────────────────────────

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        批量导入文档到知识库。

        documents require title, content and source; policy documents also
        require policy_version and timezone-aware effective_at.
        长文档会自动切片（每片 500 字）。
        """
        validated = [KnowledgeDocument.model_validate(doc) for doc in documents]
        ids, docs, metas = [], [], []

        for doc in validated:
            chunks = self._chunk_text(doc.content, chunk_size=500)

            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(
                    f"{doc.document_id}\0{doc.policy_version}\0{i}\0{chunk}".encode("utf-8")
                ).hexdigest()
                ids.append(chunk_id)
                docs.append(chunk)
                meta = {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "source": doc.source,
                    "doc_type": doc.doc_type.value,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                if doc.policy_version is not None:
                    meta["policy_version"] = doc.policy_version
                if doc.effective_at is not None:
                    meta["effective_at"] = doc.effective_at.isoformat()
                metas.append(meta)

        if ids:
            embeddings = [embed_document(meta["title"], content)
                          for meta, content in zip(metas, docs)]
            self._collection.upsert(ids=ids, documents=docs, metadatas=metas,
                                    embeddings=embeddings)
            logger.info(f"知识库导入 {len(ids)} 个文档片段")

        return len(ids)

    async def add_documents_async(self, documents: List[Dict[str, Any]]) -> int:
        """异步导入文档；ChromaDB 客户端为同步实现，因此放入线程池执行。"""
        return await asyncio.to_thread(self.add_documents, documents)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义检索：根据 query 返回最相关的文档片段。

        score 是 1 - Chroma distance 的基线启发式值，不是校准概率。
        """
        if not query.strip() or top_k < 1:
            raise ValueError("query 不能为空且 top_k 必须大于 0")
        results = self._collection.query(
            query_embeddings=[embed_query(query)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        items = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append(build_hit(doc, meta, dist, min_score=self.min_score).model_dump(mode="json"))

        return items

    async def search_async(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """异步检索；ChromaDB 客户端为同步实现，因此放入线程池执行。"""
        return await asyncio.to_thread(self.search, query, top_k)

    @property
    def doc_count(self) -> int:
        return self._collection.count()

    def rebuild_demo_collection(self) -> int:
        """Explicitly replace only the versioned demo seed; refuse unknown sources."""
        if self._collection_name != self.COLLECTION_NAME:
            raise ValueError("demo rebuild is limited to the default demo collection")
        if (self._collection.metadata or {}).get("dataset_kind") != "demo":
            raise ValueError("collection is not marked as demo data")
        stored = self._collection.get(include=["metadatas"])
        if any(not isinstance(meta, dict) or
               not str(meta.get("source", "")).startswith("demo:cartcare-default/")
               for meta in stored.get("metadatas", [])):
            raise ValueError("collection contains records without known demo provenance; reset refused")
        self._client.delete_collection(self._collection_name)
        self._collection = self._open_collection()
        self._load_default_docs()
        return self.doc_count

    async def doc_count_async(self) -> int:
        """异步获取文档片段数量。"""
        return await asyncio.to_thread(self._collection.count)

    # ── MCP 工具 handler ─────────────────────────────────────────────────────

    async def search_handler(self, params: Dict[str, Any], context: Any) -> List[Dict]:
        """
        作为 MCP 工具的 handler 注册。

        MCPToolManager.register(Tool(
            name="knowledge_search",
            handler=kb.search_handler,
            ...
        ))
        """
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        return await self.search_async(query, top_k=top_k)

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """将长文本按 chunk_size 切片，保留语义完整性（按句号/换行切分）。"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        current = ""
        # 按句子切分
        sentences = text.replace("\n", "。").split("。")
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) + 1 > chunk_size:
                if current:
                    chunks.append(current)
                current = sent
            else:
                current = f"{current}。{sent}" if current else sent

        if current:
            chunks.append(current)

        return chunks

    def _load_default_docs(self) -> None:
        """导入默认知识库文档（客服场景常见问题）。"""
        default_docs = [
            {
                "title": "退款政策",
                "source": "demo:cartcare-default/refund-policy",
                "doc_type": "policy",
                "policy_version": "refund-cancel-v1",
                "effective_at": "2026-09-30T00:00:00+00:00",
                "content": (
                    "CartCare 模拟客服政策说明，仅用于演示。"
                    "订单创建后 7 天内、订单状态符合要求时可以请求退款。"
                    "退款金额不能超过订单总额；超过 500 元需人工审批。"
                    "退款请求是否可执行由实时订单事实和 PolicyEngine 决定。"
                    "此文档不代表真实商城承诺或支付渠道处理时效。"
                ),
            },
            {
                "title": "订单查询",
                "source": "demo:cartcare-default/order-guide",
                "doc_type": "guide",
                "content": (
                    "订单查询指南。"
                    "用户可以通过订单号查询订单状态。"
                    "订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。"
                    "如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。"
                    "物流信息通常在发货后 24 小时内更新。"
                    "如果订单显示异常，请提供订单号联系客服处理。"
                ),
            },
            {
                "title": "账户安全",
                "source": "demo:cartcare-default/account-guide",
                "doc_type": "guide",
                "content": (
                    "账户安全说明。"
                    "建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。"
                    "如果忘记密码，可以通过绑定的手机号或邮箱重置。"
                    "发现账户异常登录时，系统会自动锁定账户并发送通知。"
                    "用户可以在安全设置中开启两步验证，提高账户安全性。"
                    "不要将密码分享给他人，客服人员不会索要用户密码。"
                ),
            },
            {
                "title": "技术故障排查",
                "source": "demo:cartcare-default/technical-guide",
                "doc_type": "guide",
                "content": (
                    "常见技术问题排查。"
                    "应用崩溃：请尝试清除缓存后重启应用，如果问题持续请更新到最新版本。"
                    "登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。"
                    "页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。"
                    "支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。"
                    "500 服务器错误：这是服务端问题，请稍后重试，如果持续出现请联系技术支持。"
                ),
            },
            {
                "title": "会员与积分",
                "source": "demo:cartcare-default/membership-faq",
                "doc_type": "faq",
                "content": (
                    "会员积分规则。"
                    "每消费 1 元累积 1 积分。"
                    "积分可以在下次购物时抵扣，100 积分 = 1 元。"
                    "会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。"
                    "银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。"
                    "积分有效期为 1 年，过期自动清零。"
                    "生日当月消费可获得双倍积分。"
                ),
            },
            {
                "title": "配送说明",
                "source": "demo:cartcare-default/shipping-guide",
                "doc_type": "guide",
                "content": (
                    "配送服务说明。"
                    "标准配送：3-5 个工作日送达，免运费（订单满 99 元）。"
                    "加急配送：1-2 个工作日送达，运费 15 元。"
                    "同城配送：当日达或次日达，运费 10 元。"
                    "偏远地区可能需要额外 2-3 天。"
                    "配送时间为每天 9:00-18:00，节假日可能延迟。"
                    "如果需要修改收货地址，请在发货前联系客服。"
                ),
            },
        ]
        self.add_documents(default_docs)
        logger.info(f"已导入默认知识库: {len(default_docs)} 篇文档")
