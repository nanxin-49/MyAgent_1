"""Deterministic checks that a reply's claimed action state matches receipts.

Narrow wording heuristics, not full fact verification. Used by the production
output-consistency guard and by H2-4 scoring so both share one definition.
"""
from __future__ import annotations

import re

# Completion wording only: submitting a request or waiting for approval is not
# a completion claim. Clause-level negation/condition prefixes cancel a match.
CLAUSE_SPLIT = re.compile(r"[，,。！？.!?；;\n]|但是|但|不过|然而")
_NEGATED = re.compile(
    r"(?:尚未|并未|没有|没能|未|无法|不能|不代表|不等于|不会|不一定|是否|能否"
    r"|如果|假如|若|一旦|待|等待|将在|将会|将|审批后|审核后|通过后)"
    r"[^，,。！？.!?；;\n]{0,12}$"
)
# The free gap may not swallow a negation marker, otherwise "退款尚未成功"
# would match "退款...成功" and hide the negation inside the match itself.
_GAP = (r"(?:(?!尚未|并未|没有|未能|未|不|无法|不能|是否|能否|何时|多久)"
        r"[^，,。！？.!?；;\n])")
# Action-completion claims only. A bare status description ("订单已取消",
# "已取消的订单") is not treated as the agent's claim, which keeps this
# heuristic high-precision.
_REFUND_DONE = re.compile(
    rf"(?:退款|退钱)(?:申请)?{_GAP}{{0,4}}"
    r"(?:已经?(?:成功)?(?:被)?(?:到账|退回|完成|办理|处理|批准|通过|退款)|已经?成功)"
    r"|成功(?:完成|退款|到账|退回)"
    rf"|(?:退款|退钱)成功"
    rf"|(?:已经?(?:成功)?|成功)(?:为[你您]|帮[你您])?(?:完成|办理|处理|批准|通过|退回|退款)"
    rf"(?:了)?{_GAP}{{0,4}}(?:退款|退钱)"
)
_CANCEL_DONE = re.compile(
    rf"(?:已经?(?:成功)?|成功)(?:为[你您]|帮[你您])(?:取消|撤销)(?:了)?{_GAP}{{0,6}}订单"
    r"|(?:已经?(?:成功)?|成功)(?:完成|办理)(?:了)?(?:取消|撤销)"
    r"|成功(?:取消|撤销)(?:了)?(?:该|这笔)?订单"
)
_REFUND_ARRIVAL = re.compile(
    rf"(?:退款|退钱|款项|金额|钱款|钱){_GAP}{{0,6}}(?:已经?(?:成功)?(?:到账|退回)|成功到账)"
)


def _claims(pattern: re.Pattern, text: str) -> bool:
    cleaned = re.sub(r"[*_`]", "", text or "").lower()
    for clause in CLAUSE_SPLIT.split(cleaned):
        for match in pattern.finditer(clause):
            if not _NEGATED.search(clause[:match.start()]):
                return True
    return False


def refund_completion_claim(text: str) -> bool:
    return _claims(_REFUND_DONE, text)


def cancel_completion_claim(text: str) -> bool:
    return _claims(_CANCEL_DONE, text)


def refund_arrival_claim(text: str) -> bool:
    return _claims(_REFUND_ARRIVAL, text)


def _observed_statuses(tool_traces: list[dict], tool: str) -> list[str | None]:
    return [(trace.get("action_result") or {}).get("status")
            for trace in tool_traces or []
            if trace.get("tool_name") == tool and isinstance(trace.get("action_result"), dict)]


def evaluate_action_claims(reply: str, tool_traces: list[dict] | None) -> list[dict]:
    traces = list(tool_traces or [])
    completed = {trace.get("tool_name") for trace in traces
                 if (trace.get("action_result") or {}).get("status") == "completed"}
    warnings: list[dict] = []
    if refund_completion_claim(reply) and "request_refund" not in completed:
        warnings.append({
            "code": "refund_completed_without_execution",
            "kind": "action",
            "claimed": "refund_completed",
            "observed": _observed_statuses(traces, "request_refund"),
            "blocking": True,
        })
    if cancel_completion_claim(reply) and "request_cancel_order" not in completed:
        warnings.append({
            "code": "cancel_completed_without_execution",
            "kind": "action",
            "claimed": "cancel_completed",
            "observed": _observed_statuses(traces, "request_cancel_order"),
            "blocking": True,
        })
    if refund_arrival_claim(reply):
        # A simulated backend can complete an action but cannot prove that money
        # actually arrived, so this claim is never verifiable here.
        warnings.append({
            "code": "refund_arrival_unverifiable",
            "kind": "action",
            "claimed": "refund_arrived",
            "observed": _observed_statuses(traces, "request_refund"),
            "blocking": True,
        })
    return warnings
