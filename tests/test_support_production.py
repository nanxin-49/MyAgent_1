"""Production HTTP wiring and deterministic safety; fake SDK is not online evidence."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import main
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import build_shared_rag_tools
from evaluation.topology_experiment import SingleSupportAgent as ExperimentalAgent
from tests.test_topology_comparison import CATALOG, NOW, FakeClient
from evaluation.prepare_online_eval import prepare
from evaluation.topology_experiment import isolated_business
from evaluation import run_baseline


class EmptyMemory:
    def __init__(self, **kwargs):
        self.writes = []

    async def get_context(self, *args, **kwargs):
        return SimpleNamespace(recent_messages=[], to_prompt_text=lambda: "")

    async def add_message(self, *args):
        self.writes.append(args)

    async def update_profile(self, *args):
        pass

    async def close(self):
        pass


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: c["id"])
def test_chat_uses_support_and_guarded_shared_tools(monkeypatch, case):
    fixture, _ = prepare(NOW)
    tools, service, backend = isolated_business(fixture, NOW)
    if case["kind"] == "rag":
        expected = case["expected"]
        citation = {"reference": expected["citation"], "document_id": expected["document_id"],
                    "source": expected["source"], "chunk_index": 0, "policy_version": expected["policy_version"]}
        class Rag:
            async def search_with_rewrite(self, *args, **kwargs):
                return SimpleNamespace(success=True, retrieval_status="usable", citations=[citation],
                    data=[{"content": "7 天内可申请退款", "citation": citation}], reranked=False)
        tools.update(build_shared_rag_tools(Rag()))
        client = FakeClient("search_knowledge_base", {"query": case["message"]}, "7 天内可申请退款")
    elif case.get("tool"):
        client = FakeClient(case["tool"], case["arguments"])
    else:
        client = FakeClient("unused", {})
        client.responses = [SimpleNamespace(content=[SimpleNamespace(type="text", text="请提供商品名称或 SKU。"
            if case["kind"] == "clarification" else "电商客服无法预订机票。")])]
    runtime = SupportRuntime("test", "test", client=client)
    runtime.set_shared_tools(tools)
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_memory", EmptyMemory())
    monkeypatch.setattr(main, "_action_service", service)
    http = TestClient(main.app)  # no lifespan: use isolated deterministic dependencies
    response = http.post("/chat", json={"message": case["message"], "user_id": case.get("user_id", "customer-1")})
    assert response.status_code == 200
    body = response.json()
    assert body["topology"] == "single" and body["agent_type"] == "support"
    assert body["intent"] is None and body["primary_agent"] is None and body["supporting_agents"] is None
    trace = runtime.get_tool_trace(body["request_id"])
    assert trace["topology"] == "single" and trace["agent_type"] == "support"
    assert trace["model_call_count"] == len(client.calls) == body["model_call_count"]
    assert runtime.supports_routing is False
    if case["kind"] == "action":
        action = trace["tool_calls"][0]["action_result"]
        assert action["status"] == case["expected"]["status"]
        assert action["policy_decision"] == case["expected"]["policy_decision"]
        assert len(backend.calls) == (1 if action["status"] == "completed" else 0)
    elif case["kind"] == "rag":
        assert body["retrieval_status"] == "usable" and body["citations"][0]["reference"] == expected["citation"]
        assert expected["citation"] in body["response"]
    elif case["kind"] == "clarification":
        assert not body["tools_used"]
    elif case["kind"] == "read":
        assert trace["tool_calls"][0]["business_result"][case["expected"]["data_field"]] == case["expected"]["data_value"]
    assert len(main._memory.writes) == 2
    if case["id"] == "refund_approval":
        action_id = action["action_id"]
        assert http.post(f"/actions/{action_id}/resume", json={"user_id": "customer-1"}).json()["status"] == "awaiting_approval"
        for _ in range(2):
            assert http.post(f"/actions/{action_id}/approve", json={"user_id": "customer-1"}).json()["status"] == "completed"
        assert len(backend.calls) == 1


def test_production_prompt_and_registry_equal_accepted_single():
    tools, _, _ = isolated_business(prepare(NOW)[0], NOW)
    runtime = SupportRuntime("test", "test", client=FakeClient("unused", {}))
    runtime.set_shared_tools(tools)
    production = runtime.make_agent()
    experiment = ExperimentalAgent(FakeClient("unused", {}), "test")
    experiment.set_shared_tools(tools)
    experiment.profile = replace(experiment.profile, tool_scope=tuple(experiment.get_tools()))
    request = Request("退款", "customer-1", "test")
    assert production._build_system_prompt(request) == experiment._build_system_prompt(request)
    assert production.profile.temperature == experiment.profile.temperature
    assert production.profile.max_tokens == experiment.profile.max_tokens
    assert production.get_tools() == experiment.get_tools()
    assert production._build_role_packet(request) == ""


def test_support_dangerous_schema_cannot_skip_policy_and_idempotency():
    tools, service, backend = isolated_business(prepare(NOW)[0], NOW)
    runtime = SupportRuntime("test", "test", client=FakeClient("request_refund",
        {"order_id": "ORD-T09-REFUND-APPROVAL", "amount": 600, "approved": True}))
    runtime.set_shared_tools(tools)
    result = asyncio.run(runtime.run(Request("退款", "customer-1", "test")))
    assert not backend.calls and not service._store._actions
    assert result.tool_traces[0]["error_type"] == "validation"
    cancel = tools["request_cancel_order"]
    req = Request("取消", "customer-1", "test")
    args = {"order_id": "ORD-T09-CANCEL", "idempotency_key": "production-repeat"}
    first, second = cancel.handler(req, args), cancel.handler(req, args)
    assert first["action_id"] == second["action_id"] and len(backend.calls) == 1


def test_historical_baseline_consumer_treats_single_routing_as_unobserved(monkeypatch):
    chat = {"request_id": "single-test", "topology": "single", "agent_type": "support",
            "agent_types": ["support"], "intent": None, "primary_agent": None,
            "supporting_agents": None, "routing_reason": None, "routing_confidence": None,
            "response": "请提供订单号", "tools_used": [], "latency_ms": 5}
    monkeypatch.setattr(run_baseline, "_json_request", lambda _base, path, *args, **kwargs:
        {"trace": {"request_id": "single-test", "tool_calls": [], "primary_agent": None,
                   "supporting_agents": None}} if path.startswith("/trace/") else chat)
    row = run_baseline._run_case({"id": "nullable", "messages": ["订单状态"],
        "expected": {"intent": "order_status", "primary_agent": "general",
                     "supporting_agents": [], "multi_agent": False}}, "http://localhost", 5)
    assert row["actual"]["primary_agent"] is None
    assert all(row["checks"][key] is None for key in
               ("intent", "primary_routing", "supporting_routing", "multi_agent"))
    metrics = run_baseline._metric_summary([row])
    assert metrics["intent_accuracy"] is None
    assert metrics["primary_routing_accuracy"] is None
    assert metrics["multi_agent_trigger_rate"] is None
