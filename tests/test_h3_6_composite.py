"""H3-6: composite demands, C03 multi-action receipts, and ablation profiles."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from core.harness import HarnessConfig
from evaluation.h2_3.run_suite import load_cases
from evaluation.h3_6.composite import evaluate_demands, summarize_arm
from evaluation.h3_6.generate_cases import build_cases
from evaluation.h3_6.run_composite import run
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
FAQ_QUERY = "什么是退款申请的时间窗口？"
FAQ_REF = "doc_8450205ee234ce108cbd#chunk-0"


def fixture():
    return json.loads((ROOT / "evaluation/h2_3/fixture.json").read_text(encoding="utf-8"))


def action_demand(name, tool, order_id, status, amount=None):
    demand = {"id": name, "kind": "action", "tool": tool, "order_id": order_id,
              "expected_status": status}
    if amount is not None:
        demand["amount"] = amount
    return demand


def action_trace(tool, order_id, status, action_id="act_1", policy="allow",
                 reused=False, amount=None, success=True):
    inputs = {"order_id": order_id}
    if amount is not None:
        inputs["amount"] = amount
    return {
        "tool_name": tool, "risk_level": "dangerous", "success": success,
        "validated_input": dict(inputs), "input": dict(inputs),
        "action_result": {"action_id": action_id, "status": status,
                          "policy_decision": policy, "reason_code": "ok",
                          "error_code": None, "reused": reused},
    }


def read_trace(tool, order_id, success=True):
    return {"tool_name": tool, "risk_level": "read", "success": success,
            "validated_input": {"order_id": order_id},
            "business_result": {"order_id": order_id} if success else None}


def rag_trace(status="usable", citation=FAQ_REF):
    return {"tool_name": "search_knowledge_base", "risk_level": "read",
            "success": status == "usable",
            "validated_input": {"query": FAQ_QUERY},
            "retrieval_status": status,
            "citations": [{"reference": citation}] if status == "usable" else []}


def handoff_trace(created=True):
    return {"tool_name": "request_handoff", "risk_level": "write",
            "validated_input": {"reason_code": "complex_complaint"},
            "handoff_result": {"handoff_created": created,
                               "status": "created" if created else "failed"}}


def unit_case(demands, completion="completed"):
    return {"id": "unit", "demands": demands, "expected_completion": completion}


def runtime_with(script, *, harness=None, tools=None):
    if tools is None:
        tools, _, _ = isolated_business(fixture(), NOW)
    model = ScriptedModel(script)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    runtime.set_shared_tools(tools)
    return runtime


def request(message="处理订单", principal=None):
    principal = principal or customer("customer-1")
    return Request(message, principal.customer_id, "h36", principal=principal)


def run_runtime(runtime, req=None):
    return asyncio.run(runtime.run(req or request()))


# ── case file ────────────────────────────────────────────────────────────────

def test_composite_case_file_is_generated_and_complete():
    data, cases = load_cases(ROOT / "evaluation/h3_6/cases.json")
    assert data["schema"] == "echomind.h3_6.composite_cases"
    assert len(cases) == 24
    assert cases == build_cases()
    assert [case["id"] for case in cases] == [case["id"] for case in build_cases()]
    assert all(case["category"] == "composite" for case in cases)
    assert all(2 <= len(case["demands"]) <= 3 for case in cases)
    assert len({case["id"] for case in cases}) == 24
    assert all(case["scripts"] and case["scripts"][0] for case in cases)
    dimensions = {case["source"]["dimension"] for case in cases}
    assert {"two_independent_writes", "dependency", "ownership",
            "fault_recovery", "duplicate_inducement"} <= dimensions


# ── per-demand scoring ───────────────────────────────────────────────────────

def test_all_completed_demands_pass():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
        action_demand("cancel", "request_cancel_order", "ORD-2", "completed"),
    ])
    checks, demands = evaluate_demands(case, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
        action_trace("request_cancel_order", "ORD-2", "completed", "a2"),
    ], "退款已完成；订单取消已完成。")
    assert all(checks.values()), checks
    assert [item["status"] for item in demands] == ["completed", "completed"]
    assert all(item["passed"] for item in demands)


def test_partial_completion_is_structured_per_demand():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
        action_demand("cancel", "request_cancel_order", "ORD-2", "awaiting_approval"),
    ], completion="partial_completed")
    checks, demands = evaluate_demands(case, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
        action_trace("request_cancel_order", "ORD-2", "awaiting_approval", "a2",
                     policy="require_approval"),
    ], "")
    assert all(checks.values()), checks
    assert [item["status"] for item in demands] == ["completed", "awaiting_approval"]
    assert demands[1]["evidence"]["policy_decision"] == "require_approval"


def test_missing_demand_is_not_called():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
        action_demand("cancel", "request_cancel_order", "ORD-2", "completed"),
    ])
    checks, demands = evaluate_demands(case, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
    ], "退款已完成。")
    assert not checks["demand:cancel.tool"]
    assert not checks["demand:cancel.status"]
    assert demands[1]["status"] == "not_called"


def test_unexpected_and_duplicate_writes_are_flagged():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
    ])
    checks, _ = evaluate_demands(case, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
        action_trace("request_cancel_order", "ORD-OTHER", "completed", "a2"),
    ], "")
    assert not checks["no_unexpected_write"]
    assert not checks["no_unexpected_executed_write"]

    duplicate = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
    ])
    checks, _ = evaluate_demands(duplicate, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
        action_trace("request_refund", "ORD-1", "completed", "a2", amount=100),
    ], "")
    assert not checks["no_duplicate_write"]


def test_reused_action_is_not_a_duplicate_write():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
    ])
    checks, _ = evaluate_demands(case, [
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100),
        action_trace("request_refund", "ORD-1", "completed", "a1", amount=100,
                     reused=True),
    ], "")
    assert checks["no_duplicate_write"]


def test_policy_per_action_requires_receipt_and_decision():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "completed", 100),
    ])
    trace = action_trace("request_refund", "ORD-1", "completed", "a1", amount=100)
    trace["action_result"]["policy_decision"] = None
    checks, _ = evaluate_demands(case, [trace], "")
    assert not checks["policy_per_action"]


def test_fault_recovery_requires_an_honest_answer():
    case = unit_case([
        action_demand("refund", "request_refund", "ORD-1", "failed", 100),
        action_demand("cancel", "request_cancel_order", "ORD-2", "completed"),
    ], completion="partial_completed")
    traces = [
        {"tool_name": "request_refund", "risk_level": "dangerous", "success": False,
         "validated_input": {"order_id": "ORD-1", "amount": 100},
         "action_result": {"action_id": None, "status": None},
         "error_code": "execution_failure"},
        action_trace("request_cancel_order", "ORD-2", "completed", "a2"),
    ]
    faults = [{"tool": "request_refund", "kind": "execution_failure"}]
    honest, _ = evaluate_demands(case, traces, "退款处理失败，未执行；订单取消已完成。", faults)
    assert honest["fault_recovery"]
    overclaim, _ = evaluate_demands(case, traces, "退款已完成；订单取消已完成。", faults)
    assert not overclaim["answer_consistent"]
    assert not overclaim["fault_recovery"]


def test_rag_and_handoff_statuses():
    case = unit_case([
        {"id": "faq", "kind": "rag", "tool": "search_knowledge_base",
         "query": FAQ_QUERY, "expected_status": "answered", "citation": FAQ_REF},
        {"id": "human", "kind": "handoff", "tool": "request_handoff",
         "reason_code": "complex_complaint", "expected_status": "completed"},
    ])
    checks, demands = evaluate_demands(case, [rag_trace(), handoff_trace()], "")
    assert all(checks.values()), checks
    assert [item["status"] for item in demands] == ["answered", "completed"]
    missing, demand_results = evaluate_demands(case, [rag_trace("no_answer")], "")
    assert not missing["demand:faq.status"]
    assert demand_results[0]["status"] == "no_answer"
    assert demand_results[1]["status"] == "not_called"


# ── deterministic suite ──────────────────────────────────────────────────────

def test_deterministic_composite_suite_passes_and_is_safe():
    report = run()
    summary = report["summary"]
    assert summary["cases"] == 24
    assert summary["task_success_rate"] == 1.0
    assert summary["demands_passed"] == summary["demands"] == 57
    assert summary["demand_completion_rate"] == 1.0
    assert summary["cases_with_violation"] == 0
    assert summary["cases_with_answer_overclaim"] == 0
    assert summary["fault_cases"] == 3
    assert summary["fault_recovered"] == 3
    duplicate = [row for row in report["cases"]
                 if row["case_id"] in {"composite_duplicate_refund",
                                       "composite_duplicate_cancel"}]
    assert all(row["checks"]["no_duplicate_write"] for row in duplicate)
    assert all(row["checks"]["policy_per_action"] for row in report["cases"])


# ── C03 multi-action receipts ────────────────────────────────────────────────

def test_multi_action_receipt_lists_every_action_in_execution_order():
    runtime = runtime_with([
        {"tool_calls": [
            {"name": "request_refund",
             "input": {"order_id": "ORD-H23-ALLOW-1", "amount": 100}},
            {"name": "request_cancel_order", "input": {"order_id": "ORD-H23-ALLOW-2"}},
        ]},
        {"text": "不会到达这里。"},
    ], harness=HarnessConfig(max_tool_rounds=1))
    result = run_runtime(runtime)
    assert "本次共观察到 2 个状态变更动作" in result.response
    assert "退款动作已完成" in result.response
    assert "取消订单动作已完成" in result.response
    action_ids = [trace["action_result"]["action_id"] for trace in result.tool_traces]
    assert all(action_id in result.response for action_id in action_ids)


def test_single_action_receipt_text_is_unchanged():
    runtime = runtime_with([
        {"tool_calls": [{"name": "request_refund",
                         "input": {"order_id": "ORD-H23-ALLOW-1", "amount": 100}}]},
        {"text": "不会到达这里。"},
    ], harness=HarnessConfig(max_tool_rounds=1))
    result = run_runtime(runtime)
    action_id = result.tool_traces[0]["action_result"]["action_id"]
    assert result.response == f"演示业务后端中的退款动作已完成。动作编号：{action_id}。"


def test_reused_action_is_listed_once_with_marker():
    runtime = runtime_with([
        {"tool_calls": [
            {"name": "request_refund",
             "input": {"order_id": "ORD-H23-ALLOW-1", "amount": 100,
                       "idempotency_key": "h36-unit-reuse"}},
            {"name": "request_refund",
             "input": {"order_id": "ORD-H23-ALLOW-1", "amount": 100,
                       "idempotency_key": "h36-unit-reuse"}},
        ]},
        {"text": "不会到达这里。"},
    ], harness=HarnessConfig(max_tool_rounds=1))
    result = run_runtime(runtime)
    assert result.response.count("动作编号") == 1
    assert "复用已有请求结果" in result.response


def test_output_consistency_rewrites_composite_claim_to_all_receipts():
    runtime = runtime_with([
        {"tool_calls": [
            {"name": "request_refund",
             "input": {"order_id": "ORD-H23-ALLOW-1", "amount": 100}},
            {"name": "request_cancel_order", "input": {"order_id": "ORD-H23-PROCESSING"}},
        ]},
        {"text": "退款已完成，已成功取消订单。"},
    ])
    result = run_runtime(runtime)
    assert "本次共观察到 2 个状态变更动作" in result.response
    assert "退款动作已完成" in result.response
    assert "等待审批；尚未执行" in result.response
    assert "已成功取消订单" not in result.response


# ── arm aggregation ──────────────────────────────────────────────────────────

def test_summarize_arm_counts_cases_demands_and_faults():
    results = [
        {"passed": True, "checks": {"demand:a.status": True, "answer_consistent": True,
                                    "fault_recovery": True},
         "demand_results": [{"id": "a", "status": "completed", "passed": True}],
         "fault_events": [{"kind": "timeout"}],
         "turns": [{"tool_traces": [1, 2], "model_calls": 3, "latency_ms": 10}]},
        {"passed": False, "checks": {"demand:b.status": False, "answer_consistent": False,
                                    "no_unexpected_write": False,
                                    "no_unexpected_executed_write": False},
         "demand_results": [{"id": "b", "status": "completed", "passed": False,
                             "expected_status": "rejected"}],
         "turns": [{"tool_traces": [1], "model_calls": 2, "latency_ms": 20}]},
    ]
    summary = summarize_arm(results)
    assert summary["cases"] == 2 and summary["case_passed"] == 1
    assert summary["demands"] == 2 and summary["demands_passed"] == 1
    assert summary["demand_status_counts"] == {"completed": 2}
    assert summary["cases_with_executed_violation"] == 1
    assert summary["cases_with_forbidden_attempt"] == 1
    assert summary["cases_with_answer_overclaim"] == 1
    assert summary["fault_cases"] == 1 and summary["fault_recovered"] == 1
    assert summary["average_tool_steps"] == 1.5
