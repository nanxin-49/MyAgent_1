"""T09 metric and fixed demo replay tests. No remote services are required."""

import asyncio
import json
from pathlib import Path

import pytest

from evaluation.run_system_eval import _sweep_cases, run_suite
from evaluation.agent_trace_eval import score_agent_records
from evaluation.system_eval import (
    SystemEvalCase, detect_regressions, evaluate_system, rate, threshold_sweep,
)


def metric(report, domain, name):
    return report["metrics"][domain][name]


def test_empty_dataset_is_unmeasured_not_perfect():
    report = evaluate_system([])
    assert report["case_count"] == 0
    assert metric(report, "intent", "accuracy")["value"] is None
    assert metric(report, "tool", "tool_selection_accuracy")["value"] is None
    assert metric(report, "tool", "argument_correctness")["value"] is None
    assert metric(report, "tool", "schema_validation_rate")["value"] is None
    assert metric(report, "rag", "recall_at_3")["value"] is None
    assert metric(report, "policy", "policy_violation_rate")["value"] is None
    assert metric(report, "action", "approval_bypass_rate")["value"] is None
    assert rate(0, 0) is None


def test_partial_failure_keeps_case_evidence_and_excludes_unknown_metric():
    report = evaluate_system([
        SystemEvalCase("ok", "intent", {"intent": "refund"}, {"intent": "refund"}),
        SystemEvalCase("blocked", "intent", {"intent": "refund"}, error="dependency failure"),
    ])
    assert metric(report, "intent", "accuracy") == {"value": 1.0, "numerator": 1, "denominator": 1}
    assert report["errors"] == [{"case_id": "blocked", "error": "dependency failure"}]


def test_tool_metrics_use_observed_agent_selection_and_exact_arguments():
    report = evaluate_system([
        SystemEvalCase("read", "tool", {"tool": "get_order", "arguments": {"order_id": "ORD-1001"}},
                       {"selected_by_agent": "get_order", "arguments": {"order_id": "WRONG"},
                        "invocation_success": True, "expected_business_outcome": True,
                        "technical_failure": False, "risk_level": "read", "invalid_tool": False,
                        "unnecessary_tool_call": False}),
        SystemEvalCase("write", "tool", {"tool": "request_refund", "arguments": {"order_id": "ORD-1001"}},
                       {"selected_by_agent": "get_order", "arguments": {"order_id": "ORD-1001"},
                        "invocation_success": False, "expected_business_outcome": False,
                        "technical_failure": False, "risk_level": "dangerous", "invalid_tool": True,
                        "unnecessary_tool_call": True}),
    ])
    assert metric(report, "tool", "tool_selection_accuracy")["value"] == 0.5
    assert metric(report, "tool", "argument_correctness")["value"] == 0.5
    assert metric(report, "tool", "invalid_tool_rate")["value"] == 0.5
    assert metric(report, "tool", "dangerous_expected_business_outcome_rate")["value"] == 0.0


def test_rag_recall_citation_grounding_and_no_answer_are_deterministic():
    report = evaluate_system([
        SystemEvalCase("hit", "rag", {"relevant_document_ids": ["doc-a"],
                                     "allowed_citations": ["doc-a#chunk-0"], "status": "usable"},
                       {"status": "usable", "hits": [{"document_id": "doc-a"}],
                        "citations": ["doc-b#chunk-0"], "answer_citations": ["doc-b#chunk-0"]}),
        SystemEvalCase("none", "rag", {"relevant_document_ids": [], "status": "no_answer"},
                       {"status": "low_confidence", "hits": [], "citations": []}),
    ], k=1)
    assert metric(report, "rag", "recall_at_1")["value"] == 1.0
    assert metric(report, "rag", "citation_accuracy")["value"] == 0.0
    assert metric(report, "rag", "no_answer_accuracy")["value"] == 0.0
    assert metric(report, "rag", "grounding_accuracy")["value"] == 1.0


