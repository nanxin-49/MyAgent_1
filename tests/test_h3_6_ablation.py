"""H3-6: ablation profiles, runner wiring, budget caps, and report helpers."""
import json
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.support_agent import SupportResult
from core.harness import HarnessConfig
from evaluation.h2_3 import real_model
from evaluation.h2_3.run_suite import load_cases
from evaluation.h2_4.profile import PROFILES, harness_for_profile
from evaluation.h3_6 import run_ablation

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


# ── profiles ────────────────────────────────────────────────────────────────

def test_profiles_cover_full_bare_and_four_component_arms():
    assert PROFILES == ("full", "bare", "no_guardrails", "no_error_feedback",
                        "no_context_compression", "no_loop_control")
    assert harness_for_profile("full") is None
    bare = harness_for_profile("bare")
    assert bare.policy_guard is True and bare.output_consistency is False
    guardrails = harness_for_profile("no_guardrails")
    assert guardrails.policy_guard is False and guardrails.output_consistency is False
    assert guardrails.error_feedback is True
    assert harness_for_profile("no_error_feedback").error_feedback is False
    assert harness_for_profile("no_context_compression").context_compression is False
    loop = harness_for_profile("no_loop_control", max_tool_rounds=10)
    assert loop.loop_control is False and loop.tool_round_limit == 10
    assert loop.max_tool_rounds == 3
    assert all(config.mode == "evaluation" for config in (
        bare, guardrails, harness_for_profile("no_error_feedback"),
        harness_for_profile("no_context_compression"), loop))
    with pytest.raises(ValueError):
        harness_for_profile("unknown")


def test_only_full_profile_is_constructible_outside_evaluation():
    with pytest.raises(ValueError):
        HarnessConfig(policy_guard=False)
    with pytest.raises(ValueError):
        HarnessConfig(output_consistency=False)


def test_composite_schema_is_accepted_by_the_shared_loader():
    data, cases = load_cases(ROOT / "evaluation/h3_6/cases.json")
    assert data["schema"] == "echomind.h3_6.composite_cases"
    assert len(cases) == 24


# ── score_case wiring ───────────────────────────────────────────────────────

def _fake_score_case_dependencies(monkeypatch, *, result):
    captured = {}

    class FakeRuntime:
        def __init__(self, *args, client=None, harness=None, **kwargs):
            captured["harness"] = harness
            self.handoff_service = None

        def set_shared_tools(self, tools):
            captured["tools"] = tools

    def fake_isolated(fixture, now, harness=None):
        captured["isolated_harness"] = harness
        service = types.SimpleNamespace(_store=types.SimpleNamespace(_actions={}))
        backend = types.SimpleNamespace(calls=[])
        return {}, service, backend

    monkeypatch.setattr(real_model, "SupportRuntime", FakeRuntime)
    monkeypatch.setattr(real_model, "isolated_business", fake_isolated)
    monkeypatch.setattr(real_model, "build_manager", lambda *args, **kwargs: object())
    monkeypatch.setattr(real_model, "build_shared_rag_tools", lambda manager: {})
    monkeypatch.setattr(real_model, "terminal_state", lambda *args: {})
    monkeypatch.setattr(real_model, "run_turn", lambda *args: result)
    return captured


