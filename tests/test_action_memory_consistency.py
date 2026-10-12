"""N05 HTTP fault injection: Fake SDK and simulated backend, no live services."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from api import main
from actions.backend import ActionBackendError
from actions.models import ActionResult, ActionStatus
from agents.support_agent import SupportRuntime
from evaluation.prepare_online_eval import prepare
from evaluation.topology_experiment import isolated_business
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient, NOW

pytestmark = pytest.mark.usefixtures("authenticated_http")
MARKER = "SYNTHETIC-SECRET-MEMORY-OUTAGE"


class FaultMemory(EmptyMemory):
    def __init__(self, fail_role=None, read_failure=False, error=RuntimeError):
        super().__init__()
        self.fail_role, self.read_failure, self.error = fail_role, read_failure, error
        self.attempts = []
        self.profiles = 0

    async def get_context(self, *args, **kwargs):
        if self.read_failure:
            raise RedisConnectionError(MARKER)
        return await super().get_context(*args, **kwargs)

    async def add_message(self, *args):
        self.attempts.append(args[2].value)
        if args[2].value == self.fail_role:
            raise self.error(MARKER)
        await super().add_message(*args)

    async def update_profile(self, *args):
        self.profiles += 1


@pytest.fixture
def setup_chat(monkeypatch):
    def setup(memory=None, tool="request_cancel_order", args=None, backend_failure=False):
        tools, service, backend = isolated_business(prepare(NOW)[0], NOW)
        if backend_failure:
            def fail(*args, **kwargs):
                raise ActionBackendError("synthetic_execution_failure", "模拟业务执行失败")
            monkeypatch.setattr(backend, "execute_cancel", fail)
        sdk = FakeClient(tool, args or {"order_id": "ORD-T09-CANCEL"})
        runtime = SupportRuntime("test", "test", client=sdk)
        runtime.set_shared_tools(tools)
        memory = memory or FaultMemory()
        monkeypatch.setattr(main, "_orchestrator", runtime)
        monkeypatch.setattr(main, "_memory", memory)
        monkeypatch.setattr(main, "_action_service", service)
        http = TestClient(main.app, raise_server_exceptions=False,
                          headers={"Authorization": "Bearer test-customer-1"})
        return http, runtime, service, backend, sdk, memory
    return setup


def post(http):
    return http.post("/chat", json={"message": "cancel order", "conv_id": "n05-session"})


def test_normal_action_and_memory_keep_normal_response(setup_chat):
    http, runtime, service, backend, _, memory = setup_chat()
    response = post(http)
    assert response.status_code == 200
    assert response.json()["response"] == "已处理"
    assert len(backend.calls) == 1 and len(memory.writes) == 2
    trace = runtime.get_tool_trace(response.json()["request_id"])
    assert trace["memory"]["write_status"] == "completed"
    assert next(iter(service._store._actions.values())).status.value == "completed"


@pytest.mark.parametrize("role", ["user", "assistant"])
@pytest.mark.parametrize("error", [RuntimeError, RedisConnectionError])
def test_completed_action_survives_post_execution_memory_failure(setup_chat, role, error, caplog):
    http, runtime, service, backend, _, memory = setup_chat(FaultMemory(role, error=error))
    response = post(http)
    action = next(iter(service._store._actions.values()))
    trace = runtime.get_recent_tool_traces()[0]
    # The original audit's observed defect: completed + one execution + HTTP 500.
    assert action.status.value == "completed" and len(backend.calls) == 1
    assert trace["tool_calls"][0]["action_result"]["status"] == "completed"
    assert response.status_code == 200
    body = response.json()
    assert body["memory_write_status"] == "failed"
    assert body["warning_codes"] == ["memory_write_failed"]
    assert body["action_results"][0]["action_id"] == action.action_id
    assert body["action_results"][0]["status"] == "completed"
    assert body["action_results"][0]["action"]["execution_result"]["simulated"] is True
    assert http.get(f"/actions/{action.action_id}").json()["status"] == "completed"
    assert trace["memory"]["write_failed_role"] == role
    assert trace["memory"]["messages_written"] == (0 if role == "user" else 1)
    assert trace["memory"]["error_code"] == "memory_write_failed"
    assert trace["memory"]["profile_update_status"] == "not_scheduled"
    assert "request_latency_ms" in trace and memory.profiles == 0
    assert "memory_write_failed" in caplog.text
    assert MARKER not in json.dumps(body) + json.dumps(trace) + caplog.text


@pytest.mark.parametrize("role", [None, "user"])
def test_backend_failure_is_not_a_completed_receipt(setup_chat, role):
    http, runtime, service, backend, _, _ = setup_chat(FaultMemory(role), backend_failure=True)
    response = post(http)
    action = next(iter(service._store._actions.values()))
    assert action.status.value == "failed" and action.execution_result is None
    assert runtime.get_recent_tool_traces()[0]["tool_calls"][0]["action_result"]["status"] == "failed"
    if role:
        assert response.status_code == 500
    else:
        assert response.status_code == 200
        assert not response.json()["action_results"][0]["success"]
        assert response.json()["action_results"][0]["status"] == "failed"


def test_read_failure_stops_model_and_action(setup_chat):
    http, _, service, backend, sdk, memory = setup_chat(FaultMemory(read_failure=True))
    response = post(http)
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "memory_unavailable"
    assert sdk.calls == [] and backend.calls == [] and not service._store._actions
    assert memory.attempts == []


@pytest.mark.parametrize("explicit_key", [False, True])
def test_retry_reuses_n01_action_without_second_execution(setup_chat, explicit_key):
    args = {"order_id": "ORD-T09-CANCEL"}
    if explicit_key:
        args["idempotency_key"] = "n05-repeat"
    http, runtime, service, backend, sdk, _ = setup_chat(FaultMemory("assistant"), args=args)
    first = post(http)
    sdk.responses = FakeClient("request_cancel_order", args).responses
    second = post(http)
    assert first.status_code == second.status_code == 200
    assert first.json()["action_results"][0]["action_id"] == second.json()["action_results"][0]["action_id"]
    assert second.json()["action_results"][0]["reused"] is True
    assert len(backend.calls) == len(service._store._actions) == 1


def test_read_only_write_failure_is_not_silently_accepted(setup_chat):
    http, runtime, service, backend, _, _ = setup_chat(FaultMemory("user"), tool="get_order",
                                                     args={"order_id": "ORD-T09-ORDER"})
    response = post(http)
    assert response.status_code == 500 and not backend.calls and not service._store._actions
    assert runtime.get_recent_tool_traces()[0]["memory"]["write_status"] == "failed"


def test_pending_approval_write_failure_does_not_execute(setup_chat):
    http, _, service, backend, _, _ = setup_chat(FaultMemory("user"), tool="request_refund",
        args={"order_id": "ORD-T09-REFUND-APPROVAL", "amount": 600})
    assert post(http).status_code == 500
    action = next(iter(service._store._actions.values()))
    assert action.status.value == "awaiting_approval" and not backend.calls
    assert http.post(f"/actions/{action.action_id}/approve", json={}).status_code == 403
    assert action.status.value == "awaiting_approval" and not backend.calls


@pytest.mark.parametrize("headers,body,status", [
    ({"Authorization": ""}, {}, 401),
    ({"Authorization": "Bearer test-customer-1"}, {"user_id": "customer-2"}, 403),
    ({"Authorization": "Bearer test-reviewer"}, {}, 403),
])
def test_authentication_before_new_error_handling(setup_chat, headers, body, status):
    http, _, service, backend, sdk, memory = setup_chat(FaultMemory("user"))
    response = http.post("/chat", headers=headers, json={"message": "cancel", **body})
    assert response.status_code == status
    assert not sdk.calls and not backend.calls and not service._store._actions and not memory.attempts


def test_model_failure_without_action_is_not_memory_degradation(setup_chat):
    http, runtime, service, backend, sdk, memory = setup_chat(FaultMemory("user"))
    async def fail(**kwargs):
        raise RuntimeError("synthetic model outage")
    sdk.create = fail
    assert post(http).status_code == 500
    assert not backend.calls and not service._store._actions
    assert runtime.get_recent_tool_traces()[0]["tool_calls"] == []


def test_unconfirmed_store_receipt_cannot_enable_success(setup_chat, monkeypatch):
    http, runtime, service, backend, _, _ = setup_chat(FaultMemory("user"))
    monkeypatch.setattr(service, "get", lambda *args, **kwargs:
        ActionResult(success=False, status=ActionStatus.FAILED, error_code="not_found"))
    assert post(http).status_code == 500
    assert len(backend.calls) == 1
    assert runtime.get_recent_tool_traces()[0]["memory"]["write_status"] == "failed"


@pytest.mark.parametrize("missing", ["execution_result", "status"])
def test_inconsistent_receipt_cannot_enable_success(setup_chat, monkeypatch, missing):
    http, _, service, backend, _, _ = setup_chat(FaultMemory("user"))
    original = service.get
    def inconsistent(*args, **kwargs):
        receipt = original(*args, **kwargs)
        changes = {"execution_result": None} if missing == "execution_result" else {"status": "executing"}
        return receipt.model_copy(update={"action": receipt.action.model_copy(update=changes),
            **({"status": ActionStatus.EXECUTING}
               if missing == "status" else {})})
    monkeypatch.setattr(service, "get", inconsistent)
    assert post(http).status_code == 500 and len(backend.calls) == 1


def test_multiple_actions_preserve_completed_and_pending_separately(setup_chat):
    http, runtime, service, backend, sdk, _ = setup_chat(FaultMemory("assistant"))
    sdk.responses[0].content.append(SimpleNamespace(type="tool_use", id="t2", name="request_refund",
        input={"order_id": "ORD-T09-REFUND-APPROVAL", "amount": 600}))
    body = post(http).json()
    assert [r["status"] for r in body["action_results"]] == ["completed", "awaiting_approval"]
    assert len(backend.calls) == 1 and len(service._store._actions) == 2
    assert body["memory_write_status"] == "failed"
    assert [t["action_result"]["status"] for t in runtime.get_recent_tool_traces()[0]["tool_calls"]] == [
        "completed", "awaiting_approval"]


def test_model_failure_after_completed_action_retains_actual_receipt(setup_chat):
    http, _, service, backend, sdk, _ = setup_chat(FaultMemory("assistant"))
    # A later model step fails; existing BaseAgent recovery uses the observed receipt.
    sdk.responses = sdk.responses[:1]
    response = post(http)
    assert response.status_code == 200 and len(backend.calls) == 1
    assert response.json()["action_results"][0]["status"] == "completed"
    assert next(iter(service._store._actions)) in response.json()["response"]


def test_cross_customer_action_cannot_enable_memory_degradation(setup_chat):
    http, _, service, backend, _, _ = setup_chat(FaultMemory("user"))
    response = http.post("/chat", headers={"Authorization": "Bearer test-customer-2"},
                         json={"message": "cancel order"})
    assert response.status_code == 500 and not backend.calls
    assert all(action.status.value != "completed" for action in service._store._actions.values())
