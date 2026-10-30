"""N04 simulated business write/read and real startup wiring, no live services."""
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from functools import partial
from types import SimpleNamespace
from threading import Event

import pytest
from fastapi.testclient import TestClient

from actions import ActionService
from actions.backend import ActionBackendError
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import build_business_tools
from api import main
from providers import RefundProvider
from providers.errors import UnauthorizedError
from providers.models import OrderStatus
from tests.auth_helpers import customer, reviewer
from tests.test_action_service import make_service, NOW
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient

pytestmark = pytest.mark.usefixtures("authenticated_http")


def refund(service, amount="10", key="n04-key"):
    return service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n04-request", amount=amount, idempotency_key=key, principal=customer())


def assert_record(service, action):
    record = RefundProvider(service._business_backend).get_refund_for_order("ORD-1001", customer_id="customer-1")
    assert record.order_id == action.action.order_id and record.customer_id == action.action.user_id
    assert record.amount == action.action.amount
    assert record.status.value == "pending"
    assert service._business_backend.get_order("ORD-1001")["status"] == "refund_pending"
    assert action.status.value == action.action.execution_result["status"] == "completed"
    assert action.action.execution_result["refund_id"] == record.refund_id
    assert action.action.execution_result["refund_status"] == "pending"
    assert RefundProvider(service._business_backend).get_refund(record.refund_id, customer_id="customer-1") == record
    return record


@pytest.mark.parametrize("approval", [False, True])
def test_executed_refund_is_immediately_queryable(approval):
    service, backend = make_service(total="800")
    result = refund(service, "600" if approval else "10")
    if approval:
        assert result.status.value == "awaiting_approval" and not backend.calls
        result = service.approve(action_id=result.action_id, user_id="customer-1",
                                 request_id="n04-approve", principal=reviewer())
    assert result.status.value == "completed" and len(backend.calls) == 1
    assert_record(service, result)


@pytest.mark.parametrize("state", ["pending", "rejected", "backend_failure"])
def test_unexecuted_refund_does_not_create_record(state):
    service, backend = make_service(total="800", fail_operations={"execute_refund"} if state == "backend_failure" else ())
    result = refund(service, "10" if state == "backend_failure" else "600")
    if state == "rejected":
        result = service.reject(action_id=result.action_id, user_id="customer-1",
                                request_id="n04-reject", principal=customer())
    assert result.status.value == {"pending": "awaiting_approval", "rejected": "rejected", "backend_failure": "failed"}[state]
    assert not backend.calls and service._business_backend.get_refund_for_order("ORD-1001") is None
    assert service._business_backend.get_order("ORD-1001")["status"] == "shipped"


def test_same_key_reuses_one_record_and_changed_parameters_conflict():
    service, backend = make_service()
    first = refund(service)
    second = refund(service, "10.00")
    changed = refund(service, "20")
    assert first.action_id == second.action_id and second.reused
    assert changed.error_code == "idempotency_conflict" and changed.action is None
    assert len(backend.calls) == 1
    assert_record(service, first)
    assert len(service._business_backend._data["refunds"]) == 1


def test_concurrent_duplicate_requests_create_one_record():
    service, backend = make_service()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: refund(service), range(8)))
    assert len({r.action_id for r in results}) == len(backend.calls) == 1
    assert_record(service, results[0])
    assert len(service._business_backend._data["refunds"]) == 1


def test_cross_customer_cannot_read_generated_or_malformed_refund():
    service, _ = make_service()
    record = assert_record(service, refund(service))
    provider = RefundProvider(service._business_backend)
    with pytest.raises(UnauthorizedError):
        provider.get_refund(record.refund_id, customer_id="customer-2")
    raw = service._business_backend._data["refunds"][record.refund_id]
    raw["private_marker"] = "N04-SYNTHETIC-SECRET"
    raw.pop("amount")
    tools = build_business_tools(service._business_backend)
    req = Request("refund progress", "customer-2", "n04-read", principal=customer("customer-2"))
    result = tools["get_refund_status"].handler(req, {"order_id": "ORD-1001"})
    assert result["success"] is False and result["data"] is None
    assert result["error"]["code"] == "not_found"
    assert "N04-SYNTHETIC-SECRET" not in json.dumps(result)
    assert result["error"]["details"] == {}