def test_score_case_uses_composite_scorer_and_forwards_faults(monkeypatch):
    result = SupportResult("r1", "部分完成。", False, 1.0, [], [], [],
                           steps=[], stop_reason="completed")
    captured = _fake_score_case_dependencies(monkeypatch, result=result)
    calls = {}

    def fake_evaluate(case, traces, answer, faults):
        calls.update(case=case, traces=traces, answer=answer, faults=faults)
        return {"demand:refund.status": False}, [
            {"id": "refund", "status": "rejected", "passed": False}]

    monkeypatch.setattr(real_model, "evaluate_demands", fake_evaluate)

    class FakeInjector:
        def __init__(self, faults):
            self.faults = list(faults or [])
            self.events = ([{"kind": self.faults[0]["kind"]}]
                           if self.faults else [])

        def bind(self, name, handler):
            return handler

    monkeypatch.setattr(real_model, "FaultInjector", FakeInjector)
    case = {"id": "composite", "category": "composite", "message": "退款并取消",
            "demands": [{"id": "refund", "kind": "action",
                         "tool": "request_refund", "order_id": "ORD-1",
                         "expected_status": "completed"}],
            "expected_completion": "completed",
            "faults": [{"tool": "request_refund", "kind": "execution_failure"}]}
    report = real_model.score_case(case, {}, api_key="fake", base_url="http://fake",
                                   model="fake", budgeted=None, kb=object(),
                                   harness=harness_for_profile("no_error_feedback"))
    assert calls["case"] is case and calls["answer"] == "部分完成。"
    assert calls["faults"] and calls["faults"][0]["kind"] == "execution_failure"
    assert captured["harness"] is not None
    assert report["checks"] == {"demand:refund.status": False}
    assert report["passed"] is False
    assert report["demand_results"][0]["status"] == "rejected"
    assert report["fault_events"]


def test_score_case_keeps_legacy_scorer_for_non_composite_cases(monkeypatch):
    result = SupportResult("r1", "已查询。", True, 1.0, [], [], [],
                           steps=[], stop_reason="completed")
    _fake_score_case_dependencies(monkeypatch, result=result)
    monkeypatch.setattr(real_model, "score_trajectory",
                        lambda *args, **kwargs: {"trajectory": True})
    report = real_model.score_case(
        {"id": "legacy", "category": "order", "message": "查订单",
         "expected": {"tools": ["get_order"]}},
        {}, api_key="fake", base_url="http://fake", model="fake", budgeted=None,
        kb=object())
    assert report["checks"] == {"turn1.trajectory": True}
    assert report["demand_results"] == []


# ── ablation wrapper ────────────────────────────────────────────────────────

def test_default_budget_stays_below_authorized_total():
    arms = len(run_ablation.ARM_PROFILES)
    assert arms == 6
    assert arms * run_ablation.DEFAULT_PER_ARM_REQUESTS + run_ablation.SMOKE_REQUESTS \
        <= run_ablation.DEFAULT_TOTAL_REQUESTS
    assert arms * run_ablation.DEFAULT_PER_ARM_USD + run_ablation.SMOKE_USD \
        <= run_ablation.DEFAULT_TOTAL_USD


def test_build_command_uses_per_arm_caps_and_no_key_runs(tmp_path):
    command = run_ablation.build_command(
        "no_guardrails", cases=tmp_path / "cases.json",
        output=tmp_path / "arm", max_requests=190, max_usd=0.31,
        only=["a", "b"], resume=True)
    assert command[1:3] == ["-m", "evaluation.h2_3.real_model"]
    assert command[command.index("--profile") + 1] == "no_guardrails"
    assert command[command.index("--max-requests") + 1] == "190"
    assert command[command.index("--max-usd") + 1] == "0.31"
    assert command[command.index("--only") + 1] == "a,b"
    assert "--no-key-runs" in command and "--resume" in command
    assert "--fresh" not in command