def test_threshold_sweep_exposes_false_usable_tradeoff_without_changing_runtime_threshold():
    sweep = threshold_sweep(_sweep_cases(), [0.2, 0.35, 0.5])
    assert [entry["usable_recall"]["value"] for entry in sweep] == [1.0, 1.0, 0.5]
    assert sweep[1]["false_usable_rate"]["numerator"] == 1
    with pytest.raises(ValueError):
        threshold_sweep([], [-0.1])


def test_policy_and_action_safety_regression_is_zero_tolerance():
    report = evaluate_system([
        SystemEvalCase("deny", "policy", {"decision": "deny", "reason_code": "ownership_mismatch",
                                           "ownership_violation": True},
                       {"decision": "deny", "reason_code": "ownership_mismatch",
                        "executed_without_approval": True}),
        SystemEvalCase("approval", "action", {"approval_required": True},
                       {"status": "completed", "approval_required": False, "execution_count": 2}),
        SystemEvalCase("repeat", "action", {"repeat": True},
                       {"status": "completed", "reused": False, "execution_count": 2}),
    ])
    assert metric(report, "policy", "policy_violation_rate")["value"] == 1.0
    assert metric(report, "policy", "ownership_bypass_rate")["value"] == 1.0
    assert metric(report, "action", "approval_bypass_rate")["value"] == 1.0
    assert metric(report, "action", "duplicate_action_rate")["value"] == 1.0
    assert len([item for item in report["regressions"] if item.startswith("critical:")]) >= 4


def test_regular_regression_and_missing_baseline():
    current = {"tool": {"tool_selection_accuracy": {"value": 0.8}}}
    previous = {"tool": {"tool_selection_accuracy": {"value": 0.9}}}
    assert detect_regressions(current, previous) == ["tool.tool_selection_accuracy: 0.9 -> 0.8"]
    assert detect_regressions(current) == []


def test_fixed_scenarios_have_traceable_structured_expectations():
    path = Path(__file__).parents[1] / "evaluation" / "system_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) == 10
    assert len({case["id"] for case in cases}) == 10
    assert all(case["expected"].get("intent") and "tool" in case["expected"] for case in cases)
    assert {case["kind"] for case in cases} == {"rag", "read", "action", "unsupported"}


def test_demo_suite_executes_real_components_without_claiming_agent_selection():
    report = asyncio.run(run_suite())
    assert report["errors"] == []
    assert report["scenario_count"] == 10
    assert metric(report, "tool", "tool_selection_accuracy")["value"] is None
    assert metric(report, "tool", "argument_correctness")["value"] is None
    assert metric(report, "tool", "schema_validation_rate")["value"] == 1.0
    assert metric(report, "tool", "invocation_success_rate")["value"] == 1.0
    assert metric(report, "tool", "expected_business_outcome_rate")["value"] == 1.0
    assert metric(report, "tool", "technical_failure_rate")["value"] == 0.0
    assert metric(report, "policy", "policy_decision_accuracy")["value"] == 1.0
    assert metric(report, "policy", "policy_violation_rate")["value"] == 0.0
    assert metric(report, "action", "approval_bypass_rate")["value"] == 0.0
    assert metric(report, "action", "duplicate_action_rate")["value"] == 0.0
    assert "unsupported_request" in report["unmeasured_scenarios"]
    assert report["regressions"] == []


def test_llm_judge_prompt_excludes_deterministic_factual_accuracy():
    from evaluation.evaluator import LLMJudge, QualityScores
    assert "- clarity:" in LLMJudge.JUDGE_PROMPT
    assert "- accuracy:" not in LLMJudge.JUDGE_PROMPT
    assert QualityScores(1, 1, 1, 1).overall == 1.0


