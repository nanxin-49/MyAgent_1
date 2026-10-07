"""Deterministic experiment wiring/measurement tests, not Agent quality evidence."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from agents.agent_orchestrator import Request
from evaluation.prepare_online_eval import prepare
from evaluation.run_topology_comparison import ObservedMessages
from evaluation.topology_eval import compare, score_record
from evaluation.topology_experiment import SingleSupportAgent, bind_tools, helper_tools, isolated_business

CATALOG = json.loads((Path(__file__).resolve().parents[1] / "evaluation/t10_cases.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, tool, args, text="已处理"):
        self.calls = []
        self.responses = [SimpleNamespace(content=[SimpleNamespace(type="tool_use", id="t1", name=tool, input=args)]),
                          SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])]
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def record(case, response="请提供商品名称或 SKU。", traces=None, arm="single_agent"):
    return {"case_id": case, "topology": arm, "run": 1, "elapsed_ms": 20,
        "chat": {"response": response, "intent": None, "tools_used": [], "escalated": False},
        "tool_traces": traces or [], "backend_executions": [], "model_calls": []}


def test_contract_does_not_require_guessing_inventory_and_has_new_provenance():
    inventory = next(c for c in CATALOG if c["id"] == "inventory_lookup")
    assert inventory["kind"] == "clarification" and "arguments" not in inventory
    assert inventory["expected"]["tool"] is None
    faq = next(c for c in CATALOG if c["id"] == "faq_policy")
    assert faq["expected"]["source"] == "demo:cartcare-default/refund-policy"
    assert "refund-cancel-v1" in faq["expected"]["citation"]


def test_inventory_clarification_passes_but_guessed_sku_fails():
    assert score_record(CATALOG, record("inventory_lookup"))["task_success"]
    guessed = record("inventory_lookup", traces=[{"tool_name": "check_inventory",
        "validated_input": {"product_id": "SKU-1001"}}])
    assert not score_record(CATALOG, guessed)["task_success"]
    irrelevant = record("inventory_lookup", traces=[{"tool_name": "inspect_request_context"}])
    assert score_record(CATALOG, irrelevant)["unnecessary_tool_calls"] == 1


def test_missing_observations_do_not_pass_or_become_zero_model_calls():
    missing = {"case_id": "order_lookup", "topology": "single_agent", "run": 1,
               "error": "dependency unavailable", "elapsed_ms": 10}
    report = compare(CATALOG, [missing], {})
    arm = report["arms"]["single_agent"]
    assert arm["metrics"]["task_success"]["value"] == 0
    assert arm["metrics"]["tool_selection"]["value"] is None
    assert arm["model_calls"] is None
    assert arm["metrics"]["intent_accuracy"] == "N/A"
    assert arm["metrics"]["routing_accuracy"] == "N/A"
    assert arm["metrics"]["grounding"]["not_applicable"] == 1
    assert arm["metrics"]["grounding"]["missing"] == 0
    assert arm["metrics"]["argument_correctness"]["missing"] == 1


def test_single_shares_registry_and_has_no_classifier_role_packet():
    fixture, _ = prepare(NOW)
    tools, _, _ = isolated_business(fixture, NOW)
    client = FakeClient("get_order", {"order_id": "ORD-T09-ORDER"})
    agent = SingleSupportAgent(client, "test")
    shared = bind_tools(agent, tools, None)
    assert set(agent.get_tools()) == set(shared) | set(helper_tools())
    assert agent.get_tools()["request_refund"] is tools["request_refund"]
    req = Request("查询 ORD-T09-ORDER", "customer-1", "test")
    assert agent._build_role_packet(req) == ""
    result = asyncio.run(agent.handle(req))
    assert req.intent is None and req.entities == {}
    assert result.tool_traces[0]["business_result"]["order_id"] == "ORD-T09-ORDER"


def test_single_cannot_bypass_approval_ownership_or_isolation():
    fixture, _ = prepare(NOW)
    tools, service, backend = isolated_business(fixture, NOW)
    other_tools, other_service, other_backend = isolated_business(fixture, NOW)
    req = Request("退款", "customer-1", "test")
    result = tools["request_refund"].handler(req, {"order_id": "ORD-T09-REFUND-APPROVAL", "amount": 600})
    assert result["status"] == "awaiting_approval" and backend.calls == []
    assert other_service._store._actions == {} and other_backend.calls == []
    denied = tools["request_cancel_order"].handler(Request("取消", "customer-2", "test"),
                                                     {"order_id": "ORD-T09-OWNERSHIP"})
    assert denied["status"] == "rejected" and backend.calls == []
    done = tools["request_cancel_order"].handler(req, {"order_id": "ORD-T09-CANCEL", "idempotency_key": "same"})
    again = tools["request_cancel_order"].handler(req, {"order_id": "ORD-T09-CANCEL", "idempotency_key": "same"})
    assert done["action_id"] == again["action_id"] and len(backend.calls) == 1
    assert other_backend.calls == []


def test_usage_observer_preserves_response_and_marks_missing_usage():
    client = FakeClient("get_order", {"order_id": "ORD-T09-ORDER"})
    events = []
    result = asyncio.run(ObservedMessages(client, "single_support", events).create(model="test", messages=[]))
    assert result.content[0].type == "tool_use"
    assert events[0]["input_tokens"] is None and events[0]["output_tokens"] is None
    assert events[0]["stage"] == "single_support"


def test_runner_preserves_failed_specialist_calls_before_general_fallback(monkeypatch):
    from agents.agent_orchestrator import AgentOrchestrator, AgentResponse, AgentType
    from core.intent_recognizer import IntentCategory, UrgencyLevel
    from evaluation import run_topology_comparison as runner

    def factory(**kwargs):
        topology = AgentOrchestrator(**kwargs)
        async def recognize(message, history=None):
            return SimpleNamespace(intent=IntentCategory.REFUND, intent_group="billing",
                urgency=UrgencyLevel.LOW, entities={}, confidence=1)
        async def billing(req):
            return AgentResponse(AgentType.BILLING, "failed", False, tool_traces=[
                {"tool_name": "get_order", "tool_use_id": "failed_call", "agent_type": "billing"}])
        async def general(req):
            return AgentResponse(AgentType.GENERAL, "完成", True, tool_traces=[
                {"tool_name": "request_refund", "tool_use_id": "fallback_call", "agent_type": "general"}])
        topology._intent_recognizer.recognize = recognize
        topology._pool[AgentType.BILLING][0].handle = billing
        topology._pool[AgentType.GENERAL][0].handle = general
        return topology

    monkeypatch.setattr(runner, "AgentOrchestrator", factory)
    fixture, _ = prepare(NOW)
    result = asyncio.run(runner.run_case("multi_agent", {"id": "refund_allow", "message": "退款"},
        fixture, NOW, {"api_key": "test", "model": "test"},
        SimpleNamespace(search_handler=lambda p, c: []), None,
        SimpleNamespace(temperature=.2, max_tokens=1200, timeout=5), 1))
    assert "error" not in result
    assert [t["tool_use_id"] for t in result["tool_traces"]] == ["failed_call", "fallback_call"]
    assert [t["tool_use_id"] for t in result["returned_tool_traces"]] == ["fallback_call"]
    assert result["execution"]["invoked_agents"] == ["billing", "general"]
