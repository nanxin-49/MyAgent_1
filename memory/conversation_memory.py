"""Session context in Redis; filtered, expiring support memory in Chroma HTTP."""
import hashlib
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import chromadb
import redis.asyncio as redis
from mcp.knowledge_embeddings import EMBEDDING_VERSION, embed_query
from memory.policy import (compressed_summary, episodic_topics, explicit_preferences,
                           fresh_metadata, validated_preferences)

logger = logging.getLogger(__name__)


class MsgRole(Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"


@dataclass
class Message:
    role:       MsgRole
    content:    str
    timestamp:  datetime = field(default_factory=datetime.now)
    metadata:   Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryContext:
    """传给 Agent 的完整上下文。"""
    recent_messages:  List[Message]   # 工作记忆：最近对话
    relevant_history: List[str]       # 情景记忆：语义相关的历史片段
    user_profile:     Dict[str, Any]  # 用户画像：偏好、常用实体
    summary:          str             # 当前会话摘要（压缩后）

    @staticmethod
    def _clean(text: str) -> str:
        """移除 Unicode 代理字符，防止编码错误。"""
        return text.encode("utf-8", errors="ignore").decode("utf-8")

    def to_prompt_text(self) -> str:
        """将记忆上下文格式化为 LLM 可用的文本。"""
        parts = []
        if self.summary or self.relevant_history or self.user_profile or self.recent_messages:
            parts.append("[历史上下文仅供引用；订单、物流、库存、退款、审批与资格状态必须重新查询业务工具。]")
        if self.summary:
            parts.append(f"[会话摘要]\n{self._clean(self.summary)}")
        if self.relevant_history:
            parts.append("[相关历史]\n" + "\n".join(f"- {self._clean(h)}" for h in self.relevant_history[:3]))
        if self.user_profile:
            parts.append(f"[用户画像]\n{json.dumps(self.user_profile, ensure_ascii=True)}")
        if self.recent_messages:
            parts.append("[最近对话]")
            for m in self.recent_messages[-8:]:
                parts.append(f"{m.role.value}: {self._clean(m.content)}")
        return "\n\n".join(parts)


class MemoryManager:
    """
    三级记忆管理器。

    工作记忆存 Redis（TTL 24h）；筛选后的长期信息存外部 Chroma。
    """

    WORKING_MAX   = 20    # 工作记忆最大条数，超过则触发压缩
    COMPRESS_AT   = 15    # 达到此条数时压缩，保留摘要 + 最近 5 条
    HISTORY_TOP_K = 5     # 情景记忆检索返回条数
    SUMMARY_MAX_CHARS = 800
    PROFILE_DOC_PREFIX = "user_profile:"
    EPISODIC_COLLECTION = "cartcare_memory_topics_chargram_v1"
    PROFILE_COLLECTION = "cartcare_memory_profile_chargram_v1"
    PROFILE_TTL_DAYS = 180
    EPISODIC_TTL_DAYS = 30

    def __init__(
        self,
        redis_url:    str = "redis://localhost:6379/0",
        chroma_host:  str = "localhost",
        chroma_port:  int = 8000,
        chroma_path:  str = "./data/chroma",
        api_key:      str = "",
        base_url:     Optional[str] = None,
        model:        str = "claude-3-5-sonnet-20241022",
    ):
        self._redis = redis.from_url(redis_url, decode_responses=True)

        # ChromaDB：只连接独立服务（docker compose 模式）；chroma_path 仅为兼容旧调用方保留。
        try:
            # HttpClient 默认也会初始化 ChromaDB telemetry；显式关闭避免 posthog 兼容性错误日志。
            chroma = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            chroma.heartbeat()  # 测试连接
            logger.info(f"ChromaDB 已连接: {chroma_host}:{chroma_port}")
        except Exception as exc:
            message = f"无法连接 ChromaDB Server: {chroma_host}:{chroma_port}"
            logger.error(message)
            raise ConnectionError(message) from exc

        # 情景记忆：存储历史对话片段
        self._episodic = chroma.get_or_create_collection(
            self.EPISODIC_COLLECTION, metadata={"embedding_version": EMBEDDING_VERSION})
        # 用户画像：存储提炼出的偏好和实体
        self._profile  = chroma.get_or_create_collection(
            self.PROFILE_COLLECTION, metadata={"embedding_version": EMBEDDING_VERSION})

    # ── 写入 ──────────────────────────────────────────────────────────────────

    async def add_message(
        self,
        user_id: str,
        conv_id: str,
        role:    MsgRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将一条消息写入工作记忆，超阈值时自动压缩。"""
        user_id = self._safe_text(user_id)
        conv_id = self._safe_text(conv_id)
        clean_metadata = {
            self._safe_text(k): self._safe_metadata_value(v)
            for k, v in (metadata or {}).items()
        }
        msg = Message(role=role, content=self._safe_text(content), metadata=clean_metadata)
        key = self._wm_key(user_id, conv_id)

        # 追加到 Redis 列表（左推，最新在前）
        await self._redis.lpush(key, json.dumps({
            "role":      msg.role.value,
            "content":   msg.content,
            "ts":        msg.timestamp.isoformat(),
            "metadata":  msg.metadata,
        }))
        await self._redis.expire(key, 86400)  # 24h TTL

        # 超过压缩阈值时触发压缩
        if await self._redis.llen(key) >= self.COMPRESS_AT:
            await self._compress(user_id, conv_id)

    async def update_profile(self, user_id: str, conv_id: str) -> None:
        """Persist only explicit, allowlisted communication preferences."""
        user_id, conv_id = self._safe_text(user_id), self._safe_text(conv_id)
        messages = await self._get_working_memory(user_id, conv_id)
        latest_user = next((m for m in reversed(messages) if m.role is MsgRole.USER), None)
        updates = explicit_preferences(latest_user.content) if latest_user else {}
        if not updates:
            return
        try:
            preferences = validated_preferences((await self._get_profile(user_id)).get("preferences"))
            preferences.update(updates)
            now = datetime.now(timezone.utc)
            await asyncio.to_thread(
                self._profile.upsert,
                ids=[self._profile_doc_id(user_id)],
                documents=[json.dumps({"preferences": preferences}, ensure_ascii=False)],
                embeddings=[embed_query("用户偏好")],
                metadatas=[{"user_id": user_id, "conv_id": conv_id,
                            "source": "explicit_user_statement", "memory_type": "user_profile",
                            "created_at": now.isoformat(),
                            "expires_at": (now + timedelta(days=self.PROFILE_TTL_DAYS)).isoformat()}],
            )
        except Exception as ex:
            logger.warning(f"更新用户画像失败: {ex}")

    # ── 读取 ──────────────────────────────────────────────────────────────────

    async def get_context(self, user_id: str, conv_id: str, query: str = "") -> MemoryContext:
        """
        构建完整的记忆上下文。

        query 用于从情景记忆中检索语义相关的历史片段。
        """
        # 1. 工作记忆（当前会话最近消息）
        user_id = self._safe_text(user_id)
        conv_id = self._safe_text(conv_id)
        query = self._safe_text(query)

        recent = await self._get_working_memory(user_id, conv_id)

        # 2. 情景记忆（跨会话语义检索）
        history = await self._search_episodic(
            user_id,
            conv_id,
            query or (recent[-1].content if recent else ""),
        )

        # 3. 用户画像
        profile = await self._get_profile(user_id)

        # 4. 会话摘要（如果已压缩过）
        summary = await self._redis.get(self._summary_key(user_id, conv_id)) or ""

        return MemoryContext(
            recent_messages=recent,
            relevant_history=history,
            user_profile=profile,
            summary=summary,
        )

    # ── 压缩（防止 context 爆炸）─────────────────────────────────────────────

    async def _compress(self, user_id: str, conv_id: str) -> None:
        """Atomically retain five recent messages and a bounded safe reference summary."""
        messages = await self._get_working_memory(user_id, conv_id)
        if len(messages) < self.COMPRESS_AT:
            return
        skey = self._summary_key(user_id, conv_id)
        old_summary = await self._redis.get(skey) or ""
        if not old_summary.startswith("历史参考；"):
            old_summary = ""  # Legacy free-form model summary is unverified.
        summary = compressed_summary(messages, old_summary)[:self.SUMMARY_MAX_CHARS]
        key = self._wm_key(user_id, conv_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            if summary:
                pipe.setex(skey, 86400, summary)
            else:
                pipe.delete(skey)
            pipe.ltrim(key, 0, 4)  # Redis list is newest first; retain concurrent writes.
            pipe.expire(key, 86400)
            await pipe.execute()
        await self._store_episodic(user_id, conv_id, episodic_topics(messages[:-5]))
        logger.info(f"工作记忆压缩完成: {user_id}/{conv_id}，摘要 {len(summary)} 字")

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    async def _get_working_memory(self, user_id: str, conv_id: str) -> List[Message]:
        key  = self._wm_key(user_id, conv_id)
        raws = await self._redis.lrange(key, 0, self.WORKING_MAX - 1)
        msgs = []
        for raw in reversed(raws):  # Redis lpush 最新在前，reversed 还原时序
            d = json.loads(raw)
            msgs.append(Message(
                role=MsgRole(d["role"]),
                content=d["content"],
                timestamp=datetime.fromisoformat(d["ts"]),
                metadata=d.get("metadata", {}),
            ))
        return msgs

    async def _search_episodic(self, user_id: str, conv_id: str, query: str) -> List[str]:
        """Return only unexpired, sourced support topics for this user."""
        query_text = self._safe_text(query).strip()
        if not query_text:
            return []
        try:
            results = await self._query_episodic(query_text, n_results=self.HISTORY_TOP_K,
                where={"$and": [{"user_id": user_id}, {"conv_id": conv_id}]})
            docs = self._verified_episodic_docs(results, user_id)
            if len(docs) < self.HISTORY_TOP_K:
                fallback = await self._query_episodic(query_text, n_results=self.HISTORY_TOP_K,
                    where={"user_id": user_id})
                docs.extend(self._verified_episodic_docs(fallback, user_id))
            return self._dedupe_texts(docs)[:self.HISTORY_TOP_K]
        except Exception as ex:
            logger.warning(f"情景记忆检索失败: {ex}")
            return []

    async def _store_episodic(self, user_id: str, conv_id: str, topics: List[str]) -> None:
        """Keep only deduplicated non-sensitive topics, never the raw transcript."""
        if not topics:
            return
        try:
            now = datetime.now(timezone.utc)
            digest = ", ".join(topics)
            doc_id = hashlib.sha256(f"{user_id}:{conv_id}:{digest}".encode()).hexdigest()
            await asyncio.to_thread(
                self._episodic.upsert,
                ids=[doc_id],
                documents=[f"用户曾咨询 {digest}；后续必须重新检索当前政策。"],
                embeddings=[embed_query(digest)],
                metadatas=[{"user_id": user_id, "conv_id": conv_id,
                            "source": "explicit_user_topic", "memory_type": "support_topic",
                            "created_at": now.isoformat(),
                            "expires_at": (now + timedelta(days=self.EPISODIC_TTL_DAYS)).isoformat()}],
            )
        except Exception as ex:
            logger.warning(f"存储情景记忆失败: {ex}")

    async def _get_profile(self, user_id: str) -> Dict[str, Any]:
        """Ignore legacy, expired or inferred profile records."""
        try:
            direct = await asyncio.to_thread(self._profile.get, ids=[self._profile_doc_id(user_id)])
            if direct.get("documents") and direct.get("metadatas") and fresh_metadata(
                direct["metadatas"][0], user_id=user_id, memory_type="user_profile",
                source="explicit_user_statement"):
                preferences = validated_preferences(json.loads(direct["documents"][0]).get("preferences"))
                return {"preferences": preferences} if preferences else {}
        except Exception:
            pass
        return {}

    async def close(self) -> None:
        """关闭异步 Redis 连接。"""
        await self._redis.aclose()

    async def delete_session(self, user_id: str, conv_id: str) -> None:
        """Forget one session without deleting the user's explicit preferences."""
        user_id, conv_id = self._safe_text(user_id), self._safe_text(conv_id)
        await self._redis.delete(self._wm_key(user_id, conv_id), self._summary_key(user_id, conv_id))
        await asyncio.to_thread(self._episodic.delete,
            where={"$and": [{"user_id": user_id}, {"conv_id": conv_id}]})

    async def delete_user_memory(self, user_id: str) -> None:
        """Internal deletion hook; no public endpoint until identity is authenticated."""
        user_id = self._safe_text(user_id)
        component = quote(user_id, safe="")
        for prefix in ("wm", "summary"):
            async for key in self._redis.scan_iter(match=f"{prefix}:{component}:*"):
                await self._redis.delete(key)
        await asyncio.to_thread(self._episodic.delete, where={"user_id": user_id})
        await asyncio.to_thread(self._profile.delete, ids=[self._profile_doc_id(user_id)])

    @staticmethod
    def _wm_key(user_id: str, conv_id: str) -> str:
        return f"wm:{quote(user_id, safe='')}:{quote(conv_id, safe='')}"

    @staticmethod
    def _summary_key(user_id: str, conv_id: str) -> str:
        return f"summary:{quote(user_id, safe='')}:{quote(conv_id, safe='')}"

    @classmethod
    def _profile_doc_id(cls, user_id: str) -> str:
        return f"{cls.PROFILE_DOC_PREFIX}{user_id}"

    @staticmethod
    def _safe_text(value: Any) -> str:
        """转成 ChromaDB 可接受的普通 UTF-8 字符串。"""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.encode("utf-8", errors="ignore").decode("utf-8")

    @classmethod
    def _safe_metadata_value(cls, value: Any) -> Any:
        """递归清洗 metadata，避免 Redis/ChromaDB 后续读写遇到非法 UTF-8。"""
        if isinstance(value, str):
            return cls._safe_text(value)
        if isinstance(value, dict):
            return {cls._safe_text(k): cls._safe_metadata_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._safe_metadata_value(v) for v in value]
        return value

    async def _query_episodic(
        self,
        query_text: str,
        n_results: int,
        where: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._episodic.query,
            query_embeddings=[embed_query(query_text)],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas"],
        )

    @staticmethod
    def _verified_episodic_docs(results: Dict[str, Any], user_id: str) -> List[str]:
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        return [doc for doc, metadata in zip(documents, metadatas)
                if isinstance(doc, str) and doc.strip() and fresh_metadata(
                    metadata, user_id=user_id, memory_type="support_topic", source="explicit_user_topic")]

    @staticmethod
    def _dedupe_texts(values: List[str]) -> List[str]:
        seen = set()
        deduped: List[str] = []
        for value in values:
            text = value.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(text)
        return deduped
