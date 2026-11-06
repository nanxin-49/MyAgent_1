"""Enumeration of why one agent turn stopped.

Trace-only observability. Stop reasons never drive routing, reply rewriting or
policy decisions; they only explain the outcome of the tool loop.
"""
from __future__ import annotations

import re
from enum import Enum


class StopReason(str, Enum):
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    AWAITING_APPROVAL = "awaiting_approval"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNRECOVERABLE_ERROR = "unrecoverable_error"
    LOOP_DETECTED = "loop_detected"


# Narrow "asks the user for required information" wording. Deliberately does
# not match offers such as "需要我帮您转接人工吗？".
_CLARIFICATION = re.compile(
    r"请(?:您)?(?:提供|告知|补充|确认|说明)"
    r"|需要(?:您|你)(?:提供|确认|补充)"
    r"|麻烦(?:您)?(?:提供|告知|确认)"
)


def classify_answer(answer: str, traces: list[dict] | None = None) -> StopReason:
    """Classify a finished turn from its answer and this turn's tool traces."""
    traces = traces or []
    if any((trace.get("action_result") or {}).get("status") == "awaiting_approval"
           for trace in traces):
        return StopReason.AWAITING_APPROVAL
    has_write = any(trace.get("risk_level") in {"write", "dangerous"} for trace in traces)
    if not has_write and _CLARIFICATION.search(answer or ""):
        return StopReason.NEEDS_CLARIFICATION
    return StopReason.COMPLETED
