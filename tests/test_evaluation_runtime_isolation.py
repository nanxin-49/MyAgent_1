"""N10: real lifespan and evaluator, fake external dependencies only."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from actions import ActionService
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from api import main
from evaluation.evaluator import QualityScores
from tests.auth_helpers import customer
from tests.test_action_service import NOW, raw_data
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient

pytestmark = pytest.mark.usefixtures("authenticated_http")


@pytest.fixture
def started(monkeypatch, tmp_path, request):
    from agents import support_agent
    from memory import conversation_memory
    from mcp import knowledge_base, tool_manager
    from core import intent_recognizer
    from monitor import performance_monitor
    from evaluation import evaluator
    import actions

    data = raw_data(refunds=False, status="paid", total=getattr(request, "param", "129.90"))
    fixture = tmp_path / "business.json"
    fixture.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("CARTCARE_BUSINESS_FIXTURE", str(fixture))
    monkeypatch.setenv("EVAL_BASELINE_PATH", str(tmp_path / "baseline.json"))
    monkeypatch.setattr(main, "_anthropic_cfg", lambda: {"api_key": "fake", "model": "fake"})
    for name in ("_orchestrator", "_memory", "_tool_manager", "_action_service", "_monitor", "_evaluator", "_skill_manager"):
        monkeypatch.setattr(main, name, None)
    runtimes, services, managers, sdks, plans = [], [], [], [], []
    class SDK(FakeClient):
        closed = False
        async def close(self): self.closed = True
    def runtime(**kwargs):
        sdk = SDK("request_cancel_order", {"order_id": "ORD-1001", "idempotency_key": "n10"})
        if plans:
            sdk.responses = [response for tool, args in plans.pop(0)
                             for response in FakeClient(tool, args).responses]
        obj = SupportRuntime(**kwargs, client=sdk)
        runtimes.append(obj)
        sdks.append(sdk)
        return obj
    def service(**kwargs):
        obj = ActionService(**kwargs, clock=lambda: NOW)
        services.append(obj)
        return obj
    class KB:
        def __init__(self, **kwargs): pass
        async def doc_count_async(self): return 0
        async def search_handler(self, *args): return []
    class Manager:
        def __init__(self, **kwargs):
            self._client = SDK("unused", {})
            self._tools, self._cache = {}, {}
            managers.append(self)
        def register(self, tool): self._tools[tool.name] = tool
    class Monitor:
        def __init__(self, **kwargs): pass
        async def start(self): pass
        async def stop(self): pass
    async def judge(*args, **kwargs): return QualityScores(1, 1, 1, 1)
    monkeypatch.setattr(support_agent, "SupportRuntime", runtime)
    monkeypatch.setattr(actions, "ActionService", service)
    monkeypatch.setattr(conversation_memory, "MemoryManager", EmptyMemory)
    monkeypatch.setattr(intent_recognizer, "IntentRecognizer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(knowledge_base, "KnowledgeBase", KB)
    monkeypatch.setattr(tool_manager, "MCPToolManager", Manager)
    monkeypatch.setattr(performance_monitor, "PerformanceMonitor", Monitor)
    monkeypatch.setattr(evaluator.LLMJudge, "judge", judge)
    with TestClient(main.app, raise_server_exceptions=False,
                    headers={"Authorization": "Bearer test-customer-1"}) as http:
        yield SimpleNamespace(http=http, runtimes=runtimes, services=services,
                              managers=managers, sdks=sdks, fixture=fixture, plans=plans)


def run(h, **case):
    return h.http.post("/eval/run", json={"dialog_cases": [{"question": "cancel", **case}]})


def test_startup_never_binds_chat_runtime_to_evaluator(started):
    assert main._evaluator._orchestrator is not main._orchestrator


def test_authenticated_simulated_write_on_eval_scope_leaves_chat_unchanged(started):
    """Audit trigger with an explicitly trusted test customer after N02 gates."""
    async def write(runtime):
        req = Request("cancel", "customer-1", "eval-probe", principal=customer())
        result = await runtime.run(req)
        assert result.tool_traces[0]["action_result"]["status"] == "completed"
    async def probe():
        factory = getattr(main._evaluator, "_runtime_factory", None)
        if factory is None:
            await write(main._evaluator._orchestrator)
        else:
            async with factory() as runtime:
                await write(runtime)
    asyncio.run(probe())
    assert main._action_service._business_backend.get_order("ORD-1001")["status"] == "paid"
    assert main._action_service._store._actions == {}
    assert main._memory.writes == []


def test_eval_cancel_is_observable_without_changing_chat(started):
    h = started
    # Actual /chat reads before and after the eval, through its production tools.
    def chat_read():
        h.sdks[0].responses = FakeClient("get_order", {"order_id": "ORD-1001"}).responses
        response = h.http.post("/chat", json={"message": "query"})
        assert response.status_code == 200
        return main._orchestrator.get_tool_trace(response.json()["request_id"])["tool_calls"][0]["business_result"]
    before = chat_read()
    assert before["status"] == "paid"
    response = run(h, user_id="customer-1")
    assert response.status_code == 200
    eval_service = h.services[-1]
    assert eval_service._business_backend.get_order("ORD-1001")["status"] == "cancelled"
    assert chat_read() == before
    assert main._action_service._store._actions == {}
    assert h.runtimes[-1] is not main._orchestrator
    assert h.managers[-1] is not main._tool_manager
    assert h.managers[-1]._tools["knowledge_search"].stats is not main._tool_manager._tools["knowledge_search"].stats
    assert len(main._orchestrator.get_recent_tool_traces()) == 2
    assert len(h.runtimes[-1].get_recent_tool_traces()) == 1
    assert h.sdks[-1].closed and h.managers[-1]._client._client.closed


def test_two_runs_start_clean_and_do_not_reuse_actions(started):
    assert run(started, user_id="customer-1").status_code == 200
    first = started.services[-1]
    assert run(started, user_id="customer-1").status_code == 200
    second = started.services[-1]
    assert first is not second
    assert first._business_backend.state is not second._business_backend.state
    assert first._store is not second._store
    assert len(first._executor._backend.calls) == len(second._executor._backend.calls) == 1
    assert set(first._store._actions).isdisjoint(second._store._actions)
    assert main._action_service._business_backend.get_order("ORD-1001")["status"] == "paid"


def test_eval_refund_write_then_query_shares_its_own_state(started):
    started.plans.append([
        ("request_refund", {"order_id": "ORD-1001", "amount": 10, "idempotency_key": "refund"}),
        ("get_refund_status", {"order_id": "ORD-1001"}),
        ("request_refund", {"order_id": "ORD-1001", "amount": 10.0, "idempotency_key": "refund"}),
    ])
    response = run(started, turns=["refund", "query", "repeat"])
    assert response.status_code == 200
    service = started.services[-1]
    assert service._business_backend.state is service._executor._backend.state
    traces = list(reversed(started.runtimes[-1].get_recent_tool_traces()))
    action = traces[0]["tool_calls"][0]["action_result"]
    assert action["status"] == "completed"
    record = traces[1]["tool_calls"][0]["business_result"]
    assert record["status"] == "pending" and record["amount"] == "10"
    assert traces[2]["tool_calls"][0]["action_result"]["action_id"] == action["action_id"]
    assert len(service._executor._backend.calls) == 1
    assert main._action_service._business_backend.get_refund_for_order("ORD-1001") is None
    assert main._action_service._business_backend.get_order("ORD-1001")["status"] == "paid"
    assert main._action_service._store._actions == {}


def test_eval_customer_does_not_bypass_hitl_or_ownership(started):
    # Factory fixes its initial data before chat mutation, and permits no reviewer role.
    main._action_service._business_backend._data["orders"]["ORD-1001"]["status"] = "shipped"
    started.plans.append([
        ("request_refund", {"order_id": "ORD-1001", "amount": 999, "idempotency_key": "deny"}),
    ])
    assert run(started).status_code == 200
    service = started.services[-1]
    assert service._business_backend.get_order("ORD-1001")["status"] == "paid"
    assert not service._executor._backend.calls
    action = next(iter(service._store._actions.values()))
    assert action.status.value == "rejected"
    assert action.requested_by == "evaluation:fixture:customer-1"
    assert service.request_cancel(order_id="ORD-1001", user_id="customer-2", request_id="wrong-owner",
                                  principal=customer("customer-2")).status.value == "rejected"


@pytest.mark.parametrize("started", ["800"], indirect=True)
def test_eval_high_amount_keeps_approval_gate(started):
    from evaluation.runtime import EVALUATION_PRINCIPAL
    started.plans.append([("request_refund", {"order_id": "ORD-1001", "amount": 600, "idempotency_key": "hitl"})])
    assert run(started).status_code == 200
    service = started.services[-1]
    action = next(iter(service._store._actions.values()))
    assert action.status.value == "awaiting_approval"
    result = service.approve(action_id=action.action_id, user_id="customer-1", request_id="self-approve",
                             principal=EVALUATION_PRINCIPAL)
    assert not result.success
    assert not service._executor._backend.calls
    assert service._business_backend.get_refund_for_order("ORD-1001") is None
    assert main._action_service._store._actions == {}


def test_eval_rejects_non_fixture_identity_before_constructing_runtime(started):
    assert run(started, user_id="customer-2").status_code == 422
    assert len(started.runtimes) == 1
    assert main._action_service._store._actions == {}


def test_overlapping_evals_use_request_local_runtime(started, monkeypatch):
    from evaluation.evaluator import LLMJudge
    async def overlap():
        gate = asyncio.Event()
        arrived = 0
        async def judge(*args, **kwargs):
            nonlocal arrived
            arrived += 1
            if arrived == 2: gate.set()
            await asyncio.wait_for(gate.wait(), 3)
            return QualityScores(1, 1, 1, 1)
        monkeypatch.setattr(LLMJudge, "judge", judge)
        reports = await asyncio.gather(*[main._evaluator.run(dialog_cases=[{"question": "cancel"}]) for _ in range(2)])
        assert all(r.total == 1 for r in reports)
    asyncio.run(overlap())
    first, second = started.services[-2:]
    assert first._business_backend.state is not second._business_backend.state
    assert len(first._executor._backend.calls) == len(second._executor._backend.calls) == 1
    assert main._action_service._store._actions == {}


def test_exception_after_write_does_not_pollute_chat_or_next_run(started, monkeypatch):
    from evaluation.evaluator import LLMJudge
    async def broken(*args, **kwargs): raise RuntimeError("synthetic judge crash")
    with monkeypatch.context() as patch:
        patch.setattr(LLMJudge, "judge", broken)
        assert run(started, user_id="customer-1").status_code == 500
    failed = started.services[-1]
    assert failed._business_backend.get_order("ORD-1001")["status"] == "cancelled"
    assert started.sdks[-1].closed
    assert main._action_service._business_backend.get_order("ORD-1001")["status"] == "paid"
    assert main._action_service._store._actions == {}
    assert run(started, user_id="customer-1").status_code == 200
    assert started.services[-1] is not failed
    assert len(started.services[-1]._executor._backend.calls) == 1


def test_isolation_construction_failure_closes_sdk_and_never_falls_back(started, monkeypatch):
    from mcp import tool_manager
    def broken(**kwargs): raise RuntimeError("synthetic construction failure")
    with monkeypatch.context() as patch:
        patch.setattr(tool_manager, "MCPToolManager", broken)
        assert run(started).status_code == 500
    assert started.sdks[-1].closed
    assert main._orchestrator.get_recent_tool_traces() == []
    assert main._memory.writes == []
    assert main._action_service._store._actions == {}
    assert main._action_service._business_backend.get_order("ORD-1001")["status"] == "paid"
    assert run(started).status_code == 200
    assert len(started.services[-1]._executor._backend.calls) == 1


@pytest.mark.parametrize("token, expected", [(None, 401), ("test-u", 403), ("test-reviewer", 403)])
def test_eval_still_requires_admin(started, token, expected):
    response = started.http.post("/eval/run", headers={"Authorization": "" if token is None else f"Bearer {token}"})
    assert response.status_code == expected
    assert len(started.runtimes) == 1




