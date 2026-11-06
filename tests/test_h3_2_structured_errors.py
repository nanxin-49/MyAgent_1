"""H3-2: structured tool errors, result truncation, fault-recovery comparison."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import make_tool
from core.harness import HarnessConfig
from core.tool_contract import (ToolExecutionResult, suggested_action_for,
                                truncate_tool_payload)
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel, script_from_file
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


# ── suggested action mapping ────────────────────────────────────────────────

@pytest.mark.parametrize("code,action", [
    ("invalid_arguments", "ask_user_for_missing_fields"),
    ("not_found", "ask_user_to_confirm_identifier"),
    ("refund_order_mismatch", "ask_user_to_confirm_identifier"),
    ("timeout", "retry_later"),
    ("dependency_failure", "retry_later"),
    ("service_unavailable", "retry_later"),
    ("unauthorized", "explain_access_limit"),
    ("ownership_mismatch", "explain_access_limit"),
    ("tool_not_allowed", "explain_access_limit"),
    ("refund_window_expired", "explain_policy_and_stop"),
    ("order_status_not_refundable", "explain_policy_and_stop"),
    ("handoff_policy_rejected", "explain_policy_and_stop"),
    ("something_new", "report_error"),
    (None, "report_error"),
])
def test_suggested_action_mapping(code, action):
    assert suggested_action_for(code) == action


def test_structured_payload_adds_fields_without_losing_domain_keys():
    result = ToolExecutionResult(
        False,
        {"success": False, "data": None, "source": "business_provider",
         "error": {"code": "not_found", "message": "未找到可访问的业务记录"}},
        error_code="not_found", error_type="provider", retryable=False)
    payload = result.agent_payload()
    assert payload["error"] == {"code": "not_found", "message": "未找到可访问的业务记录"}
    assert payload["source"] == "business_provider"
    assert payload["error_code"] == "not_found"
    assert payload["error_type"] == "provider"
    assert payload["retryable"] is False
    assert payload["suggested_action"] == "ask_user_to_confirm_identifier"


def test_action_rejection_payload_explains_policy():
    result = ToolExecutionResult(
        False,
        {"success": False, "action_id": "act_1", "status": "rejected",
         "error_code": "refund_window_expired", "action": {"policy_decision": {"decision": "deny"}}},
        error_code="refund_window_expired", error_type="action", retryable=False)
    payload = result.agent_payload()
    assert payload["action_id"] == "act_1"
    assert payload["status"] == "rejected"
    assert payload["suggested_action"] == "explain_policy_and_stop"


def test_timeout_and_validation_hints():
    timeout = ToolExecutionResult(False, error_code="timeout", error_type="timeout",
                                  retryable=True)
    assert timeout.agent_payload()["suggested_action"] == "retry_later"
    assert timeout.agent_payload()["retryable"] is True

    invalid = ToolExecutionResult(False, error_code="invalid_arguments",
                                  error_type="validation", retryable=False)
    assert invalid.agent_payload()["suggested_action"] == "ask_user_for_missing_fields"


# ── truncation ──────────────────────────────────────────────────────────────

def test_long_payload_is_truncated_marked_and_bounded():
    payload = {"success": True, "status": "shipped",
               "results": [{"content": "x" * 20000}], "citations": [{"id": "c1"}]}
    result = truncate_tool_payload(payload, 2000)
    assert result["truncated"] is True
    assert result["original_chars"] > 20000
    assert result["success"] is True and result["status"] == "shipped"
    assert len(json.dumps(result, ensure_ascii=False)) <= 2000


def test_short_payload_is_returned_unchanged():
    payload = {"success": True, "data": {"order_id": "ORD-1"}}
    assert truncate_tool_payload(payload, 8000) == payload
    assert "truncated" not in truncate_tool_payload(payload, 8000)


# ── model-visible error feedback ────────────────────────────────────────────

def _runtime(script, harness, tools=None):
    model = ScriptedModel(script)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    if tools is None:
        tools, _, _ = isolated_business(prepare(NOW)[0], NOW)
    runtime.set_shared_tools(tools)
    return runtime, model


def _request(message="查订单 ORD-MISSING", conv="h32"):
    principal = customer("customer-1")
    return Request(message, principal.customer_id, conv, principal=principal)


def test_error_feedback_on_exposes_structured_fields():
    turns = script_from_file("evaluation/scripts/error_feedback_not_found.json")._turns
    runtime, model = _runtime(turns, HarnessConfig())
    asyncio.run(runtime.run(_request()))
    payload = json.loads(model.calls[1]["messages"][-1]["content"][0]["content"])
    assert payload["error_code"] == "not_found"
    assert payload["suggested_action"] == "ask_user_to_confirm_identifier"
    assert "retryable" in payload


def test_error_feedback_off_still_hides_everything():
    turns = script_from_file("evaluation/scripts/error_feedback_not_found.json")._turns
    runtime, model = _runtime(turns, HarnessConfig.evaluation(error_feedback=False))
    asyncio.run(runtime.run(_request()))
    payload = json.loads(model.calls[1]["messages"][-1]["content"][0]["content"])
    assert payload == {"success": True, "acknowledged": True}


def test_trace_marks_truncated_tool_result():
    def huge(req, args):
        return {"success": True, "data": {"blob": "x" * 20000}}

    tools = {"huge": make_tool("huge", "大结果", {}, huge)}
    script = [{"tool_calls": [{"name": "huge", "input": {}}]}, {"text": "完成。"}]
    runtime, model = _runtime(script, HarnessConfig(max_tool_result_chars=2000), tools)
    result = asyncio.run(runtime.run(_request("调用大结果工具")))
    payload = json.loads(model.calls[1]["messages"][-1]["content"][0]["content"])
    assert payload["truncated"] is True
    assert len(json.dumps(payload, ensure_ascii=False)) <= 2000
    assert result.tool_traces[0]["truncated"] is True


# ── fault recovery comparison ───────────────────────────────────────────────

def test_recovery_comparison_prefers_error_feedback():
    from evaluation.h3_2.run_recovery import evaluate

    report = evaluate()
    arms = report["arms"]
    assert arms["on"]["recovery_rate"] == 1.0
    assert arms["off"]["recovery_rate"] == 0.0
    assert arms["off"]["executed_violations"] == 0
    assert len(arms["on"]["cases"]) == 5
