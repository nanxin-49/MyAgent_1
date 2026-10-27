"""H3-5: per-step trace with model usage, tool summaries and stop reasons."""
import asyncio
import json
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.usefixtures("authenticated_http")

from fastapi.testclient import TestClient

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from core.harness import HarnessConfig
from core.step_trace import summarize_parameters, summarize_tool_trace
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def fixture():
    return prepare(NOW)[0]


def runtime_with(script, *, harness=None, tools=None):
    model = ScriptedModel(script)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    if tools is None:
        tools, _, _ = isolated_business(fixture(), NOW)
    runtime.set_shared_tools(tools)
    return runtime, model


def request(message="查订单 ORD-1001", *, context="", principal=None):
    principal = principal or customer("customer-1")
    return Request(message, principal.customer_id, "h35", context=context,
                   principal=principal)


def run(runtime, req=None):
    return asyncio.run(runtime.run(req or request()))


def test_each_model_call_records_one_step_with_usage_tools_and_result():
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}],
         "usage": {"input_tokens": 101, "output_tokens": 11}},
        {"tool_calls": [{"name": "get_shipment", "input": {"order_id": "ORD-1001"}}],
         "usage": {"input_tokens": 202, "output_tokens": 22}},
        {"text": "查询完成。", "usage": {"input_tokens": 303, "output_tokens": 33}},
    ]
    runtime, _ = runtime_with(script)
    result = run(runtime)
    trace = runtime.get_tool_trace(result.request_id)

    steps = trace["steps"]
    assert [step["step"] for step in steps] == [1, 2, 3]
    assert [step["input_tokens"] for step in steps] == [101, 202, 303]
    assert [step["output_tokens"] for step in steps] == [11, 22, 33]
    assert all(step["latency_ms"] >= 0 for step in steps)
    assert trace["step_count"] == 3

    assert [tool["tool_name"] for tool in steps[0]["tools"]] == ["get_order"]
    order = steps[0]["tools"][0]
    assert order["parameter_summary"] == {"order_id": "ORD-1001"}
    assert order["result_summary"]["success"] is True
    assert order["latency_ms"] >= 0

    assert [tool["tool_name"] for tool in steps[1]["tools"]] == ["get_shipment"]
    assert steps[0]["stop_reason"] is None
    assert steps[1]["stop_reason"] is None
    assert steps[2]["tools"] == []
    assert steps[2]["stop_reason"] == "completed"
    assert trace["stop_reason"] == "completed"
    assert trace["step_scope"]


def test_round_budget_marks_the_stopping_step():
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}]},
        {"tool_calls": [{"name": "get_shipment", "input": {"order_id": "ORD-1001"}}]},
    ]
    runtime, _ = runtime_with(script, harness=HarnessConfig(max_tool_rounds=1))
    result = run(runtime)
    trace = runtime.get_tool_trace(result.request_id)

    assert len(trace["steps"]) == 1
    assert trace["steps"][0]["stop_reason"] == "budget_exhausted"
    assert trace["stop_reason"] == "budget_exhausted"


def test_duplicate_detection_is_recorded_in_the_stopping_step():
    same = {"name": "get_order", "input": {"order_id": "ORD-1001"}}
    script = [
        {"tool_calls": [dict(same)]},
        {"tool_calls": [dict(same)]},
        {"tool_calls": [dict(same)]},
        {"text": "不会到达这里。"},
    ]
    runtime, _ = runtime_with(script)
    result = run(runtime)
    trace = runtime.get_tool_trace(result.request_id)

    assert len(trace["steps"]) == 3
    skipped = trace["steps"][2]["tools"][0]
    assert skipped["tool_name"] == "get_order"
    assert skipped["error_code"] == "loop_detected"
    assert skipped["attempts"] == 0
    assert trace["steps"][2]["stop_reason"] == "loop_detected"
    assert trace["stop_reason"] == "loop_detected"


def test_parameter_summary_is_bounded_and_typed():
    summary = summarize_parameters({
        "note": "x" * 500, "ids": list(range(20)), "nested": {"a": 1},
        "amount": 12.5, "ok": True, **{f"f{index}": index for index in range(20)},
    })
    assert summary["note"] == "x" * 120 + "…"
    assert summary["ids"] == {"type": "list", "count": 20}
    assert summary["nested"] == {"type": "object", "keys": ["a"]}
    assert summary["amount"] == 12.5 and summary["ok"] is True
    assert summary["_omitted_fields"] > 0
    assert summarize_parameters("raw") == {"value_type": "str"}


def test_tool_summary_keeps_structured_result_facts_not_full_payload():
    trace = {
        "tool_name": "request_refund", "risk_level": "dangerous",
        "input": {"order_id": "ORD-1", "amount": 800.0},
        "success": True, "result_success": True, "error_code": None,
        "error_type": None, "retryable": False, "latency_ms": 2.0, "attempts": 1,
        "truncated": False,
        "action_result": {"action_id": "ACTION-PRIVATE", "status": "awaiting_approval"},
        "handoff_result": None, "retrieval_status": None, "citations": [],
        "retrieval_hits": None, "business_result": None, "helper_result": None,
    }
    summary = summarize_tool_trace(trace)
    assert summary["result_summary"]["action_status"] == "awaiting_approval"
    assert "ACTION-PRIVATE" not in json.dumps(summary)
    assert "ACTION-PRIVATE" not in json.dumps(summary["parameter_summary"])


def test_step_trace_never_stores_prompts_memory_or_model_text():
    runtime, _ = runtime_with([{"text": "PRIVATE_ANSWER"}], tools={})
    result = run(runtime, request("SECRET_USER_MESSAGE",
                                  context="PRIVATE_MEMORY_CONTENT"))
    trace = runtime.get_tool_trace(result.request_id)
    serialized = json.dumps(trace, ensure_ascii=False)
    for secret in ("PRIVATE_MEMORY_CONTENT", "SECRET_USER_MESSAGE", "PRIVATE_ANSWER"):
        assert secret not in serialized
    forbidden = {"prompt", "messages", "system", "reasoning", "thinking", "content", "text"}
    for step in trace["steps"]:
        assert not forbidden & set(step)


def test_deterministic_handoff_has_no_model_step_but_keeps_tool_trace():
    runtime, _ = runtime_with([], tools={})
    result = run(runtime, request("请帮我转人工"))
    trace = runtime.get_tool_trace(result.request_id)

    assert trace["steps"] == [] and trace["step_count"] == 0
    assert trace["tool_calls"][0]["tool_name"] == "request_handoff"
    assert trace["stop_reason"] == "completed"


def test_trace_endpoint_returns_steps_for_request_id_and_keeps_admin_gate(monkeypatch):
    from api import main
    from tests.test_support_production import EmptyMemory

    runtime, _ = runtime_with([
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}],
         "usage": {"input_tokens": 50, "output_tokens": 5}},
        {"text": "已查询。", "usage": {"input_tokens": 60, "output_tokens": 6}},
    ])
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_memory", EmptyMemory())
    admin = TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})
    body = admin.post("/chat", json={"message": "查订单", "user_id": "customer-1"}).json()

    trace = admin.get(f"/trace/tool/{body['request_id']}").json()["trace"]
    assert [step["step"] for step in trace["steps"]] == [1, 2]
    assert trace["steps"][0]["tools"][0]["tool_name"] == "get_order"
    assert trace["steps"][1]["stop_reason"] == "completed"

    anonymous = TestClient(main.app)
    assert anonymous.get(f"/trace/tool/{body['request_id']}").status_code == 401