@pytest.mark.parametrize("stage", ["refunds", "order"])
def test_failed_commit_restores_order_and_refund_table(stage):
    service, backend = make_service()
    class BrokenDict(dict):
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            if (stage == "refunds" or value == "refund_pending"):
                raise RuntimeError("synthetic commit failure")
    if stage == "refunds":
        backend._data["refunds"] = BrokenDict()
    else:
        backend._data["orders"]["ORD-1001"] = BrokenDict(backend._data["orders"]["ORD-1001"])
    result = refund(service)
    assert result.status.value == "failed"
    assert not backend.calls
    assert backend._data.get("refunds", {}) == {}
    assert backend._data["orders"]["ORD-1001"]["status"] == "shipped"


def test_pending_refund_keeps_existing_active_refund_policy():
    from policies import PolicyEngine
    from providers import OrderProvider
    service, _ = make_service()
    record = assert_record(service, refund(service))
    order = OrderProvider(service._business_backend).get_order("ORD-1001", customer_id="customer-1")
    order = order.model_copy(update={"status": OrderStatus.SHIPPED})
    decision = PolicyEngine().evaluate_refund(order, customer_id="customer-1", evaluated_at=NOW,
        amount=Decimal("10"), existing_refund=record)
    assert decision.decision.value == "deny"
    assert decision.reason_code == "refund_already_in_progress"


def test_backend_command_replay_binds_amount_and_does_not_create_second_record():
    service, backend = make_service()
    action = refund(service)
    original = assert_record(service, action)
    replay = backend.execute_refund("ORD-1001", customer_id="customer-1",
                                    amount=Decimal("10.00"), action_id=action.action_id)
    assert replay["refund_id"] == original.refund_id
    with pytest.raises(ActionBackendError, match="退款编号"):
        backend.execute_refund("ORD-1001", customer_id="customer-1",
                               amount=Decimal("20"), action_id=action.action_id)
    assert len(backend.calls) == len(service._business_backend._data["refunds"]) == 1


def test_new_action_key_after_refund_started_does_not_add_record():
    service, backend = make_service()
    assert_record(service, refund(service))
    another = refund(service, key="n04-another")
    assert another.status.value == "rejected"
    assert len(backend.calls) == len(service._business_backend._data["refunds"]) == 1


@pytest.mark.parametrize("old_status", ["failed", "rejected"])
def test_new_pending_application_is_visible_after_old_terminal_refund(old_status):
    service, backend = make_service(refunds=True)
    previous = service._business_backend._data["refunds"]["REF-1001"]
    previous["status"] = old_status
    result = refund(service)
    record = assert_record(service, result)
    assert record.refund_id != "REF-1001" and len(backend.calls) == 1
    assert RefundProvider(service._business_backend).get_refund("REF-1001", customer_id="customer-1").status.value == old_status


def test_invalid_record_validation_has_no_partial_writes():
    service, backend = make_service()
    with pytest.raises(ActionBackendError) as caught:
        backend.execute_refund("ORD-1001", customer_id="customer-1", amount=Decimal("NaN"), action_id="invalid")
    assert caught.value.code == "invalid_refund_record"
    assert backend._data["refunds"] == {} and backend.calls == []
    assert backend._data["orders"]["ORD-1001"]["status"] == "shipped"


def test_reader_cannot_observe_mid_commit_refund_and_order_pair():
    service, backend = make_service()
    assert backend.state is service._business_backend.state
    inserted, release, reader_started, reader_done = Event(), Event(), Event(), Event()
    class PausedRefunds(dict):
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            inserted.set()
            assert release.wait(3), "test must release commit"
    backend._data["refunds"] = PausedRefunds()
    def read():
        reader_started.set()
        record = service._business_backend.get_refund_for_order("ORD-1001")
        order = service._business_backend.get_order("ORD-1001")
        reader_done.set()
        return record, order
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(refund, service)
        try:
            assert inserted.wait(3)
            reading = pool.submit(read)
            assert reader_started.wait(3)
            assert not reader_done.wait(.1), "reader must wait for shared commit lock"
        finally:
            release.set()
        assert writing.result(timeout=3).status.value == "completed"
        record, order = reading.result(timeout=3)
    assert record["status"] == "pending" and order["status"] == "refund_pending"


