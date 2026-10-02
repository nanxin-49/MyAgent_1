"""Shared Tool contract for Agent tools and the local RAG tool manager.

The two callers retain their own orchestration. This module owns input
validation, risk-aware execution, error classification and result fields.
"""

from __future__ import annotations

import asyncio
import inspect
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

    def agent_payload(self) -> Any:
        # Preserve the existing domain payload while adding common failure fields.
        if self.success:
            return self.data
        if isinstance(self.data, dict):
            return self.data
        return {
            "success": False,
            "data": None,
            "error": self.error,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "retryable": self.retryable,
        }


_RETRYABLE_CODES = {"dependency_failure", "timeout", "service_unavailable"}


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


async def execute_tool(contract: Any, params: Any, handler: Callable[[], Any]) -> ToolExecutionResult:
    """Execute a validated call. Automatic retries are restricted to idempotent reads."""
    started = time.monotonic()
    try:
        validated = validate_tool_input(contract.input_schema, params)
    except ToolValidationError as exc:
        return ToolExecutionResult(False, error_code=exc.code, error_type="validation",
                                   error=str(exc), latency_ms=(time.monotonic() - started) * 1000)

    risk = RiskLevel(contract.risk_level)
    retry = contract.retry_policy.max_attempts if risk is RiskLevel.READ and contract.idempotent else 1
    for attempt in range(1, retry + 1):
        try:
            operation = _invoke(handler)
            # A timed-out synchronous write might continue in its worker thread.
            # Never apply executor timeout or retry to state-changing tools.
            if risk is RiskLevel.READ and contract.timeout_s is not None:
                payload = await asyncio.wait_for(operation, timeout=contract.timeout_s)
            else:
                payload = await operation
            if isinstance(payload, dict) and payload.get("success") is False:
                code, category, message, retryable = _failure(payload)
                result = ToolExecutionResult(False, payload, code, category,
                                             retryable and risk is RiskLevel.READ and contract.idempotent,
                                             (time.monotonic() - started) * 1000, message,
                                             attempt, validated)
            else:
                return ToolExecutionResult(True, payload, latency_ms=(time.monotonic() - started) * 1000,
                                           attempts=attempt, validated_input=validated)
        except asyncio.TimeoutError:
            result = ToolExecutionResult(False, error_code="timeout", error_type="timeout",
                                         retryable=contract.idempotent,
                                         latency_ms=(time.monotonic() - started) * 1000,
                                         error="执行超时", attempts=attempt, validated_input=validated)
        except Exception as exc:
            code = str(getattr(exc, "code", "execution_failure"))
            result = ToolExecutionResult(False, error_code=code, error_type="execution",
                                         retryable=code in _RETRYABLE_CODES and risk is RiskLevel.READ and contract.idempotent,
                                         latency_ms=(time.monotonic() - started) * 1000,
                                         error=str(exc), attempts=attempt, validated_input=validated)
        if not result.retryable or attempt == retry:
            return result
    raise AssertionError("unreachable")
