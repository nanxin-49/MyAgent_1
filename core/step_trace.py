"""Per-step trace summaries for the Agent tool loop.

One step is one Agent model call. Tool calls are attached to the step that
selected them, so a request can be replayed as:

    model step (tokens, latency) -> selected tools (params, result summary)
    -> next model step -> ... -> stop_reason

Only already-recorded facts are summarized. Prompts, model text, hidden
reasoning, raw memory content, and full tool payloads are never copied here.
"""
from typing import Any, Dict, Optional

MAX_PARAMETER_FIELDS = 12
MAX_PARAMETER_CHARS = 120


def _summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= MAX_PARAMETER_CHARS else (
            value[:MAX_PARAMETER_CHARS] + "…")
    if isinstance(value, (list, tuple)):
        return {"type": "list", "count": len(value)}
    if isinstance(value, dict):
        return {"type": "object",
                "keys": sorted(str(key) for key in value)[:MAX_PARAMETER_FIELDS]}
    return {"type": type(value).__name__}


def summarize_parameters(input_value: Any) -> Dict[str, Any]:
    """Compact, bounded view of model-selected tool parameters."""
    if not isinstance(input_value, dict):
        return {"value_type": type(input_value).__name__}
    summary: Dict[str, Any] = {}
    for key, value in list(input_value.items())[:MAX_PARAMETER_FIELDS]:
        summary[str(key)] = _summarize_value(value)
    if len(input_value) > MAX_PARAMETER_FIELDS:
        summary["_omitted_fields"] = len(input_value) - MAX_PARAMETER_FIELDS
    return summary


def _result_summary(trace: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "success": trace.get("success"),
        "result_success": trace.get("result_success"),
        "error_code": trace.get("error_code"),
        "truncated": bool(trace.get("truncated")),
    }
    action = trace.get("action_result")
    if isinstance(action, dict) and action.get("status"):
        summary["action_status"] = action["status"]
    handoff = trace.get("handoff_result")
    if isinstance(handoff, dict):
        if handoff.get("status"):
            summary["handoff_status"] = handoff["status"]
        if "handoff_created" in handoff:
            summary["handoff_created"] = bool(handoff.get("handoff_created"))
    if trace.get("retrieval_status"):
        summary["retrieval_status"] = trace["retrieval_status"]
    citations = trace.get("citations")
    if isinstance(citations, list) and citations:
        summary["citation_count"] = len(citations)
    hits = trace.get("retrieval_hits")
    if isinstance(hits, list):
        summary["retrieval_hit_count"] = len(hits)
    business = trace.get("business_result")
    if isinstance(business, dict) and business:
        summary["business_fields"] = sorted(business)
    return summary


def summarize_tool_trace(trace: Dict[str, Any], *, aux_model_calls: int = 0) -> Dict[str, Any]:
    """Summarize one existing tool trace for the step that selected it.

    ``aux_model_calls`` counts tool-internal SDK calls (for example RAG rewrite
    or rerank); their details stay in the request-level ``model_calls`` ledger.
    """
    return {
        "tool_name": trace.get("tool_name"),
        "risk_level": trace.get("risk_level"),
        "parameter_summary": summarize_parameters(trace.get("input")),
        "result_summary": _result_summary(trace),
        "success": trace.get("success"),
        "error_code": trace.get("error_code"),
        "error_type": trace.get("error_type"),
        "retryable": trace.get("retryable"),
        "latency_ms": trace.get("latency_ms"),
        "attempts": trace.get("attempts"),
        "aux_model_calls": max(0, int(aux_model_calls or 0)),
    }


def new_model_step(step: int, *, model: Optional[str] = None,
                   input_tokens: Optional[int] = None,
                   output_tokens: Optional[int] = None,
                   latency_ms: float = 0.0) -> Dict[str, Any]:
    return {
        "step": step,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "tools": [],
        "stop_reason": None,
    }
