"""Score captured /chat responses and Tool Traces against T09 case labels.

This adapter only measures fields exposed by the public API. It does not infer
Policy or Action execution from the final natural-language response.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .system_eval import SystemEvalCase, evaluate_system


CASES_PATH = Path(__file__).with_name("system_cases.json")


def _arguments_match(expected: dict[str, Any], actual: dict[str, Any], tool: str | None) -> bool:
    allowed_extra = {"idempotency_key", "amount"} if tool == "request_refund" else (
        {"idempotency_key"} if tool == "request_cancel_order" else set()
    )
    if any(actual.get(key) != value for key, value in expected.items()):
        return False
    return not (set(actual) - set(expected) - allowed_extra)


def score_agent_records(catalog: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    cases = {case["id"]: case for case in catalog}
    rows: list[SystemEvalCase] = []
    for record in records:
        case_id = record["case_id"]
        if case_id not in cases:
            raise ValueError(f"unknown case_id: {case_id}")
        case = cases[case_id]
        expected = case["expected"]
        if record.get("error"):
            rows.append(SystemEvalCase(case_id, "end_to_end", expected, mode="agent_trace",
                                       error=record["error"]))
            continue
        chat = record.get("chat") or {}
        traces = record.get("tool_traces") or []
        response = str(chat.get("response") or "")
        names = [trace.get("tool_name") for trace in traces] if traces else list(chat.get("tools_used") or [])
        expected_tool = expected.get("tool")
        target = next((trace for trace in traces if trace.get("tool_name") == expected_tool), None)
        action = (target or {}).get("action_result") or {}
        business = (target or {}).get("business_result") or {}
        checks: dict[str, bool] = {}
        if "intent" in chat:
            rows.append(SystemEvalCase(case_id, "intent", {"intent": expected["intent"]},
                                       {"intent": chat["intent"]}, mode="agent_trace"))
            checks["intent"] = chat["intent"] == expected["intent"]
        if traces or "tools_used" in chat:
            allowed = set(expected.get("allowed_tools", [expected_tool] if expected_tool else []))
            observed: dict[str, Any] = {"selected_by_agent": names,
                                        "invalid_tool": any(t.get("error_code") in {
                                            "invalid_arguments", "tool_not_found"} for t in traces),
                                        "unnecessary_tool_call": any(name not in allowed for name in names)
                                        or any(names.count(name) > 1 and name in {
                                            "request_refund", "request_cancel_order"} for name in names)}
            checks["tool_selection"] = expected_tool in names if expected_tool else not names
            if target and target.get("validated_input") is not None and "arguments" in case:
                observed["arguments"] = target["validated_input"]
                observed["arguments_match"] = _arguments_match(case["arguments"], target["validated_input"], expected_tool)
                checks["arguments"] = observed["arguments_match"]
            elif "arguments" in case:
                checks["arguments"] = False
            if expected_tool:
                observed["invocation_success"] = bool(target and target.get("validated_input") is not None)
            if target:
                observed["risk_level"] = target.get("risk_level")
                observed["latency_ms"] = target.get("latency_ms")
                observed["technical_failure"] = target.get("error_code") in {
                    "dependency_failure", "timeout", "execution_failure", "service_unavailable", "degraded"
                } or target.get("error_type") in {"timeout", "execution"}
                if case["kind"] == "read" and business:
                    observed["expected_business_outcome"] = business.get(expected["data_field"]) == expected["data_value"]
                    checks["provider_fact"] = observed["expected_business_outcome"]
                elif case["kind"] == "action" and action:
                    observed["expected_business_outcome"] = (
                        action.get("status") == expected["status"]
                        and action.get("policy_decision") == expected.get("policy_decision")
                        and action.get("reason_code") == expected.get("reason_code")
                    )
                elif case["kind"] == "rag" and "retrieval_status" in chat:
                    observed["expected_business_outcome"] = chat["retrieval_status"] == expected["status"]
            rows.append(SystemEvalCase(case_id, "tool", {
                "tool": expected_tool, **({"arguments": case["arguments"]} if "arguments" in case else {}),
            }, observed, mode="agent_trace"))
        if case["kind"] == "rag" and "retrieval_status" in chat:
            citations = [item.get("reference") for item in chat.get("citations", [])]
            hits = [hit for trace in traces if trace.get("tool_name") == "search_knowledge_base"
                    for hit in (trace.get("retrieval_hits") or [])]
            expected_fact = expected.get("expected_fact")
            grounded = (
                expected["citation"] in citations
                and any((hit.get("citation") or {}).get("reference") == expected["citation"]
                        and expected_fact in hit.get("content", "") for hit in hits)
                and expected_fact in response
            ) if expected_fact else expected["citation"] in citations
            rows.append(SystemEvalCase(case_id, "rag", {
                "status": expected["status"], "allowed_citations": [expected["citation"]],
                "relevant_document_ids": [expected["document_id"]],
            }, {"status": chat["retrieval_status"], "citations": citations,
                "hits": hits, "grounding_check": grounded}, mode="agent_trace"))
            checks["retrieval_status"] = chat["retrieval_status"] == expected["status"]
            checks["citation"] = expected["citation"] in citations
            checks["grounding"] = grounded
        elif case["kind"] == "rag":
            checks["retrieval_status"] = False
            checks["citation"] = False
            checks["grounding"] = False
        if case["kind"] == "read" and "provider_fact" not in checks:
            checks["provider_fact"] = False
        if case["kind"] == "action":
            if action:
                checks["action_status"] = action.get("status") == expected["status"]
                checks["policy_decision"] = action.get("policy_decision") == expected.get("policy_decision")
                checks["reason_code"] = action.get("reason_code") == expected.get("reason_code")
                # A completed user-facing answer may identify either the action
                # receipt or the order. The trace remains the source of truth for
                # whether the state change actually happened.
                checks["user_result"] = any(token and token in response for token in (
                    action.get("action_id"), case.get("arguments", {}).get("order_id"),
                ))
                rows.append(SystemEvalCase(case_id, "policy", {
                    "decision": expected.get("policy_decision"), "reason_code": expected.get("reason_code"),
                    "ownership_violation": case_id == "ownership_violation",
                }, {"decision": action.get("policy_decision"), "reason_code": action.get("reason_code"),
                    "executed_without_approval": bool(action.get("execution_simulated")) and
                    action.get("policy_decision") != "allow"}, mode="agent_trace"))
                rows.append(SystemEvalCase(case_id, "action", {
                    "approval_required": expected.get("approval_required"),
                }, {"status": action.get("status"),
                    "approval_required": action.get("status") == "awaiting_approval",
                    "execution_count": 1 if action.get("execution_simulated") else 0}, mode="agent_trace"))
            else:
                checks["action_status"] = False
        if case["kind"] == "unsupported" and "escalated" in chat:
            checks["escalation"] = bool(chat["escalated"]) == expected["escalation"]
            checks["out_of_scope_response"] = any(token in response for token in ("不在", "无法", "不能"))
        if "response" in chat:
            checks["response_completed"] = bool(response) and "抱歉，处理您的请求时出现问题" not in response
            rows.append(SystemEvalCase(case_id, "end_to_end", expected, {"checks": checks,
                **({"escalation": bool(chat["escalated"])}
                   if "escalated" in chat and "escalation" in expected else {}),
                "latency_ms": chat.get("latency_ms")}, mode="agent_trace"))
    report = evaluate_system(rows)
    report["record_count"] = len(records)
    report["limitations"] = [
        "Only captured /chat response and Tool Trace fields were scored",
        "Policy and approval are scored only when an action_result is present in the Tool Trace",
        "Grounding uses exact citation and a labelled fact string; it is not full natural-language entailment",
        "Missing observations remain null and do not count as passed",
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Score captured CartCare /chat and Tool Traces")
    parser.add_argument("--observations", type=Path, required=True,
                        help="JSON array of {case_id, chat, tool_traces} records")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    catalog = json.loads(args.cases.read_text(encoding="utf-8"))
    records = json.loads(args.observations.read_text(encoding="utf-8"))
    report = score_agent_records(catalog, records)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] or report["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
