"""H3-1: stop reasons, step/token budgets, duplicate detection, step timeouts."""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import make_tool
from core.harness import HarnessConfig
from core.stop_reason import StopReason
from core.tool_contract import RetryPolicy, RiskLevel
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def fixture():
    return prepare(NOW)[0]


def h23_fixture():
    return json.loads((ROOT / "evaluation/h2_3/fixture.json").read_text(encoding="utf-8"))


def runtime_with(script, *, fixture_data=None, harness=None, tools=None):
    model = ScriptedModel(script)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    if tools is None:
        tools, _, _ = isolated_business(fixture_data or fixture(), NOW)
    runtime.set_shared_tools(tools)
    return runtime, model


def request(message="查订单 ORD-1001", principal=None):
    principal = principal or customer("customer-1")
    return Request(message, principal.customer_id, "h31", principal=principal)


def run(runtime, req=None):
    return asyncio.run(runtime.run(req or request()))


# ── enum and config ─────────────────────────────────────────────────────────

def test_stop_reason_enum_is_exactly_six_values():
    assert {item.value for item in StopReason} == {
        "completed", "needs_clarification", "awaiting_approval",
        "budget_exhausted", "unrecoverable_error", "loop_detected"}


def test_harness_budgets_have_data_backed_defaults():
    config = HarnessConfig()
    assert config.max_tool_steps == 8
    assert config.max_tokens_per_turn == 60000
    assert config.duplicate_call_limit == 3
    assert config.tool_timeout_s == 30.0
    with pytest.raises(ValueError):
        HarnessConfig(max_tool_steps=0)
    with pytest.raises(ValueError):
        HarnessConfig(max_tokens_per_turn=0)
    with pytest.raises(ValueError):
        HarnessConfig(duplicate_call_limit=0)
    assert HarnessConfig.evaluation(max_tool_steps=1).max_tool_steps == 1


# ── completed / clarification / approval ────────────────────────────────────

def test_completed_answer_records_stop_reason_in_trace():
    runtime, _ = runtime_with([{"text": "这是最终回答。"}])
    result = run(runtime)
    assert result.stop_reason == StopReason.COMPLETED.value
    trace = runtime.get_tool_trace(result.request_id)
    assert trace["stop_reason"] == StopReason.COMPLETED.value


def test_clarification_answer_is_classified_without_changing_text():
    answer = "请提供订单号，我帮您查询退款进度。"
    runtime, _ = runtime_with([{"text": answer}])
    result = run(runtime)
    assert result.stop_reason == StopReason.NEEDS_CLARIFICATION.value
    assert result.response == answer


def test_plain_or_policy_answer_is_not_clarification():
    runtime, _ = runtime_with([{"text": "退款政策：7×24 小时内可提交申请。"}])
    assert run(runtime).stop_reason == StopReason.COMPLETED.value
    runtime, _ = runtime_with([{"text": "需要我帮您转接人工吗？"}])
    assert run(runtime).stop_reason == StopReason.COMPLETED.value


def test_pending_approval_sets_stop_reason():
    script = [
        {"tool_calls": [{"name": "request_refund",
                         "input": {"order_id": "ORD-H23-APPROVAL-1", "amount": 800.0}}]},
        {"text": "退款申请已提交，等待审批。"},
    ]
    runtime, _ = runtime_with(script, fixture_data=h23_fixture())
    result = run(runtime, request("为订单 ORD-H23-APPROVAL-1 申请退款 800 元"))
    assert result.stop_reason == StopReason.AWAITING_APPROVAL.value
    assert result.tool_traces[0]["action_result"]["status"] == "awaiting_approval"


# ── budgets ─────────────────────────────────────────────────────────────────

def test_round_budget_stops_with_fixed_message_instead_of_raising():
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}]},
        {"tool_calls": [{"name": "get_shipment", "input": {"order_id": "ORD-1001"}}]},
    ]
    runtime, model = runtime_with(script, harness=HarnessConfig(max_tool_rounds=1))
    result = run(runtime)
    assert result.stop_reason == StopReason.BUDGET_EXHAUSTED.value
    assert "已达到工具调用上限" in result.response
    assert len(model.calls) == 1


def test_step_budget_skips_remaining_calls_in_same_round():
    script = [
        {"tool_calls": [
            {"name": "get_order", "input": {"order_id": "ORD-1001"}},
            {"name": "get_shipment", "input": {"order_id": "ORD-1001"}},
        ]},
        {"text": "不会到达这里。"},
    ]
    runtime, model = runtime_with(script, harness=HarnessConfig(max_tool_steps=1))
    result = run(runtime)
    assert result.stop_reason == StopReason.BUDGET_EXHAUSTED.value
    assert len(model.calls) == 1
    assert result.tools_used == ["get_order"]
    assert any(trace.get("error_code") == "budget_exhausted" for trace in result.tool_traces)


