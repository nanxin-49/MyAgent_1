"""H3-3: context composition, prompt budget, and deterministic compression."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import make_tool
from core.context_budget import compose_context, compress_messages, estimate_tokens
from core.harness import HarnessConfig
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


# ── estimator and composition ───────────────────────────────────────────────

def test_estimate_tokens_ascii_cjk_mixed():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("退款") == 2
    assert estimate_tokens("ab退款") == 3


def test_compose_context_reports_categories_without_double_counting():
    messages = [
        {"role": "user", "content": "[背景信息]\n" + "历史" * 10},
        {"role": "assistant", "content": "好的，我已了解背景信息。"},
        {"role": "user", "content": "查订单"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "get_order"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1",
                                      "content": json.dumps({"success": True, "results": ["x"] * 5,
                                                             "citations": [], "retrieval_status": "usable"})}]},
    ]
    composition = compose_context(messages, system="系统提示", tool_schemas=[{"name": "get_order"}])
    for key in ("system_prompt", "tool_schemas", "memory_context", "user_message",
                "dialogue", "tool_results", "retrieval", "total"):
        assert key in composition
    assert composition["memory_context"] > 0
    assert composition["tool_results"] > 0
    assert composition["retrieval"] > 0
    assert composition["total"] == sum(composition[key] for key in (
        "system_prompt", "tool_schemas", "memory_context", "user_message",
        "dialogue", "tool_results"))


# ── compression ─────────────────────────────────────────────────────────────

def _long_messages():
    tool_payload = {"success": False, "error_code": "not_found", "retryable": False,
                    "suggested_action": "ask_user_to_confirm_identifier",
                    "error": "x" * 4000}
    return [
        {"role": "user", "content": "[背景信息]\n" + "背景" * 3000},
        {"role": "assistant", "content": "好的，我已了解背景信息。"},
        {"role": "user", "content": "查订单"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "get_order"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1",
                                      "content": json.dumps(tool_payload, ensure_ascii=False)}]},
    ]


def test_compress_messages_keeps_structured_fields_and_current_request():
    messages = _long_messages()
    current = messages[-1]
    result = compress_messages(messages, budget=600, fixed_tokens=50)
    assert result["compressed"] is True
    compressed = json.loads(result["messages"][-1]["content"][0]["content"])
    assert compressed["compressed"] is True
    assert compressed["error_code"] == "not_found"
    assert compressed["suggested_action"] == "ask_user_to_confirm_identifier"
    assert result["messages"][2] == current or result["messages"][2]["content"] == "查订单"
    assert result["messages"][0]["content"].startswith("[背景信息]")
    assert len(result["messages"][0]["content"]) < len(messages[0]["content"])


def test_compress_messages_noop_when_within_budget():
    messages = [{"role": "user", "content": "查订单"}]
    result = compress_messages(messages, budget=1000, fixed_tokens=10)
    assert result["compressed"] is False
    assert result["messages"] == messages


def test_compress_messages_marks_over_budget_without_dropping_fixed_parts():
    messages = _long_messages()
    result = compress_messages(messages, budget=100, fixed_tokens=10_000)
    assert result["over_budget"] is True
    assert result["messages"][-1]["content"] == messages[-1]["content"] or \
        json.loads(result["messages"][-1]["content"][0]["content"]).get("compressed") is True
    assert result["estimated_tokens"] >= 10_000


# ── agent integration ───────────────────────────────────────────────────────

def _runtime(script, harness, tools):
    model = ScriptedModel(script)
    runtime = SupportRuntime("test", "test", client=model, harness=harness)
    runtime.set_shared_tools(tools)
    return runtime, model


def _tools_with_big_result():
    tools, _, _ = isolated_business(prepare(NOW)[0], NOW)
    tools["big"] = make_tool("big", "大结果", {}, lambda req, args: {
        "success": True, "data": {"blob": "x" * 3000}})
    return tools


def test_agent_records_context_rounds_and_compresses_when_over_budget():
    tools = _tools_with_big_result()
    script = [
        {"tool_calls": [{"name": "big", "input": {}}]},
        {"text": "完成。"},
    ]
    harness = HarnessConfig(max_context_tokens=1200)
    runtime, _ = _runtime(script, harness, tools)
    principal = customer("customer-1")
    request = Request("调用大结果工具", principal.customer_id, "h33",
                      context="[背景信息]\n" + "背景" * 2000, principal=principal)
    result = asyncio.run(runtime.run(request))
    assert result.response == "完成。"
    rounds = result.context_rounds
    assert len(rounds) == 2
    assert rounds[0]["round"] == 1 and rounds[1]["round"] == 2
    assert all("estimated_tokens" in row for row in rounds)
    assert any(row["compressed"] for row in rounds)
    trace = runtime.get_tool_trace(result.request_id)
    assert len(trace["context_rounds"]) == 2


def test_context_compression_off_records_but_does_not_compress():
    tools = _tools_with_big_result()
    script = [{"tool_calls": [{"name": "big", "input": {}}]}, {"text": "完成。"}]
    harness = HarnessConfig.evaluation(context_compression=False, max_context_tokens=1200)
    runtime, _ = _runtime(script, harness, tools)
    principal = customer("customer-1")
    request = Request("调用大结果工具", principal.customer_id, "h33",
                      context="[背景信息]\n" + "背景" * 2000, principal=principal)
    result = asyncio.run(runtime.run(request))
    assert len(result.context_rounds) == 2
    assert not any(row["compressed"] for row in result.context_rounds)
    assert result.response == "完成。"


# ── comparison runner ───────────────────────────────────────────────────────

def test_context_budget_comparison_keeps_success_and_reduces_tokens():
    from evaluation.h3_3.run_context_budget import evaluate

    report = evaluate()
    on, off = report["arms"]["on"], report["arms"]["off"]
    assert on["task_success_rate"] == 1.0
    assert off["task_success_rate"] == 1.0
    assert on["estimated_tokens"] < off["estimated_tokens"]
    assert on["compressed_rounds"] > 0
    assert on["executor_calls"] == off["executor_calls"]
