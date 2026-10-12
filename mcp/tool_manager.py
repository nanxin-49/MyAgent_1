"""
亮点：MCP 工具调用框架

核心问题：工具调用出错（检索不全、召回不好）怎么优化？

本模块的答案：
  1. 查询改写（Query Rewriting）—— 用 LLM 把用户原始问题扩写成多个角度的子查询，
     再合并去重，解决"召回不全"问题。
  2. 结果重排（Reranking）—— 对召回结果用 LLM 打分，按相关性重新排序，
     解决"召回不好/排序差"问题。
  3. 熔断器（Circuit Breaker）—— 连续失败超阈值时自动断开，防止雪崩。
  4. 结果缓存（TTL Cache）—— 相同参数直接返回缓存，减少重复调用。
  5. 降级策略（Fallback）—— 工具不可用时返回有意义的降级结果。
"""
import asyncio
import hashlib
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from anthropic import AsyncAnthropic

from core.llm_utils import extract_text_content
from core.tool_contract import RetryPolicy, RiskLevel, ToolValidationError, execute_tool, validate_tool_input
from mcp.rag_contract import RetrievalHit, RetrievalStatus

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED    = "closed"     # 正常
    OPEN      = "open"       # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 探测恢复


@dataclass
class ToolResult:
    success:        bool
    data:           Any
    tool_name:      str
    error:          Optional[str] = None
    cached:         bool = False
    latency_ms:     float = 0.0
    reranked:       bool = False   # True only for a validated model ordering
    error_code:     Optional[str] = None
    error_type:     Optional[str] = None
    retryable:      bool = False
    validated_input: Optional[Dict[str, Any]] = None
    attempts:       int = 0
    retrieval_status: Optional[str] = None
    citations:      List[Dict[str, Any]] = field(default_factory=list)
    rerank_status:  str = "not_requested"


@dataclass(frozen=True)
class RerankResult:
    items: List[Any]
    reranked: bool
    status: str


@dataclass
class ToolStats:
    """工具运行时统计，供 Monitor 读取。"""
    total:              int = 0
    success:            int = 0
    failed:             int = 0
    total_latency_ms:   float = 0.0
    consecutive_fails:  int = 0

    @property
    def success_rate(self) -> float:
        return self.success / self.total if self.total else 1.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total if self.total else 0.0


