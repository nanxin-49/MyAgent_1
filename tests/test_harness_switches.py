"""H2-1: component switches, evaluation-only config, and JSON-scripted model."""
import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from actions import ActionService, InMemoryBusinessActionBackend
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from api import main
from core.harness import HarnessConfig
from evaluation.prepare_online_eval import prepare
from evaluation.runtime import EvaluationRuntimeFactory
from evaluation.scripted_model import ScriptedModel, script_from_file
from evaluation.topology_experiment import isolated_business
from memory.conversation_memory import MsgRole
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer
from tests.test_action_service import NOW, raw_data
from tests.test_memory_boundary import manager


def action_service(*, harness=None, expired=False):
    data = raw_data(refunds=False)
    if expired:
        data["orders"]["ORD-1001"]["created_at"] = "2026-09-01T00:00:00Z"
    read = InMemoryBusinessBackend(data)
    write = InMemoryBusinessActionBackend(read.state)
    service = ActionService(
        business_backend=read,
        action_backend=write,
        clock=lambda: NOW,
        harness=harness,
    )
    return service, write


def refund(service, amount="100"):
    return service.request_refund(
        order_id="ORD-1001",
        user_id="customer-1",
        request_id="harness-req",
        amount=Decimal(amount),
        principal=customer("customer-1"),
    )


def runtime_with(script_turns, harness, tools=None):
    model = ScriptedModel(script_turns)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    runtime.set_shared_tools(tools or {})
    return runtime, model


def request(message="查订单 ORD-1001"):
    return Request(message, "customer-1", "test", principal=customer("customer-1"))


# ── config isolation ─────────────────────────────────────────────────────────

def test_production_config_cannot_disable_components():
    assert HarnessConfig().tool_round_limit == 3
    with pytest.raises(ValueError):
        HarnessConfig(policy_guard=False)
    with pytest.raises(ValueError):
        HarnessConfig(loop_control=False, mode="production")
    off = HarnessConfig.evaluation(loop_control=False)
    assert off.mode == "evaluation" and off.tool_round_limit == 1000


def test_chat_and_eval_inputs_do_not_expose_harness():
    assert "harness" not in main.ChatRequest.model_fields
    assert "harness" not in main.EvalRunInput.model_fields
    runtime = SupportRuntime("k", "m", client=ScriptedModel([]))
    assert runtime._harness == HarnessConfig()
    assert runtime._harness.policy_guard is True


def test_evaluation_factory_and_components_accept_harness():
    config = HarnessConfig.evaluation(loop_control=False, policy_guard=False)
    factory = EvaluationRuntimeFactory(
        fixture_data={}, cfg={"api_key": "fake", "model": "fake"},
        knowledge_tool=object(), skills_dir=".", max_prompt_chars=1000,
        harness=config,
    )
    assert factory._harness is config
    service, _ = action_service(harness=config)
    assert service._policy_guard is False
    runtime = SupportRuntime("k", "m", client=ScriptedModel([]), harness=config)
    assert runtime._harness is config


def test_evaluation_factory_passes_harness_to_components(monkeypatch):
    import actions
    import agents.support_agent as support_agent
    from mcp.tool_manager import Tool

    captured = {}

    class CaptureService:
        def __init__(self, **kwargs):
            captured["service"] = kwargs

    class CaptureRuntime:
        def __init__(self, **kwargs):
            captured["runtime"] = kwargs

        def set_shared_tools(self, tools):
            captured["tools"] = tools

        async def close(self):
            return None

    monkeypatch.setattr(actions, "ActionService", CaptureService)
    monkeypatch.setattr(support_agent, "SupportRuntime", CaptureRuntime)
    tool = Tool(name="knowledge_search", description="demo",
                handler=lambda *args: [], schema={"type": "object", "properties": {}})
    config = HarnessConfig.evaluation(loop_control=False)
    factory = EvaluationRuntimeFactory(
        fixture_data=raw_data(refunds=False), cfg={"api_key": "fake", "model": "fake"},
        knowledge_tool=tool, skills_dir=str(Path(__file__).resolve().parents[1] / "skills"),
        max_prompt_chars=5000, harness=config,
    )

    async def run():
        async with factory() as runtime:
            assert runtime is not None

    asyncio.run(run())
    assert captured["runtime"]["harness"] is config
    assert captured["service"]["harness"] is config


# ── individual switches ──────────────────────────────────────────────────────