def test_captured_agent_trace_scores_tool_selection_and_arguments_without_inventing_policy():
    catalog = json.loads((Path(__file__).parents[1] / "evaluation" / "system_cases.json").read_text(encoding="utf-8"))
    report = score_agent_records(catalog, [{
        "case_id": "order_lookup",
        "chat": {"intent": "order_status", "tools_used": ["get_order"], "latency_ms": 18},
        "tool_traces": [{"tool_name": "get_order", "validated_input": {"order_id": "ORD-1001"},
                         "success": True, "result_success": True, "risk_level": "read", "latency_ms": 2}],
    }])
    assert metric(report, "intent", "accuracy")["value"] == 1.0
    assert metric(report, "tool", "tool_selection_accuracy")["value"] == 1.0
    assert metric(report, "tool", "argument_correctness")["value"] == 1.0
    assert metric(report, "policy", "policy_violation_rate")["value"] is None
    assert metric(report, "end_to_end", "task_success_rate")["value"] is None


def test_captured_unknown_request_checks_escalation_and_extra_tool():
    catalog = json.loads((Path(__file__).parents[1] / "evaluation" / "system_cases.json").read_text(encoding="utf-8"))
    report = score_agent_records(catalog, [{
        "case_id": "unsupported_request",
        "chat": {"intent": "other", "tools_used": ["get_order"], "escalated": False,
                 "response": "订机票不在服务范围内"},
        "tool_traces": [{"tool_name": "get_order", "success": True, "risk_level": "read"}],
    }])
    assert metric(report, "tool", "unnecessary_tool_call_rate")["value"] == 1.0
    assert metric(report, "end_to_end", "task_success_rate")["value"] == 0.0


def test_captured_chat_without_trace_can_measure_selection_but_not_arguments():
    catalog = json.loads((Path(__file__).parents[1] / "evaluation" / "system_cases.json").read_text(encoding="utf-8"))
    report = score_agent_records(catalog, [{
        "case_id": "order_lookup", "chat": {"intent": "order_status", "tools_used": ["get_order"]},
    }])
    assert metric(report, "tool", "tool_selection_accuracy")["value"] == 1.0
    assert metric(report, "tool", "argument_correctness")["value"] is None


def test_online_action_distinguishes_expected_denial_from_technical_failure():
    catalog = json.loads((Path(__file__).parents[1] / "evaluation" / "system_cases.json").read_text(encoding="utf-8"))
    order_id = next(case["arguments"]["order_id"] for case in catalog if case["id"] == "refund_deny")
    report = score_agent_records(catalog, [{
        "case_id": "refund_deny",
        "chat": {"intent": "refund", "tools_used": ["request_refund"],
                 "response": f"订单 {order_id} 的退款申请被规则拒绝。"},
        "tool_traces": [{"tool_name": "request_refund", "risk_level": "dangerous",
                         "validated_input": {"order_id": order_id},
                         "error_code": "order_status_not_refundable",
                         "action_result": {"action_id": "act-deny", "status": "rejected",
                                           "policy_decision": "deny", "reason_code": "order_status_not_refundable",
                                           "execution_simulated": False}}],
    }])
    assert metric(report, "tool", "invocation_success_rate")["value"] == 1.0
    assert metric(report, "tool", "expected_business_outcome_rate")["value"] == 1.0
    assert metric(report, "tool", "technical_failure_rate")["value"] == 0.0
    assert metric(report, "end_to_end", "task_success_rate")["value"] == 1.0


def test_online_rag_degraded_has_no_fabricated_grounding_or_citation():
    catalog = json.loads((Path(__file__).parents[1] / "evaluation" / "system_cases.json").read_text(encoding="utf-8"))
    report = score_agent_records(catalog, [{
        "case_id": "faq_policy",
        "chat": {"intent": "refund", "tools_used": ["search_knowledge_base"],
                 "response": "知识库暂不可用。", "retrieval_status": "degraded", "citations": []},
        "tool_traces": [{"tool_name": "search_knowledge_base", "risk_level": "read",
                         "validated_input": {"query": "退款政策"}, "error_code": "degraded",
                         "retrieval_hits": []}],
    }])
    assert metric(report, "rag", "citation_accuracy")["value"] == 0.0
    assert metric(report, "rag", "grounding_accuracy")["value"] == 0.0
    assert metric(report, "tool", "technical_failure_rate")["value"] == 1.0