# ── 熔断器 ────────────────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    三态熔断器：CLOSED → OPEN → HALF_OPEN → CLOSED

    连续失败 failure_threshold 次后打开；
    打开 recovery_s 秒后进入 HALF_OPEN 探测；
    探测成功则关闭，失败则重新打开。
    """

    def __init__(self, failure_threshold: int = 5, recovery_s: float = 60.0):
        self.threshold   = failure_threshold
        self.recovery_s  = recovery_s
        self.state       = CircuitState.CLOSED
        self.fail_count  = 0
        self.opened_at:  Optional[float] = None

    def allow(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.opened_at >= self.recovery_s:  # type: ignore
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN：放行一次探测

    def record_success(self) -> None:
        self.fail_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.fail_count += 1
        if self.fail_count >= self.threshold:
            self.state     = CircuitState.OPEN
            self.opened_at = time.monotonic()
            logger.warning(f"熔断器打开（连续失败 {self.fail_count} 次）")


# ── 工具定义 ──────────────────────────────────────────────────────────────────

@dataclass
class Tool:
    name:        str
    description: str
    handler:     Callable                    # async (params, context) -> Any
    schema:      Dict[str, Any]              # JSON Schema
    cache_ttl:   float = 0.0                 # 0 = 不缓存
    timeout_s:   float = 30.0
    supports_rerank: bool = False            # 是否支持结果重排
    fallback:    Optional[Callable] = None    # sync/async (params, context, error) -> Any
    risk_level: RiskLevel = RiskLevel.READ
    retry_policy: RetryPolicy = RetryPolicy()
    idempotent: bool = True

    # 运行时状态（不参与构造）
    stats:   ToolStats    = field(default_factory=ToolStats, init=False)
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker, init=False)

    @property
    def input_schema(self) -> Dict[str, Any]:
        return self.schema


# ── MCP 工具管理器 ────────────────────────────────────────────────────────────

class MCPToolManager:
    """
    MCP 工具调用框架。

    核心优化链路（针对检索类工具）：
      用户查询 → 查询改写（多角度子查询）→ 并行召回 → 结果重排 → 返回 Top-K
    """

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model  = model
        self._tools: Dict[str, Tool] = {}
        self._cache: Dict[str, tuple] = {}   # key → (result, expire_at, reranked)

    # ── 注册 / 注销 ───────────────────────────────────────────────────────────

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name}")

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    # ── 核心调用 ──────────────────────────────────────────────────────────────

    async def call(
        self,
        name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        *,
        use_cache: bool = True,
        rerank_top_k: int = 0,          # >0 时对结果重排，取 Top-K
    ) -> ToolResult:
        """
        调用工具，完整执行链：
          缓存检查 → 熔断检查 → 参数校验 → 执行（含超时）→ 可选重排 → 缓存写入
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, data=None, tool_name=name, error=f"工具不存在: {name}",
                              error_code="tool_not_found", error_type="validation")

        try:
            validated = validate_tool_input(tool.input_schema, params)
        except ToolValidationError as exc:
            return ToolResult(success=False, data=None, tool_name=name, error=str(exc),
                              error_code=exc.code, error_type="validation")

        owner = getattr(tool.handler, "__self__", None)
        use_cache = (use_cache and tool.risk_level is RiskLevel.READ
                     and not hasattr(owner, "validate_hits_async"))

        cache_rerank_top_k = rerank_top_k if rerank_top_k > 0 and tool.supports_rerank else 0

        # 缓存命中
        if use_cache and tool.cache_ttl > 0:
            cached = self._get_cache(name, params, cache_rerank_top_k)
            if cached is not None:
                cached_data, cached_reranked, cached_status = cached
                tool.stats.total += 1
                tool.stats.success += 1
                return ToolResult(
                    success=True,
                    data=cached_data,
                    tool_name=name,
                    cached=True,
                    reranked=cached_reranked,
                    rerank_status=cached_status,
                    validated_input=validated,
                )

        # 熔断检查
        if not tool.breaker.allow():
            error = f"工具熔断中: {name}，请稍后重试"
            return await self._fallback_result(tool, params, context, error,
                                               error_code="circuit_open", retryable=True,
                                               validated_input=validated)

        t0 = time.monotonic()
        tool.stats.total += 1
        async def invoke_handler() -> Any:
            return await self._run_handler(tool, params, context)

        execution = await execute_tool(tool, params, invoke_handler)
        latency = (time.monotonic() - t0) * 1000
        if execution.success:
            data = execution.data
            tool.stats.success += 1
            tool.stats.consecutive_fails = 0
            tool.stats.total_latency_ms += latency
            tool.breaker.record_success()

            # 重排（针对返回列表的检索工具）
            reranked = False
            rerank_status = "not_requested"
            if rerank_top_k > 0 and tool.supports_rerank and isinstance(data, list):
                query = params.get("query", "")
                candidates = data
                outcome = await self._rerank(query, candidates, rerank_top_k)
                data, reranked, rerank_status = outcome.items, outcome.reranked, outcome.status
                if hasattr(owner, "validate_hits_async"):
                    result = await self._finalize_rag(name, candidates, outcome, rerank_top_k)
                    result.latency_ms = latency
                    result.validated_input = validated
                    result.attempts = execution.attempts
                    return result

            # 写缓存：缓存最终返回结果，避免下次命中未重排的原始结果。
            if use_cache and tool.cache_ttl > 0:
                self._set_cache(name, params, data, tool.cache_ttl, cache_rerank_top_k, reranked, rerank_status)

            return ToolResult(success=True, data=data, tool_name=name,
                              latency_ms=latency, reranked=reranked, rerank_status=rerank_status,
                              validated_input=validated, attempts=execution.attempts)

        tool.stats.failed += 1
        tool.stats.consecutive_fails += 1
        if execution.retryable:
            tool.breaker.record_failure()
        logger.error("工具异常: %s — %s", name, execution.error)
        if not execution.retryable:
            return ToolResult(success=False, data=execution.data, tool_name=name,
                              error=execution.error, error_code=execution.error_code,
                              error_type=execution.error_type, retryable=False,
                              latency_ms=latency, validated_input=validated,
                              attempts=execution.attempts)
        return await self._fallback_result(tool, params, context, execution.error or "工具执行失败",
                                           error_code=execution.error_code, error_type=execution.error_type,
                                           retryable=execution.retryable, latency_ms=latency,
                                           validated_input=validated, attempts=execution.attempts)

    async def _fallback_result(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        error: str,
        *,
        error_code: Optional[str] = None,
        error_type: Optional[str] = None,
        retryable: bool = False,
        latency_ms: float = 0.0,
        validated_input: Optional[Dict[str, Any]] = None,
        attempts: int = 0,
    ) -> ToolResult:
        """工具不可用时返回降级结果，而不是把空错误直接暴露给调用方。"""
        if tool.fallback is None or tool.risk_level is not RiskLevel.READ:
            return ToolResult(success=False, data=None, tool_name=tool.name, error=error,
                              error_code=error_code, error_type=error_type, retryable=retryable,
                              latency_ms=latency_ms, validated_input=validated_input, attempts=attempts)
        try:
            data = tool.fallback(params, context, error)
            if asyncio.iscoroutine(data):
                data = await data
            return ToolResult(
                success=True,
                data=data,
                tool_name=tool.name,
                error=error,
                error_code=error_code,
                error_type=error_type,
                retryable=retryable,
                latency_ms=latency_ms,
                validated_input=validated_input,
                attempts=attempts,
            )
        except Exception as ex:
            logger.error(f"工具降级失败: {tool.name} — {ex}")
            return ToolResult(success=False, data=None, tool_name=tool.name, error=f"{error}; fallback失败: {ex}",
                              error_code=error_code, error_type=error_type, retryable=retryable,
                              latency_ms=latency_ms, validated_input=validated_input, attempts=attempts)

    async def _run_handler(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """
        执行工具 handler。

        优先支持 async handler；如果历史工具仍是同步函数，则放入线程池执行，
        避免阻塞事件循环。
        """
        if inspect.iscoroutinefunction(tool.handler):
            return await tool.handler(params, context)
        result = await asyncio.to_thread(tool.handler, params, context)
        if inspect.isawaitable(result):
            return await result
        return result

    # ── 查询改写（解决召回不全）────────────────────────────────────────────────

    async def rewrite_query(self, query: str, n: int = 3) -> List[str]:
        """
        用 LLM 将原始查询改写为 n 个不同角度的子查询。

        目的：单一查询往往只能召回某一角度的文档，
        多角度子查询并行检索后合并，显著提升召回率。

        示例：
          原始: "退款流程"
          改写: ["如何申请退款", "退款需要多少天", "退款政策是什么"]
        """
        prompt = f"""将以下用户查询改写为 {n} 个不同角度的搜索子查询，用于检索知识库。
要求：每个子查询角度不同，覆盖原始问题的不同方面。
原始查询: "{query}"
返回 JSON 数组，例如: ["子查询1", "子查询2", "子查询3"]"""
        prompt = self._clean_text(prompt)
        try:
            resp = await self._client.messages.create(
                model=self._model, max_tokens=256, temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = extract_text_content(resp.content)
            s, e = raw.find("["), raw.rfind("]") + 1
            queries = json.loads(raw[s:e])
            # 原始查询也保留，去重
            return list(dict.fromkeys([query] + queries))
        except Exception as ex:
            logger.warning(f"查询改写失败，使用原始查询: {ex}")
            return [query]

    async def search_with_rewrite(
        self,
        tool_name: str,
        query: str,
        top_k: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """
        完整的检索优化链路：查询改写 → 并行召回 → 去重 → 重排 → Top-K

        这是解决"检索不全、召回不好"的完整方案。
        """
        if not isinstance(query, str) or not query.strip() or top_k < 1:
            return ToolResult(success=False, data=[], tool_name=tool_name,
                              error="query 不能为空且 top_k 必须大于 0",
                              error_code="invalid_arguments", error_type="validation",
                              retrieval_status=RetrievalStatus.NO_ANSWER.value)
        # 1. 查询改写：生成多角度子查询
        sub_queries = await self.rewrite_query(query, n=3)
        logger.info(f"查询改写: {query!r} → {sub_queries}")

        # 2. 并行召回：所有子查询同时检索
        recall_k = max(top_k, 5)
        tasks = [
            self.call(tool_name, {"query": q, "top_k": recall_k}, context, use_cache=True)
            for q in sub_queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Only complete, high-enough, non-fallback hits may become answer evidence.
        seen, merged, low_confidence = set(), [], []
        degraded = False
        for r in results:
            if not isinstance(r, ToolResult):
                degraded = True
                continue
            if not r.success:
                degraded = degraded or r.error_code not in {"no_results"}
                continue
            if r.error_code is not None:
                degraded = True  # dependency fallback is never answer evidence
                continue
            if not isinstance(r.data, list):
                degraded = True
                continue
            for item in r.data:
                if not isinstance(item, dict) or item.get("fallback"):
                    degraded = True
                    continue
                try:
                    hit = RetrievalHit.model_validate(item)
                except Exception:
                    degraded = True
                    continue
                normalized = hit.model_dump(mode="json")
                if hit.retrieval_status is not RetrievalStatus.USABLE or hit.citation is None:
                    low_confidence.append(normalized)
                    continue
                key = hit.citation.reference
                if key not in seen:
                    seen.add(key)
                    merged.append(normalized)

        if not merged:
            status = (RetrievalStatus.DEGRADED if degraded else
                      RetrievalStatus.LOW_CONFIDENCE if low_confidence else RetrievalStatus.NO_ANSWER)
            return ToolResult(success=status is not RetrievalStatus.DEGRADED, data=[],
                              tool_name=tool_name,
                              error="RAG retrieval unavailable" if status is RetrievalStatus.DEGRADED else None,
                              error_code="degraded" if status is RetrievalStatus.DEGRADED else None,
                              error_type="retrieval" if status is RetrievalStatus.DEGRADED else None,
                              retrieval_status=status.value, rerank_status="no_candidates")

        outcome = await self._rerank(query, merged, top_k)
        return await self._finalize_rag(tool_name, merged, outcome, top_k)

    async def _finalize_rag(self, tool_name, candidates, outcome, top_k):
        """Only validated subsets of original evidence can produce usable results."""
        try:
            original = {}
            for item in candidates:
                hit = RetrievalHit.model_validate(item)
                if hit.retrieval_status is RetrievalStatus.USABLE and hit.citation is not None:
                    original[hit.citation.reference] = hit.model_dump(mode="json")
            def checked(items):
                if not isinstance(items, list):
                    raise ValueError("invalid final evidence")
                hits, seen = [], set()
                for item in items:
                    hit = RetrievalHit.model_validate(item)
                    normalized = hit.model_dump(mode="json")
                    if (hit.retrieval_status is not RetrievalStatus.USABLE or hit.citation is None
                            or not hit.content.strip() or original.get(hit.citation.reference) != normalized):
                        raise ValueError("final evidence not in validated candidates")
                    if hit.citation.reference not in seen:
                        seen.add(hit.citation.reference)
                        hits.append(normalized)
                return hits
            final = checked(outcome.items)
            tool = self._tools.get(tool_name)
            owner = getattr(tool.handler, "__self__", None) if tool else None
            if final and hasattr(owner, "validate_hits_async"):
                final = checked(await owner.validate_hits_async(final))
            final = final[:top_k]
        except Exception:
            return ToolResult(success=False, data=[], tool_name=tool_name,
                              error="RAG evidence validation failed", error_code="degraded",
                              error_type="retrieval", retrieval_status=RetrievalStatus.DEGRADED.value,
                              reranked=outcome.reranked, rerank_status=outcome.status)
        citations = [item["citation"] for item in final]
        return ToolResult(success=True, data=final, tool_name=tool_name,
                          reranked=outcome.reranked, rerank_status=outcome.status,
                          retrieval_status=(RetrievalStatus.USABLE if final else RetrievalStatus.NO_ANSWER).value,
                          citations=citations)

    # ── 结果重排 ──────────────────────────────────────────────────────────────

    async def _rerank(self, query: str, items: List[Any], top_k: int) -> RerankResult:
        """A complete permutation, not a relevance filter. [] is invalid for candidates."""
        if len(items) <= top_k:
            return RerankResult(items[:top_k], False, "not_needed")
        items_text = "\n".join(f"{i}. {json.dumps(item, ensure_ascii=False)[:200]}"
                               for i, item in enumerate(items))
        prompt = f"""根据用户查询，将以下检索候选按相关性降序排列，返回 JSON 索引数组。
用户查询: "{query}"
检索候选:
{items_text}
返回格式: [最相关的索引, ..., 最不相关的索引]。
必须包含全部候选编号且各出现一次，不得省略、重复或使用未知编号。
这是排序任务，不负责判定无答案；有候选时空数组不是有效排序。
只返回 JSON 数组，不要其他文字。"""
        prompt = self._clean_text(prompt)
        tool = self._tools.get("knowledge_search")
        timeout_s = tool.timeout_s if tool else 30.0
        try:
            resp = await asyncio.wait_for(self._client.messages.create(
                model=self._model, max_tokens=256, temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            ), timeout=timeout_s)
        except TimeoutError:
            return RerankResult(items[:top_k], False, "timeout_fallback")
        except Exception:
            return RerankResult(items[:top_k], False, "service_error_fallback")
        try:
            order = json.loads(extract_text_content(resp.content).strip())
            if (not isinstance(order, list) or len(order) != len(items)
                    or any(type(i) is not int for i in order)
                    or set(order) != set(range(len(items)))):
                raise ValueError("rerank requires a full permutation of candidate indices")
        except Exception:
            return RerankResult(items[:top_k], False, "invalid_output_fallback")
        return RerankResult([items[i] for i in order][:top_k], True, "ranked")

    # ── 缓存 ──────────────────────────────────────────────────────────────────

    def _cache_key(self, name: str, params: Dict, rerank_top_k: int = 0) -> str:
        payload = {"params": params, "rerank_top_k": rerank_top_k}
        return f"{name}:{hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"

    def _get_cache(self, name: str, params: Dict, rerank_top_k: int = 0) -> Optional[Tuple[Any, bool, str]]:
        key = self._cache_key(name, params, rerank_top_k)
        if key in self._cache:
            entry = self._cache[key]
            data, expire_at, reranked = entry[:3]
            status = entry[3] if len(entry) > 3 else ("ranked" if reranked else "not_requested")
            if time.monotonic() < expire_at:
                return data, reranked, status
            del self._cache[key]
        return None

    def _set_cache(
        self,
        name: str,
        params: Dict,
        data: Any,
        ttl: float,
        rerank_top_k: int = 0,
        reranked: bool = False,
        rerank_status: str = "not_requested",
    ) -> None:
        if len(self._cache) >= 5000:
            # 清掉最旧的 1/4
            for k in list(self._cache)[:1250]:
                del self._cache[k]
        self._cache[self._cache_key(name, params, rerank_top_k)] = (data, time.monotonic() + ttl, reranked, rerank_status)

    # ── 参数校验 ──────────────────────────────────────────────────────────────

    def _validate_params(self, tool: Tool, params: Dict[str, Any]) -> None:
        """Compatibility entry point; Agent and RAG share this validator."""
        validate_tool_input(tool.input_schema, params)

    @staticmethod
    def _clean_text(value: Any) -> str:
        """移除 Unicode 代理字符，避免 LLM 请求编码失败。"""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.encode("utf-8", errors="ignore").decode("utf-8")

    # ── 统计 ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            name: {
                "total": t.stats.total,
                "success_rate": round(t.stats.success_rate, 3),
                "avg_latency_ms": round(t.stats.avg_latency_ms, 1),
                "consecutive_fails": t.stats.consecutive_fails,
                "circuit_state": t.breaker.state.value,
            }
            for name, t in self._tools.items()
        }
