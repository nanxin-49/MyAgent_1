"""Shared Tool contract for Agent tools and the local RAG tool manager.

The two callers retain their own orchestration. This module owns input
validation, risk-aware execution, error classification and result fields.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping


class RiskLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")


class ToolValidationError(ValueError):
    code = "invalid_arguments"


@dataclass(frozen=True)
class ToolExecutionResult:
    success: bool
    data: Any = None
    error_code: str | None = None
    error_type: str | None = None
    retryable: bool = False
    latency_ms: float = 0.0
    error: str | None = None
    attempts: int = 0
    validated_input: dict[str, Any] | None = None
    timeout_s: float | None = None
    suggested_action: str | None = None

    def agent_payload(self) -> Any:
        # Preserve the existing domain payload while adding common failure fields.
        if self.success:
            return self.data
        action = self.suggested_action or suggested_action_for(self.error_code, self.error_type)
        if isinstance(self.data, dict):
            payload = dict(self.data)
            payload.setdefault("error_code", self.error_code)
            payload.setdefault("error_type", self.error_type)
            payload.setdefault("retryable", self.retryable)
            payload.setdefault("suggested_action", action)
            return payload
        return {
            "success": False,
            "data": None,
            "error": self.error,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "retryable": self.retryable,
            "suggested_action": action,
        }


_RETRYABLE_CODES = {"dependency_failure", "timeout", "service_unavailable"}

# Deterministic guidance attached to failures for the model. This is advice,
# never authorization: Policy/HITL still decide every state change.
_SUGGESTED_ACTIONS = {
    "invalid_arguments": "ask_user_for_missing_fields",
    "not_found": "ask_user_to_confirm_identifier",
    "refund_order_mismatch": "ask_user_to_confirm_identifier",
    "timeout": "retry_later",
    "dependency_failure": "retry_later",
    "service_unavailable": "retry_later",
    "rate_limited": "retry_later",
    "unauthorized": "explain_access_limit",
    "ownership_required": "explain_access_limit",
    "ownership_mismatch": "explain_access_limit",
    "refund_ownership_mismatch": "explain_access_limit",
    "permission": "explain_access_limit",
    "tool_not_allowed": "explain_access_limit",
    "refund_window_expired": "explain_policy_and_stop",
    "order_status_not_refundable": "explain_policy_and_stop",
    "refund_already_completed": "explain_policy_and_stop",
    "refund_already_in_progress": "explain_policy_and_stop",
    "amount_exceeds_order_total": "explain_policy_and_stop",
    "invalid_amount": "explain_policy_and_stop",
    "invalid_state_transition": "explain_policy_and_stop",
    "handoff_policy_rejected": "explain_policy_and_stop",
}


def suggested_action_for(error_code: str | None, error_type: str | None = None) -> str:
    """Map a typed error to a stable, model-readable next step."""
    if error_code in _SUGGESTED_ACTIONS:
        return _SUGGESTED_ACTIONS[error_code]
    if error_type == "permission":
        return "explain_access_limit"
    if error_type == "validation":
        return "ask_user_for_missing_fields"
    if error_type == "timeout":
        return "retry_later"
    return "report_error"


def truncate_tool_payload(payload: Any, limit: int) -> Any:
    """Bound the model-visible tool result and mark that it was cut.

    Trace extraction still reads the full payload; only the JSON sent to the
    model is bounded. The result is guaranteed to serialize within ``limit``
    characters.
    """
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return payload
    if not isinstance(payload, dict):
        preview = text[:max(0, limit - 80)]
        return {"success": False, "truncated": True, "original_chars": len(text),
                "preview": preview}
    priority = ("success", "error_code", "error_type", "retryable", "suggested_action",
                "retrieval_status", "answer_guidance", "status", "action_id", "refund_id",
                "source", "data")
    kept: dict[str, Any] = {}
    for key in priority:
        if key in payload:
            kept[key] = payload[key]
    marker = {"truncated": True, "original_chars": len(text)}
    reserve = len(json.dumps({**kept, **marker}, ensure_ascii=False, default=str)) + 8
    if reserve > limit:
        # Even the priority fields do not fit: keep only scalar priorities.
        kept = {key: value for key, value in kept.items()
                if not isinstance(value, (dict, list))}
        reserve = len(json.dumps({**kept, **marker}, ensure_ascii=False, default=str)) + 8
    used = len(json.dumps(kept, ensure_ascii=False, default=str))
    for key, value in payload.items():
        if key in kept:
            continue
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        cost = len(encoded) + len(key) + 4
        if used + cost <= limit - len(json.dumps(marker, ensure_ascii=False)) - 8:
            kept[key] = value
            used += cost
            continue
        room = limit - len(json.dumps(marker, ensure_ascii=False)) - used - len(key) - 8
        if room > 20:
            kept[key] = encoded[:room] + "…"
        break
    kept.update(marker)
    result_text = json.dumps(kept, ensure_ascii=False, default=str)
    # Last resort: drop or shorten non-priority content until it fits exactly.
    while len(result_text) > limit:
        removable = [key for key in kept
                     if key not in priority and key not in marker]
        if removable:
            kept.pop(removable[-1])
        else:
            strings = [(key, value) for key, value in kept.items()
                       if key not in marker and isinstance(value, str) and len(value) > 8]
            if not strings:
                break
            key, value = max(strings, key=lambda item: len(item[1]))
            overflow = len(result_text) - limit + 8
            kept[key] = value[:max(0, len(value) - overflow)] + "…"
        result_text = json.dumps(kept, ensure_ascii=False, default=str)
    return kept


def validate_tool_input(schema: Mapping[str, Any], params: Any) -> dict[str, Any]:
    """Validate the supported JSON Schema subset, without type coercion."""
    if not isinstance(params, dict):
        raise ToolValidationError("工具参数必须是 JSON 对象")
    if schema.get("type") != "object":
        raise ToolValidationError("工具 schema 必须是 object")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ToolValidationError("工具 schema properties 无效")
    for field in schema.get("required", []):
        if field not in params:
            raise ToolValidationError(f"缺少必需参数: {field}")
    unknown = set(params) - set(properties)
    if unknown and schema.get("additionalProperties", False) is False:
        raise ToolValidationError(f"不允许的工具参数: {', '.join(sorted(unknown))}")
    for key, value in params.items():
        if key not in properties:
            continue
        definition = properties[key]
        kind = definition.get("type")
        valid = {
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
            "boolean": lambda x: isinstance(x, bool),
            "array": lambda x: isinstance(x, list),
            "object": lambda x: isinstance(x, dict),
        }
        if kind not in valid or not valid[kind](value):
            raise ToolValidationError(f"参数 {key} 类型错误，期望 {kind}")
        if kind == "string" and len(value) < definition.get("minLength", 0):
            raise ToolValidationError(f"参数 {key} 长度不足")
    return dict(params)


def _failure(payload: Any) -> tuple[str, str, str, bool]:
    if isinstance(payload, dict):
        detail = payload.get("error")
        code = payload.get("error_code") or (detail.get("code") if isinstance(detail, dict) else None)
        code = str(code or "tool_failed")
        message = detail.get("message", code) if isinstance(detail, dict) else str(detail or payload.get("message") or code)
        source = payload.get("source")
        category = "provider" if source == "business_provider" else "action" if "action_id" in payload else "tool"
        return code, category, message, code in _RETRYABLE_CODES
    return "tool_failed", "tool", str(payload), False


async def _invoke(handler: Callable[[], Any]) -> Any:
    if inspect.iscoroutinefunction(handler):
        return await handler()
    result = await asyncio.to_thread(handler)
    if inspect.isawaitable(result):
        return await result
    return result


async def execute_tool(contract: Any, params: Any, handler: Callable[[], Any],
                       *, timeout_s: float | None = None) -> ToolExecutionResult:
    """Execute a validated call. Automatic retries are restricted to idempotent reads.

    ``timeout_s`` is an optional harness-level cap: the effective timeout is the
    smaller of the contract's and this value. Writes never get an executor
    timeout, because a cancelled worker thread may keep running.
    """
    started = time.monotonic()
    try:
        validated = validate_tool_input(contract.input_schema, params)
    except ToolValidationError as exc:
        return ToolExecutionResult(False, error_code=exc.code, error_type="validation",
                                   error=str(exc), latency_ms=(time.monotonic() - started) * 1000,
                                   suggested_action=suggested_action_for(exc.code, "validation"))

    risk = RiskLevel(contract.risk_level)
    effective_timeout = contract.timeout_s
    if timeout_s is not None and (effective_timeout is None or timeout_s < effective_timeout):
        effective_timeout = timeout_s
    retry = contract.retry_policy.max_attempts if risk is RiskLevel.READ and contract.idempotent else 1
    for attempt in range(1, retry + 1):
        try:
            operation = _invoke(handler)
            # A timed-out synchronous write might continue in its worker thread.
            # Never apply executor timeout or retry to state-changing tools.
            if risk is RiskLevel.READ and effective_timeout is not None:
                payload = await asyncio.wait_for(operation, timeout=effective_timeout)
            else:
                payload = await operation
            if isinstance(payload, dict) and payload.get("success") is False:
                code, category, message, retryable = _failure(payload)
                result = ToolExecutionResult(False, payload, code, category,
                                             retryable and risk is RiskLevel.READ and contract.idempotent,
                                             (time.monotonic() - started) * 1000, message,
                                             attempt, validated, effective_timeout,
                                             suggested_action_for(code, category))
            else:
                return ToolExecutionResult(True, payload, latency_ms=(time.monotonic() - started) * 1000,
                                           attempts=attempt, validated_input=validated,
                                           timeout_s=effective_timeout)
        except asyncio.TimeoutError:
            # A timed-out synchronous handler may still be running in its worker
            # thread. Retrying here could overlap workers, so surface the timeout
            # and let the caller/model decide whether to try again later.
            return ToolExecutionResult(False, error_code="timeout", error_type="timeout",
                                       retryable=contract.idempotent,
                                       latency_ms=(time.monotonic() - started) * 1000,
                                       error="执行超时", attempts=attempt, validated_input=validated,
                                       timeout_s=effective_timeout,
                                       suggested_action=suggested_action_for("timeout", "timeout"))
        except Exception as exc:
            code = str(getattr(exc, "code", "execution_failure"))
            result = ToolExecutionResult(False, error_code=code, error_type="execution",
                                         retryable=code in _RETRYABLE_CODES and risk is RiskLevel.READ and contract.idempotent,
                                         latency_ms=(time.monotonic() - started) * 1000,
                                         error=str(exc), attempts=attempt, validated_input=validated,
                                         timeout_s=effective_timeout,
                                         suggested_action=suggested_action_for(code, "execution"))
        if not result.retryable or attempt == retry:
            return result
    raise AssertionError("unreachable")
