"""
CartCare 智能客服系统 — FastAPI 入口

启动时打印 CartCare 启动标识。
所有核心组件在 lifespan 中初始化，通过环境变量配置。
"""
import asyncio
import json
import logging
import os
import pathlib
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional


_ROOT = str(pathlib.Path(__file__).parent.parent.resolve())
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, ValidationError
from actions import ActionResult

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BANNER = """========================================
 CartCare
 E-commerce Support Agent
========================================
"""

# ── 全局组件（lifespan 中初始化）─────────────────────────────────────────────
_orchestrator = None
_memory       = None
_tool_manager = None
_monitor      = None
_evaluator    = None
_skill_manager = None
_action_service = None

def _anthropic_cfg() -> Dict[str, Any]:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("未设置 ANTHROPIC_API_KEY")
    cfg: Dict[str, Any] = {
        "api_key":  key,
        "model":    os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip(),
    }
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    if base_url:
        cfg["base_url"] = base_url
    return cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _memory, _tool_manager, _monitor, _evaluator, _skill_manager, _action_service

    print(BANNER, flush=True)

    from agents.support_agent import SupportRuntime
    from agents.tools import build_shared_rag_tools
    from agents.tools import build_action_tools, build_business_tools
    from actions import ActionService, InMemoryBusinessActionBackend
    from core.intent_recognizer import IntentRecognizer
    from evaluation.evaluator import EndToEndEvaluator
    from mcp.knowledge_base import KnowledgeBase
    from mcp.tool_manager import MCPToolManager, Tool
    from core.tool_contract import RetryPolicy
    from memory.conversation_memory import MemoryManager
    from monitor.performance_monitor import PerformanceMonitor
    from core.skill_loader import SkillManager
    from providers.mock_backend import InMemoryBusinessBackend

    cfg = _anthropic_cfg()
    logger.info(f"模型: {cfg['model']}  base_url: {cfg.get('base_url', '(官方)')}")

    # 可选意图诊断，仅用于显式请求的评测，不参与 /chat dispatch。
    recognizer = IntentRecognizer(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # Skills：启动时从目录加载业务能力说明，并在 Agent 调用 LLM 时动态注入。
    skills_dir = os.getenv("ECHOMIND_SKILLS_DIR", str(pathlib.Path(_ROOT) / "skills"))
    _skill_manager = SkillManager(
        root_dir=skills_dir,
        max_prompt_chars=int(os.getenv("ECHOMIND_SKILLS_MAX_PROMPT_CHARS", "5000")),
    )
    _skill_manager.load()

    # 单客服 Agent runtime
    _orchestrator = SupportRuntime(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        skill_manager=_skill_manager,
    )

    # 记忆管理器（Redis 工作记忆 + ChromaDB 情景记忆/用户画像）
    _memory = MemoryManager(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # MCP 工具管理器 + RAG 知识库（基于 ChromaDB 的真实检索）
    _tool_manager = MCPToolManager(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )
    kb = KnowledgeBase(
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
    )
    logger.info(f"知识库已加载: {await kb.doc_count_async()} 个文档片段")

    def knowledge_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str):
        query = params.get("query", "")
        return [{
            "title": "知识库降级结果",
            "content": f"知识库暂时不可用，未能完成对“{query}”的语义检索。请稍后重试，或转人工客服确认。",
            "score": 0.0,
            "fallback": True,
            "error": error,
        }]

    _tool_manager.register(Tool(
        name="knowledge_search",
        description="搜索知识库（基于 ChromaDB 向量检索）",
        handler=kb.search_handler,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        cache_ttl=300.0,
        supports_rerank=True,
        fallback=knowledge_fallback,
        retry_policy=RetryPolicy(max_attempts=2),
    ))
    from core.model_observation import ObservedClient
    _tool_manager._client = ObservedClient(_tool_manager._client, "rag_rewrite_or_rerank")

    business_fixture = os.getenv(
        "CARTCARE_BUSINESS_FIXTURE",
        str(pathlib.Path(_ROOT) / "providers" / "fixtures" / "business_provider_data.json"),
    )
    with open(business_fixture, "r", encoding="utf-8") as handle:
        business_data = json.load(handle)
    business_backend = InMemoryBusinessBackend(business_data)
    action_backend = InMemoryBusinessActionBackend(business_data)
    _action_service = ActionService(
        business_backend=business_backend,
        action_backend=action_backend,
    )
    business_tools = build_business_tools(business_backend)
    business_tools.update(build_action_tools(_action_service))
    logger.info(
        "业务工具已加载（测试/演示 backend）: %s",
        ", ".join(sorted(business_tools)),
    )

    if _orchestrator is not None:
        shared_tools = build_shared_rag_tools(_tool_manager)
        shared_tools.update(business_tools)
        _orchestrator.set_shared_tools(shared_tools)

    # 性能监控（可选启动 Prometheus）
    prom_port = int(os.getenv("PROMETHEUS_PORT", "0")) or None
    _monitor = PerformanceMonitor(
        orchestrator=_orchestrator,
        tool_manager=_tool_manager,
        interval_s=float(os.getenv("MONITOR_INTERVAL", "10")),
        webhook_url=os.getenv("ALERT_WEBHOOK_URL") or None,
        prometheus_port=prom_port,
    )
    await _monitor.start()

    # 评测器
    _evaluator = EndToEndEvaluator(
        orchestrator=_orchestrator,
        recognizer=recognizer,
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        baseline_path=os.getenv("EVAL_BASELINE_PATH", "/app/data/eval/baseline.json"),
    )

    logger.info("CartCare 已就绪")
    yield

    await _monitor.stop()
    if _memory is not None:
        await _memory.close()
    if _orchestrator is not None:
        await _orchestrator.close()
    logger.info("CartCare 已关闭")


# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CartCare E-commerce Support Agent",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message:     str
    user_id:     str = "anonymous"
    conv_id:     Optional[str] = None


class ChatResponse(BaseModel):
    conv_id:     str
    request_id:  str = ""
    response:    str
    topology: str = "single"
    intent: Optional[str] = None
    intent_group: Optional[str] = None
    agent_type:  str
    agent_types: List[str] = Field(default_factory=list)
    primary_agent: Optional[str] = Field(default=None, deprecated=True)
    supporting_agents: Optional[List[str]] = Field(default=None, deprecated=True)
    tools_used: List[str] = Field(default_factory=list)
    routing_reason: Optional[str] = Field(default=None, deprecated=True)
    routing_confidence: Optional[float] = Field(default=None, deprecated=True)
    escalated:   bool
    latency_ms:  float
    knowledge_used: bool = False
    retrieval_status: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    intent_confidence: Optional[float] = None
    intent_source_scores: Optional[Dict[str, float]] = None
    model_call_count: int = 0
    model_observation_scope: str = "support + RAG SDK calls; excludes Memory/profile"


def collect_rag_evidence(tool_traces: List[Dict[str, Any]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
    """Expose only usable retrieval citations; trace retrieval is not claim verification."""
    rag_traces = [trace for trace in tool_traces if trace.get("tool_name") == "search_knowledge_base"]
    citations = list({citation["reference"]: citation
                      for trace in rag_traces if trace.get("retrieval_status") == "usable"
                      for citation in trace.get("citations", []) if citation.get("reference")}.values())
    return ("usable" if citations else rag_traces[-1].get("retrieval_status") if rag_traces else None), citations


def render_rag_citations(response: str, citations: List[Dict[str, Any]]) -> str:
    """Make validated retrieval references visible without citing degraded text."""
    references = [item["reference"] for item in citations if item.get("reference")]
    missing = [reference for reference in references if reference not in response]
    return response + ("\n\n知识库引用：" + "；".join(missing) if missing else "")


class ActionCommandRequest(BaseModel):
    user_id: str = "anonymous"
    request_id: Optional[str] = None


class ToolTraceResponse(BaseModel):
    request_id: str
    found: bool
    trace: Dict[str, Any] = Field(default_factory=dict)


class RecentToolTracesResponse(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)


# ── 路由 ──────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if _orchestrator is None:
        raise HTTPException(503, "服务未就绪")
    return {"status": "ok", "agents": _orchestrator.get_stats()}


@app.get("/skills", tags=["Skills"])
async def skills_summary():
    """查看当前已加载的 Skills，便于确认热加载结果和排查解析错误。"""
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    return _skill_manager.summary()


@app.post("/skills/reload", tags=["Skills"])
async def reload_skills():
    """运行时重新扫描 Skill 目录，不需要重启服务。"""
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    _skill_manager.reload()
    if _orchestrator is not None:
        _orchestrator.set_skill_manager(_skill_manager)
    return _skill_manager.summary()


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    主对话接口。完整流程：
      记忆读取 → SingleSupportAgent / Tool Contract → 记忆写入
    """
    if _orchestrator is None or _memory is None:
        raise HTTPException(503, "服务未就绪")

    from agents.agent_orchestrator import Request as OrcReq
    from memory.conversation_memory import MsgRole

    conv_id = req.conv_id or str(uuid.uuid4())

    # 1. 读取记忆上下文
    mem_ctx = await _memory.get_context(req.user_id, conv_id, query=req.message)

    # 2. 构建客服请求；历史直接提供给 Agent。
    history = [
        {"role": m.role.value, "content": m.content}
        for m in mem_ctx.recent_messages[-5:]
    ] if mem_ctx.recent_messages else None

    full_context = mem_ctx.to_prompt_text()

    orch_req = OrcReq(
        message=req.message,
        user_id=req.user_id,
        conv_id=conv_id,
        context=full_context,
        history=history,
    )

    # 3. 执行
    result = await _orchestrator.run(orch_req)

    # 4. 写入记忆
    await _memory.add_message(req.user_id, conv_id, MsgRole.USER, req.message)
    await _memory.add_message(req.user_id, conv_id, MsgRole.ASSISTANT, result.response)

    # 5. 异步更新用户画像（不阻塞响应）
    asyncio.create_task(_memory.update_profile(req.user_id, conv_id))

    retrieval_status, citations = collect_rag_evidence(result.tool_traces)
    return ChatResponse(
        conv_id=conv_id,
        request_id=result.request_id,
        response=render_rag_citations(result.response, citations),
        topology="single",
        agent_type="support",
        agent_types=["support"],
        tools_used=result.tools_used,
        model_call_count=len(result.model_calls),
        escalated=result.escalated,
        latency_ms=round(result.latency_ms, 1),
        knowledge_used=bool(citations),
        retrieval_status=retrieval_status,
        citations=citations,
    )


@app.post("/actions/{action_id}/approve", response_model=ActionResult, tags=["Actions"])
async def approve_action(action_id: str, req: ActionCommandRequest):
    """Approve an awaiting demo action; repeated approvals are idempotent."""
    if _action_service is None:
        raise HTTPException(503, "服务未就绪")
    return _action_service.approve(
        action_id=action_id,
        user_id=req.user_id,
        request_id=req.request_id or str(uuid.uuid4()),
    )


@app.post("/actions/{action_id}/reject", response_model=ActionResult, tags=["Actions"])
async def reject_action(action_id: str, req: ActionCommandRequest):
    """Reject an awaiting demo action; rejection is terminal."""
    if _action_service is None:
        raise HTTPException(503, "服务未就绪")
    return _action_service.reject(
        action_id=action_id,
        user_id=req.user_id,
        request_id=req.request_id or str(uuid.uuid4()),
    )


@app.post("/actions/{action_id}/resume", response_model=ActionResult, tags=["Actions"])
async def resume_action(action_id: str, req: ActionCommandRequest):
    """Resume an approved demo action; completed actions are returned unchanged."""
    if _action_service is None:
        raise HTTPException(503, "服务未就绪")
    return _action_service.resume(
        action_id=action_id,
        user_id=req.user_id,
        request_id=req.request_id or str(uuid.uuid4()),
    )


@app.get("/actions/{action_id}", response_model=ActionResult, tags=["Actions"])
async def get_action(action_id: str, user_id: str = "anonymous"):
    if _action_service is None:
        raise HTTPException(503, "服务未就绪")
    return _action_service.get(action_id, user_id=user_id)


async def _build_knowledge_context(message: str, intent=None, top_k: int = 3) -> tuple[str, bool]:
    """
    为 /chat 主链路构建 RAG 知识上下文。

    这里复用 MCPToolManager 的查询改写、并行召回、重排、fallback 能力。
    """
    if _tool_manager is None:
        return "", False
    if not _should_use_knowledge(message, intent=intent):
        return "", False
    try:
        result = await _tool_manager.search_with_rewrite("knowledge_search", message, top_k=top_k)
        if result.retrieval_status != "usable" or not isinstance(result.data, list) or not result.data:
            return "", False

        parts = ["[知识库检索结果]"]
        used = False
        for i, item in enumerate(result.data[:top_k], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "未命名文档"))
            content = str(item.get("content", "")).strip()
            score = item.get("score", "")
            if not content:
                continue
            used = True
            parts.append(f"{i}. 标题: {title}\n   相关度: {score}\n   内容: {content[:600]}")

        if not used:
            return "", False
        parts.append("请优先依据以上知识库内容回答；如果知识库内容不足，再结合通用客服能力说明。")
        return "\n".join(parts), True
    except Exception as ex:
        logger.warning(f"构建知识库上下文失败: {ex}")
        return "", False


def _should_use_knowledge(message: str, intent=None) -> bool:
    """跳过纯寒暄，业务类问题才检索知识库，避免无关 RAG 干扰回复。"""
    msg = (message or "").strip().lower()
    if not msg:
        return False
    intent_value = getattr(intent, "value", intent)
    if intent_value in {"greeting", "feedback", "escalation", "human_handoff", "other"}:
        return False
    if intent_value in {
        "query", "request", "technical", "billing", "account", "complaint",
        "order_status", "logistics", "refund", "invoice", "payment_issue",
        "account_security", "technical_login", "technical_crash",
    }:
        return True
    greetings = {"你好", "您好", "嗨", "hi", "hello", "hey", "早上好", "晚上好"}
    if msg in greetings:
        return False
    business_keywords = [
        "退款", "订单", "物流", "配送", "发票", "扣款", "支付", "账单", "订阅",
        "登录", "报错", "错误", "崩溃", "会员", "积分", "账户", "密码", "地址",
        "refund", "order", "invoice", "payment", "error", "login",
    ]
    return len(msg) >= 4 or any(kw in msg for kw in business_keywords)


@app.get("/monitor")
async def monitor_summary():
    """实时监控摘要：Agent 成功率、工具统计、告警、优化建议。"""
    if _monitor is None:
        raise HTTPException(503, "服务未就绪")
    return _monitor.summary()


@app.get("/trace/tool/{request_id}", response_model=ToolTraceResponse)
async def get_tool_trace(request_id: str):
    """查看某次请求的工具调用明细。"""
    if _orchestrator is None:
        raise HTTPException(503, "服务未就绪")
    trace = _orchestrator.get_tool_trace(request_id)
    return ToolTraceResponse(
        request_id=request_id,
        found=trace is not None,
        trace=trace or {},
    )


@app.get("/trace/tools", response_model=RecentToolTracesResponse)
async def list_recent_tool_traces(limit: int = 20):
    """查看最近 N 次请求的工具调用明细。"""
    if _orchestrator is None:
        raise HTTPException(503, "服务未就绪")
    return RecentToolTracesResponse(items=_orchestrator.get_recent_tool_traces(limit=limit))


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus 指标入口。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/search")
async def search(query: str, top_k: int = 5):
    """
    演示检索优化链路：查询改写 → 并行召回 → 重排 → Top-K。
    展示 MCP 工具调用的核心亮点。
    """
    if _tool_manager is None:
        raise HTTPException(503, "服务未就绪")
    if top_k < 1:
        raise HTTPException(422, "top_k 必须大于 0")
    result = await _tool_manager.search_with_rewrite("knowledge_search", query, top_k=top_k)
    return {"query": query, "results": result.data, "reranked": result.reranked,
            "retrieval_status": result.retrieval_status, "citations": result.citations,
            "success": result.success, "error_code": result.error_code}


class DocInput(BaseModel):
    """单篇文档输入。"""
    document_id: Optional[str] = None
    title: str
    content: str
    source: str = "api:knowledge/add"
    doc_type: str = "guide"
    policy_version: Optional[str] = None
    effective_at: Optional[str] = None


class BatchDocInput(BaseModel):
    """批量文档导入请求体。"""
    documents: List[DocInput]


class EvalIntentInput(BaseModel):
    """意图识别评测用例。"""
    message: str
    expected_intent: str
    context: Optional[Dict[str, Any]] = None


class EvalDialogInput(BaseModel):
    """对话质量评测用例。question 单轮，turns 多轮。"""
    question: Optional[str] = None
    turns: Optional[List[str]] = None
    user_id: Optional[str] = None
    conv_id: Optional[str] = None


class EvalRunInput(BaseModel):
    """评测请求。为空时使用内置默认用例。"""
    intent_cases: Optional[List[EvalIntentInput]] = None
    dialog_cases: Optional[List[EvalDialogInput]] = None


@app.post("/knowledge/add", tags=["知识库"])
async def add_knowledge(body: BatchDocInput):
    """
    批量导入文档到知识库。

    文档会自动切片（每片 500 字），使用应用端版本化显式向量后存入 Chroma HTTP。

    示例请求体：
    ```json
    {
      "documents": [
        {"title": "演示退款政策", "content": "示例政策内容...", "source": "demo:manual-policy",
         "doc_type": "policy", "policy_version": "demo-v1", "effective_at": "2026-09-30T00:00:00Z"},
        {"title": "配送说明", "content": "标准配送 3-5 个工作日..."}
      ]
    }
    ```
    """
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__
    try:
        count = await kb.add_documents_async([d.model_dump(exclude_none=True) for d in body.documents])
    except (ValidationError, ValueError) as exc:
        detail = exc.errors(include_input=False, include_context=False) if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(422, {"error": "文档 metadata 无效", "details": detail}) from exc
    _tool_manager._cache.clear()
    total = await kb.doc_count_async()
    return {"message": f"成功导入 {count} 个文档片段", "added_chunks": count, "total_chunks": total}


@app.post("/knowledge/upload", tags=["知识库"])
async def upload_knowledge(file: UploadFile = File(...)):
    """
    上传文件导入知识库。

    支持格式：
    - `.txt` / `.md`：整个文件作为一篇文档，文件名作为标题
    - `.json`：JSON 数组格式 `[{"title": "...", "content": "..."}, ...]`

    文件大小限制：10MB
    """
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件大小超过 10MB 限制")

    text = content.decode("utf-8", errors="ignore")
    filename = file.filename or "unknown"

    if filename.endswith(".json"):
        import json as _json
        try:
            docs = _json.loads(text)
            if not isinstance(docs, list):
                raise HTTPException(400, "JSON 文件应为数组格式: [{title, content}, ...]")
        except _json.JSONDecodeError as e:
            raise HTTPException(400, f"JSON 解析失败: {e}")
        for doc in docs:
            if not isinstance(doc, dict):
                raise HTTPException(422, "JSON 文档必须是对象")
            doc.setdefault("source", f"upload:{filename}")
            doc.setdefault("doc_type", "guide")
    else:
        # txt / md：整个文件作为一篇文档
        title = filename.rsplit(".", 1)[0] if "." in filename else filename
        docs = [{"title": title, "content": text, "source": f"upload:{filename}",
                 "doc_type": "guide"}]

    try:
        count = await kb.add_documents_async(docs)
    except (ValidationError, ValueError) as exc:
        detail = exc.errors(include_input=False, include_context=False) if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(422, {"error": "文档 metadata 无效", "details": detail}) from exc
    _tool_manager._cache.clear()
    total = await kb.doc_count_async()
    return {
        "message": f"文件 {filename} 导入成功",
        "added_chunks": count,
        "total_chunks": total,
    }


@app.get("/knowledge/stats", tags=["知识库"])
async def knowledge_stats():
    """查看知识库统计信息（文档片段总数）。"""
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    kb = tool.handler.__self__
    return {"total_chunks": await kb.doc_count_async()}


@app.post("/eval/run")
async def run_eval(body: Optional[EvalRunInput] = None):
    """运行内置评测用例，返回评测报告。"""
    if _evaluator is None:
        raise HTTPException(503, "服务未就绪")
    from evaluation.evaluator import DEFAULT_DIALOG_CASES, DEFAULT_INTENT_CASES, IntentTestCase

    if body and body.intent_cases is not None:
        intent_cases = [
            IntentTestCase(
                message=c.message,
                expected_intent=c.expected_intent,
                context=c.context,
            )
            for c in body.intent_cases
        ]
    else:
        intent_cases = []

    if body and body.dialog_cases is not None:
        dialog_cases = [
            c.model_dump(exclude_none=True)
            for c in body.dialog_cases
        ]
    else:
        dialog_cases = DEFAULT_DIALOG_CASES

    report = await _evaluator.run(
        intent_cases=intent_cases,
        dialog_cases=dialog_cases,
    )
    return {
        "pass_rate":       report.pass_rate,
        "total":           report.total,
        "passed":          report.passed,
        "avg_scores":      report.avg_scores,
        "regressions":     report.regressions,
        "recommendations": report.recommendations,
        "results": [
            {
                "test_id": r.test_id,
                "passed": r.passed,
                "scores": r.scores,
                "detail": r.detail,
                "metadata": r.metadata,
            }
            for r in report.results
        ],
    }


# ── 交互式 CLI ────────────────────────────────────────────────────────────────
async def _cli():
    """CLI shares production initialization and the same guarded chat path."""
    print("CartCare CLI — 输入 quit 退出\n")
    async with lifespan(app):
        conv_id = str(uuid.uuid4())
        while True:
            try:
                msg = input("你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见")
                break
            if not msg or msg.lower() in ("quit", "exit", "退出"):
                print("再见")
                break
            result = await chat(ChatRequest(message=msg, user_id="cli_user", conv_id=conv_id))
            print(f"\nCartCare [{result.agent_type}]: {result.response}\n")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(_cli())
    else:
        uvicorn.run(
            "api.main:app",
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            reload=os.getenv("APP_ENV") == "development",
        )