def test_real_lifespan_refund_approval_and_http_query(monkeypatch, tmp_path):
    """Execute production lifespan; replace only SDK/Memory/RAG/monitor/eval boundaries."""
    from tests.test_action_service import raw_data
    from agents import support_agent
    from memory import conversation_memory
    from mcp import knowledge_base, tool_manager
    from core import intent_recognizer
    from monitor import performance_monitor
    from evaluation import evaluator
    import actions
    from actions import InMemoryActionStore
    from core.checkpoint import InMemoryCheckpointStore

    fixture = tmp_path / "n04-business.json"
    fixture.write_text(json.dumps(raw_data(refunds=False, total="800")), encoding="utf-8")
    monkeypatch.setenv("CARTCARE_BUSINESS_FIXTURE", str(fixture))
    monkeypatch.setattr(main, "_anthropic_cfg", lambda: {"api_key": "fake", "model": "fake"})
    for name in ("_orchestrator", "_memory", "_tool_manager", "_action_service", "_monitor", "_evaluator", "_skill_manager"):
        monkeypatch.setattr(main, name, None)
    class SDK(FakeClient):
        async def close(self):
            pass
    sdk = SDK("request_refund", {"order_id": "ORD-1001", "amount": 600, "idempotency_key": "n04-http"})
    runtime = SupportRuntime("fake", "fake", client=sdk)
    monkeypatch.setattr(support_agent, "SupportRuntime", lambda **kwargs: runtime)
    monkeypatch.setattr(conversation_memory, "MemoryManager", EmptyMemory)
    monkeypatch.setattr(intent_recognizer, "IntentRecognizer", lambda **kwargs: SimpleNamespace())
    class KB:
        def __init__(self, **kwargs): pass
        async def doc_count_async(self): return 0
        async def search_handler(self, *args): return []
    class Manager:
        def __init__(self, **kwargs): self._client = SDK("unused", {})
        def register(self, tool): pass
    class Monitor:
        def __init__(self, **kwargs): pass
        async def start(self): pass
        async def stop(self): pass
    monkeypatch.setattr(knowledge_base, "KnowledgeBase", KB)
    monkeypatch.setattr(tool_manager, "MCPToolManager", Manager)
    monkeypatch.setattr(performance_monitor, "PerformanceMonitor", Monitor)
    monkeypatch.setattr(evaluator, "EndToEndEvaluator", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(actions, "RedisActionStore", lambda *args, **kwargs: InMemoryActionStore())
    monkeypatch.setattr(actions, "RedisCheckpointStore",
                        lambda *args, **kwargs: InMemoryCheckpointStore())
    monkeypatch.setattr(actions, "ActionService", partial(ActionService, clock=lambda: NOW))
    with TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"}) as http:
        pending = http.post("/chat", json={"message": "申请退款"})
        assert pending.status_code == 200
        action_id = pending.json()["action_results"][0]["action_id"]
        service = main._action_service
        assert service._business_backend.get_refund_for_order("ORD-1001") is None
        approved = http.post(f"/actions/{action_id}/approve", headers={"Authorization": "Bearer test-reviewer"}, json={})
        assert approved.status_code == 200 and approved.json()["status"] == "completed"
        assert_record(service, service.get(action_id, user_id="customer-1", principal=customer()))
        sdk.responses = SDK("get_refund_status", {"order_id": "ORD-1001"}, "退款申请等待后续处理，未到账。").responses
        queried = http.post("/chat", json={"message": "查询退款进度"})
        assert queried.status_code == 200
        trace = runtime.get_tool_trace(queried.json()["request_id"])
        assert trace["tool_calls"][0]["result_success"] is True
        assert trace["tool_calls"][0]["business_result"]["status"] == "pending"
        assert len(service._executor._backend.calls) == 1