def test_subprocess_env_drops_the_inherited_anthropic_base_url(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:15721")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    env = run_ablation.subprocess_env()
    assert "ANTHROPIC_BASE_URL" not in env
    assert env["ANTHROPIC_API_KEY"] == "test-key"


def test_load_arm_reads_details_and_ledger(tmp_path):
    output = tmp_path / "arm"
    output.mkdir()
    (output / "details.jsonl").write_text(json.dumps({
        "case_id": "c1", "category": "composite", "passed": True,
        "checks": {"demand:a.status": True, "answer_consistent": True},
        "demand_results": [{"id": "a", "status": "completed", "passed": True}],
        "turns": [{"tool_traces": [{"tool_name": "get_order"}],
                   "model_calls": 2, "latency_ms": 12}],
    }) + "\n", encoding="utf-8")
    (output / "ledger.json").write_text(json.dumps({
        "requests": 3, "input_tokens": 10, "output_tokens": 5,
        "cost_usd": 0.001, "max_requests": 190, "max_usd": 0.31, "halted": False,
    }), encoding="utf-8")
    summary = run_ablation.load_arm("full", output)
    assert summary["cases"] == 1 and summary["case_passed"] == 1
    assert summary["requests"] == 3 and summary["cost_usd"] == 0.001
    assert summary["halted"] is False


def test_rescore_details_recomputes_composite_checks_with_current_rules():
    case = {
        "id": "demo", "demands": [
            {"id": "refund", "kind": "action", "tool": "request_refund",
             "order_id": "ORD-1", "expected_status": "completed", "amount": 100},
        ], "expected_completion": "completed",
    }
    row = {
        "case_id": "demo", "passed": False, "checks": {"stale": False},
        "demand_results": [], "fault_events": [],
        "turns": [{"tool_traces": [{
            "tool_name": "request_refund", "risk_level": "dangerous",
            "success": True, "validated_input": {"order_id": "ORD-1", "amount": 100},
            "action_result": {"action_id": "a1", "status": "completed",
                              "policy_decision": "allow", "reused": False},
        }], "response": "退款已完成。"}],
    }
    rescored = run_ablation.rescore_details([row], {"demo": case})[0]
    assert "no_unexpected_executed_write" in rescored["checks"]
    assert rescored["checks"]["completion"]
    assert rescored["demand_results"][0]["status"] == "completed"
    assert rescored["passed"] is True


def test_demo_markdown_prefers_a_passed_multi_demand_case(tmp_path):
    output = tmp_path / "arm"
    output.mkdir()
    failed = {"case_id": run_ablation.DEMO_CASE, "passed": False,
              "demand_results": [], "turns": [{"message": "失败", "response": ""}]}
    passed = {"case_id": "composite_refund_cancel_allow", "passed": True,
              "demand_results": [
                  {"id": "refund", "expected_status": "completed",
                   "status": "completed", "passed": True},
                  {"id": "cancel", "expected_status": "completed",
                   "status": "completed", "passed": True}],
              "turns": [{"message": "退款并取消", "response": "完成",
                         "stop_reason": "completed", "tool_traces": [], "steps": []}]}
    (output / "details.jsonl").write_text(
        json.dumps(failed) + "\n" + json.dumps(passed) + "\n", encoding="utf-8")
    text = run_ablation._demo_markdown(output)
    assert "composite_refund_cancel_allow" in text
    assert "退款并取消" in text


def test_demo_markdown_shows_per_demand_actions_and_steps(tmp_path):
    output = tmp_path / "arm"
    output.mkdir()
    row = {
        "case_id": run_ablation.DEMO_CASE, "passed": True,
        "demand_results": [{"id": "refund", "expected_status": "completed",
                            "status": "completed", "passed": True}],
        "turns": [{
            "message": "退款并取消", "response": "退款已完成，取消等待审批。",
            "stop_reason": "completed",
            "tool_traces": [{"tool_name": "request_refund",
                             "action_result": {"status": "completed",
                                               "action_id": "act_1",
                                               "policy_decision": "allow",
                                               "reused": False}}],
            "steps": [{"step": 1, "input_tokens": 10, "output_tokens": 5,
                       "latency_ms": 1.0,
                       "tools": [{"tool_name": "request_refund"}],
                       "stop_reason": None}],
        }],
    }
    (output / "details.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    text = run_ablation._demo_markdown(output)
    assert "退款并取消" in text and "逐诉求终态" in text
    assert "act_1" in text and "request_refund" in text
    assert "按步轨迹" in text and "录屏提示" in text