def test_token_budget_stops_before_executing_tools():
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}],
         "usage": {"input_tokens": 1000, "output_tokens": 10}},
        {"text": "不会到达这里。"},
    ]
    runtime, model = runtime_with(script,
                                  harness=HarnessConfig(max_tokens_per_turn=100))
    result = run(runtime)
    assert result.stop_reason == StopReason.BUDGET_EXHAUSTED.value
    assert len(model.calls) == 1
    assert result.tools_used == []


# ── duplicate detection ─────────────────────────────────────────────────────

def test_duplicate_consecutive_call_stops_before_third_execution():
    same = {"name": "get_order", "input": {"order_id": "ORD-1001"}}
    script = [
        {"tool_calls": [dict(same)]},
        {"tool_calls": [dict(same)]},
        {"tool_calls": [dict(same)]},
        {"text": "不会到达这里。"},
    ]
    runtime, model = runtime_with(script)
    result = run(runtime)
    assert result.stop_reason == StopReason.LOOP_DETECTED.value
    assert len(model.calls) == 3
    assert result.tools_used == ["get_order", "get_order"]
    assert any(trace.get("error_code") == "loop_detected" for trace in result.tool_traces)


def test_alternating_calls_do_not_trigger_duplicate_detection():
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"}}]},
        {"tool_calls": [{"name": "get_shipment", "input": {"order_id": "ORD-1001"}}]},
        {"text": "查询完成。"},
    ]
    runtime, _ = runtime_with(script)
    result = run(runtime)
    assert result.stop_reason == StopReason.COMPLETED.value


def test_loop_control_off_disables_step_token_and_duplicate_budgets():
    same = {"name": "get_order", "input": {"order_id": "ORD-1001"}}
    script = [
        {"tool_calls": [dict(same)], "usage": {"input_tokens": 1000}},
        {"tool_calls": [dict(same)]},
        {"tool_calls": [dict(same)]},
        {"text": "三次查询完成。"},
    ]
    config = HarnessConfig.evaluation(loop_control=False, max_tool_steps=1,
                                      max_tokens_per_turn=1, duplicate_call_limit=1)
    runtime, _ = runtime_with(script, harness=config)
    result = run(runtime)
    assert len(result.tools_used) == 3
    assert result.stop_reason == StopReason.COMPLETED.value


def test_unrecoverable_error_sets_stop_reason():
    runtime, _ = runtime_with([{"error": "provider unavailable"}])
    result = run(runtime)
    assert result.stop_reason == StopReason.UNRECOVERABLE_ERROR.value


# ── step timeout ────────────────────────────────────────────────────────────

def test_read_tool_timeout_uses_harness_cap_without_retrying_worker():
    calls = 0

    def slow(req, args):
        nonlocal calls
        calls += 1
        time.sleep(0.02)
        return {"success": True}

    tools = {"slow": make_tool("slow", "慢查询", {}, slow, timeout_s=None,
                               retry_policy=RetryPolicy(max_attempts=2))}
    script = [
        {"tool_calls": [{"name": "slow", "input": {}}]},
        {"text": "查询失败，已停止。"},
    ]
    runtime, _ = runtime_with(script, harness=HarnessConfig(tool_timeout_s=0.001),
                              tools=tools)
    result = run(runtime)
    timeout = [trace for trace in result.tool_traces
               if trace.get("error_code") == "timeout"]
    assert timeout, result.tool_traces
    assert timeout[0]["attempts"] == 1
    assert timeout[0]["timeout_s"] == 0.001
    time.sleep(0.05)
    assert calls == 1


def test_write_tool_is_not_cancelled_by_step_timeout():
    def slow_write(req, args):
        time.sleep(0.02)
        return {"success": True, "written": True}

    tools = {"slow_write": make_tool("slow_write", "慢写", {}, slow_write,
                                     risk_level=RiskLevel.WRITE, timeout_s=None,
                                     idempotent=False)}
    script = [
        {"tool_calls": [{"name": "slow_write", "input": {}}]},
        {"text": "写入完成。"},
    ]
    runtime, _ = runtime_with(script, harness=HarnessConfig(tool_timeout_s=0.001),
                              tools=tools)
    result = run(runtime)
    assert result.tool_traces[0]["success"] is True
    assert result.tool_traces[0]["error_code"] is None