def test_policy_guard_off_only_in_evaluation():
    on_service, on_backend = action_service(expired=True)
    on = refund(on_service)
    assert on.status.value == "rejected" and on.error_code == "refund_window_expired"
    assert len(on_backend.calls) == 0

    off_service, off_backend = action_service(
        expired=True, harness=HarnessConfig.evaluation(policy_guard=False))
    off = refund(off_service)
    assert off.status.value == "completed"
    assert off.action.policy_decision.reason_code == "harness_policy_disabled"
    assert len(off_backend.calls) == 1


def test_error_feedback_controls_model_visible_error():
    fixture = prepare(NOW)[0]
    tools, _, _ = isolated_business(fixture, NOW)
    turns = script_from_file("evaluation/scripts/error_feedback_not_found.json")._turns
    on_runtime, on_model = runtime_with(turns, HarnessConfig(), tools)
    asyncio.run(on_runtime.run(request("查订单 ORD-MISSING")))
    on_payload = on_model.calls[1]["messages"][-1]["content"][0]["content"]
    assert "not_found" in on_payload and "error" in on_payload and "acknowledged" not in on_payload

    off_runtime, off_model = runtime_with(
        turns, HarnessConfig.evaluation(error_feedback=False), tools)
    asyncio.run(off_runtime.run(request("查订单 ORD-MISSING")))
    off_payload = off_model.calls[1]["messages"][-1]["content"][0]["content"]
    assert json.loads(off_payload) == {"success": True, "acknowledged": True}
    assert "error_code" not in off_payload


def test_context_compression_off_keeps_raw_messages():
    async def run(enabled):
        memory = manager()
        memory._context_compression = enabled
        for index in range(16):
            content = "订单号 ORD-ALPHA-123" if index == 0 else f"消息 {index}"
            await memory.add_message("u", "c", MsgRole.USER, content)
        key = memory._wm_key("u", "c")
        return len(memory._redis.values[key]), memory._summary_key("u", "c") in memory._redis.values

    assert asyncio.run(run(True)) == (6, True)
    assert asyncio.run(run(False)) == (16, False)


def test_loop_control_off_runs_fourth_tool_round():
    fixture = prepare(NOW)[0]
    tools, _, _ = isolated_business(fixture, NOW)
    turns = script_from_file("evaluation/scripts/loop_control_4_rounds.json")._turns
    on_runtime, on_model = runtime_with(turns, HarnessConfig(), tools)
    on_result = asyncio.run(on_runtime.run(request()))
    assert len(on_model.calls) == 3
    assert len(on_result.tools_used) == 3
    assert "四次查询完成" not in on_result.response

    off_runtime, off_model = runtime_with(
        turns, HarnessConfig.evaluation(loop_control=False), tools)
    off_result = asyncio.run(off_runtime.run(request()))
    assert len(off_model.calls) == 5
    assert len(off_result.tools_used) == 4
    assert "四次查询完成" in off_result.response


def test_output_consistency_off_returns_raw_claim():
    turn = [{"text": "已成功创建人工交接记录，编号 DEMO-123。"}]
    on_runtime, _ = runtime_with(turn, HarnessConfig())
    on_result = asyncio.run(on_runtime.run(request("你好")))
    assert "已成功创建人工交接记录" not in on_result.response
    assert "本次未创建人工交接记录" in on_result.response

    off_runtime, _ = runtime_with(
        turn, HarnessConfig.evaluation(output_consistency=False))
    off_result = asyncio.run(off_runtime.run(request("你好")))
    assert off_result.response == "已成功创建人工交接记录，编号 DEMO-123。"


# ── scripted model round-trip ────────────────────────────────────────────────

def test_scripted_model_executes_multi_round_tools():
    fixture = prepare(NOW)[0]
    tools, _, _ = isolated_business(fixture, NOW)
    script = [
        {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1001"},
                         "id": "call_1"}]},
        {"tool_calls": [{"name": "get_shipment", "input": {"order_id": "ORD-1001"},
                         "id": "call_2"}]},
        {"text": "查询完成。"},
    ]
    runtime, model = runtime_with(script, HarnessConfig(), tools)
    result = asyncio.run(runtime.run(request()))
    assert len(model.calls) == 3
    assert result.tools_used == ["get_order", "get_shipment"]
    assert result.response == "查询完成。"
    assert model.calls[0]["model"] == "test"
