from tests.auth_helpers import customer, reviewer
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from actions import (
    ActionService,
    ActionStatus,
    ActionType,
    InMemoryBusinessActionBackend,
    InMemoryActionStore,
)
from actions.backend import ActionBackendError
from agents.agent_orchestrator import BillingAgent, Request
from agents.tools import build_action_tools
from core.harness import HarnessConfig
from core.intent_recognizer import IntentCategory, UrgencyLevel
from providers.mock_backend import InMemoryBusinessBackend


FIXTURE = Path(__file__).parent / "fixtures" / "business_provider_data.json"
NOW = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)


def raw_data(*, refunds=True, status="shipped", total="129.90"):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["orders"]["ORD-1001"]["status"] = status
    data["orders"]["ORD-1001"]["total_amount"] = total
    if not refunds:
        data["refunds"] = {}
    return data


def make_service(*, refunds=False, status="shipped", total="129.90", fail_operations=(), backend=None, store=None):
    data = raw_data(refunds=refunds, status=status, total=total)
    read_backend = InMemoryBusinessBackend(data)
    action_backend = backend or InMemoryBusinessActionBackend(read_backend.state, fail_operations=fail_operations)
    return ActionService(
        business_backend=read_backend,
        action_backend=action_backend,
        store=store,
        clock=lambda: NOW,
    ), action_backend


def test_refund_allow_executes_once():
    service, backend = make_service(refunds=False)

    result = service.request_refund(
        order_id="ORD-1001", user_id="customer-1", request_id="req-1"
    , principal=customer('customer-1'))

    assert result.status is ActionStatus.COMPLETED
    assert result.action.policy_decision.reason_code == "refund_eligible"
    assert result.action.policy_version == "refund-cancel-v1"
    assert result.action.execution_result["simulated"] is True
    assert len(backend.calls) == 1


def test_refund_requires_approval_then_approve_executes():
    service, backend = make_service(refunds=False, total="800.00")

    pending = service.request_refund(
        order_id="ORD-1001",
        user_id="customer-1",
        request_id="req-2",
        amount="600.00",
    principal=customer('customer-1'))
    assert pending.status is ActionStatus.AWAITING_APPROVAL
    assert pending.action.policy_decision.reason_code == "amount_requires_approval"
    assert backend.calls == []

    completed = service.approve(
        action_id=pending.action_id, user_id="customer-1", request_id="approve-1"
    , principal=reviewer('customer-1'))
    assert completed.status is ActionStatus.COMPLETED
    assert len(backend.calls) == 1


def test_reject_is_terminal_and_never_executes():
    service, backend = make_service(refunds=False, total="800.00")
    pending = service.request_refund(
        order_id="ORD-1001", user_id="customer-1", request_id="req-3", amount="600"
    , principal=customer('customer-1'))

    rejected = service.reject(
        action_id=pending.action_id, user_id="customer-1", request_id="reject-1"
    , principal=customer('customer-1'))
    resumed = service.resume(
        action_id=pending.action_id, user_id="customer-1", request_id="resume-1"
    , principal=customer('customer-1'))

    assert rejected.status is ActionStatus.REJECTED
    assert resumed.status is ActionStatus.REJECTED
    assert backend.calls == []


def test_policy_deny_cannot_be_bypassed_by_approval_or_resume():
    service, backend = make_service(refunds=False, status="shipped")
    denied = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-4"
    , principal=customer('customer-1'))

    approved = service.approve(
        action_id=denied.action_id, user_id="customer-1", request_id="approve-2"
    , principal=reviewer('customer-1'))
    resumed = service.resume(
        action_id=denied.action_id, user_id="customer-1", request_id="resume-2"
    , principal=customer('customer-1'))

    assert denied.status is ActionStatus.REJECTED
    assert denied.action.error_code == "order_status_not_cancellable"
    assert approved.status is ActionStatus.REJECTED
    assert resumed.status is ActionStatus.REJECTED
    assert backend.calls == []


def test_cancel_allowed_for_pending_order():
    service, backend = make_service(refunds=False, status="pending")

    result = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-5"
    , principal=customer('customer-1'))

    assert result.status is ActionStatus.COMPLETED
    assert result.action.action_type is ActionType.CANCEL_ORDER
    assert backend.calls[0]["operation"] == "cancel"


def test_ownership_violation_is_rejected_without_execution():
    service, backend = make_service(refunds=False, status="pending")

    result = service.request_cancel(
        order_id="ORD-1001", user_id="customer-2", request_id="req-6"
    , principal=customer('customer-2'))

    assert result.status is ActionStatus.REJECTED
    assert result.error_code == "unauthorized"
    assert backend.calls == []


def test_same_idempotency_key_returns_existing_action():
    service, backend = make_service(refunds=False, status="pending")
    first = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-7", idempotency_key="idem-7"
    , principal=customer('customer-1'))
    second = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="retry-7", idempotency_key="idem-7"
    , principal=customer('customer-1'))

    assert second.action_id == first.action_id
    assert second.reused is True
    assert len(backend.calls) == 1


def test_idempotency_key_is_scoped_to_user_and_action():
    service, backend = make_service(refunds=False, status="pending")
    first = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-7a", idempotency_key="same"
    , principal=customer('customer-1'))
    other_user = service.request_cancel(
        order_id="ORD-1001", user_id="customer-2", request_id="req-7b", idempotency_key="same"
    , principal=customer('customer-2'))

    assert first.action_id != other_user.action_id
    assert other_user.error_code == "unauthorized"
    assert len(backend.calls) == 1


def test_derived_idempotency_key_deduplicates_agent_retries():
    service, backend = make_service(refunds=False, status="pending")
    first = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-8"
    , principal=customer('customer-1'))
    second = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="retry-8"
    , principal=customer('customer-1'))

    assert second.action_id == first.action_id
    assert second.reused is True
    assert len(backend.calls) == 1


@pytest.mark.parametrize("key_kind", ["external", "internal", "derived"])
def test_n01_same_parameters_reuse_normalized_amount(key_kind):
    service, backend = make_service()
    key = None if key_kind == "derived" else "n01-same"
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-first", amount="10.00", idempotency_key=key, principal=customer('customer-1'))
    retry_key = first.action.idempotency_key if key_kind == "internal" else key
    second = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-retry", amount="1E1", idempotency_key=retry_key, principal=customer('customer-1'))
    assert first.status is second.status is ActionStatus.COMPLETED
    assert second.action_id == first.action_id and second.reused
    assert len(backend.calls) == 1


@pytest.mark.parametrize("key_kind", ["external", "internal"])
@pytest.mark.parametrize("changed", ["amount", "order"])
def test_n01_changed_parameters_conflict_without_old_result(key_kind, changed):
    service, backend = make_service()
    other = dict(service._business_backend._data["orders"]["ORD-1001"])
    other["order_id"] = "ORD-N01"
    service._business_backend._data["orders"]["ORD-N01"] = other
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-first", amount="10", idempotency_key="n01-conflict", principal=customer('customer-1'))
    key = first.action.idempotency_key if key_kind == "internal" else "n01-conflict"
    second = service.request_refund(
        order_id="ORD-N01" if changed == "order" else "ORD-1001",
        user_id="customer-1", request_id="n01-change",
        amount="20" if changed == "amount" else "10", idempotency_key=key, principal=customer('customer-1'))
    assert not second.success and second.error_code == "idempotency_conflict"
    assert second.action is None and second.action_id is None and not second.reused
    assert len(backend.calls) == 1
    assert service.get(action_id=first.action_id, user_id="customer-1", principal=customer('customer-1')).action.amount == Decimal("10")


@pytest.mark.parametrize("order_id", ["ORD-1001", "ORD-N01-OTHER"])
def test_n01_cross_user_internal_key_does_not_disclose_action(order_id):
    service, backend = make_service()
    other = dict(service._business_backend._data["orders"]["ORD-1001"])
    other.update(order_id="ORD-N01-OTHER", customer_id="customer-2")
    service._business_backend._data["orders"]["ORD-N01-OTHER"] = other
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-first", amount="10", idempotency_key="n01-private", principal=customer('customer-1'))
    result = service.request_refund(order_id=order_id, user_id="customer-2",
        request_id="n01-other", amount="10", idempotency_key=first.action.idempotency_key, principal=customer('customer-2'))
    assert not result.success and result.error_code == "unauthorized"
    payload = json.dumps(result.to_tool_result())
    assert first.action_id not in payload and "customer-1" not in payload
    assert first.action.idempotency_key not in payload
    assert len(backend.calls) == 1


def test_n01_concurrent_duplicates_execute_once():
    service, backend = make_service()
    start = Barrier(8)
    def request(index):
        start.wait(timeout=5)
        return service.request_refund(order_id="ORD-1001", user_id="customer-1",
            request_id=f"n01-thread-{index}", amount="10.00", idempotency_key="n01-parallel", principal=customer('customer-1'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(request, range(8)))
    assert all(result.status is ActionStatus.COMPLETED for result in results)
    assert len({result.action_id for result in results}) == 1
    assert sum(not result.reused for result in results) == 1
    assert len(backend.calls) == 1


def test_n01_internal_key_cannot_reuse_another_action_type():
    service, backend = make_service(status="pending")
    first = service.request_cancel(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-cancel", idempotency_key="n01-kind", principal=customer('customer-1'))
    result = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-refund", idempotency_key=first.action.idempotency_key, principal=customer('customer-1'))
    assert result.error_code == "idempotency_conflict" and result.action is None
    assert len(backend.calls) == 1


def test_n01_pending_retry_does_not_bypass_approval():
    service, backend = make_service(total="800.00")
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-pending", amount="600", idempotency_key="n01-approval", principal=customer('customer-1'))
    retry = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-pending-retry", amount="600.00", idempotency_key="n01-approval", principal=customer('customer-1'))
    conflict = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-lower", amount="10", idempotency_key="n01-approval", principal=customer('customer-1'))
    assert retry.status is ActionStatus.AWAITING_APPROVAL and retry.reused
    assert retry.action_id == first.action_id
    assert conflict.error_code == "idempotency_conflict" and conflict.action is None
    assert backend.calls == []


def test_n01_rejected_retry_preserves_original_key_binding():
    service, backend = make_service()
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-bound", amount="10", idempotency_key="n01-binding", principal=customer('customer-1'))
    rejected = service.request_refund(order_id="ORD-MISSING", user_id="customer-1",
        request_id="n01-missing", amount="10", idempotency_key="n01-binding", principal=customer('customer-1'))
    assert rejected.error_code == "not_found" and rejected.action is None
    retry = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-bound-retry", amount="10", idempotency_key="n01-binding", principal=customer('customer-1'))
    assert retry.reused and retry.action_id == first.action_id
    assert len(backend.calls) == 1


def test_n01_omitted_amount_matches_effective_total():
    service, backend = make_service(total="100.00")
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-total", idempotency_key="n01-total-key", principal=customer('customer-1'))
    retry = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n01-total-retry", amount="1E2", idempotency_key="n01-total-key", principal=customer('customer-1'))
    assert retry.reused and retry.action_id == first.action_id
    assert len(backend.calls) == 1


def test_duplicate_approval_and_resume_do_not_execute_twice():
    service, backend = make_service(refunds=False, total="800.00")
    pending = service.request_refund(
        order_id="ORD-1001", user_id="customer-1", request_id="req-9", amount="600"
    , principal=customer('customer-1'))
    first = service.approve(
        action_id=pending.action_id, user_id="customer-1", request_id="approve-9"
    , principal=reviewer('customer-1'))
    second = service.approve(
        action_id=pending.action_id, user_id="customer-1", request_id="approve-9-retry"
    , principal=reviewer('customer-1'))
    resumed = service.resume(
        action_id=pending.action_id, user_id="customer-1", request_id="resume-9"
    , principal=customer('customer-1'))

    assert first.status is ActionStatus.COMPLETED
    assert second.reused is True
    assert resumed.reused is True
    assert len(backend.calls) == 1


def test_policy_is_rechecked_before_approved_execution():
    service, backend = make_service(refunds=False, total="800.00")
    pending = service.request_refund(
        order_id="ORD-1001", user_id="customer-1", request_id="req-10", amount="600"
    , principal=customer('customer-1'))
    # Simulate authoritative state changing while approval is pending.
    service._business_backend._data["orders"]["ORD-1001"]["status"] = "cancelled"

    result = service.approve(
        action_id=pending.action_id, user_id="customer-1", request_id="approve-10"
    , principal=reviewer('customer-1'))

    assert result.status is ActionStatus.REJECTED
    assert result.action.error_code == "policy_changed"
    assert backend.calls == []


def test_dependency_failure_is_persisted_without_execution():
    service, backend = make_service(refunds=False, status="pending", fail_operations={"execute_cancel"})

    result = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-11"
    , principal=customer('customer-1'))

    assert result.status is ActionStatus.FAILED
    assert result.error_code == "dependency_failure"
    assert backend.calls == []


def test_action_backend_failure_is_persisted():
    class FailingBackend(InMemoryBusinessActionBackend):
        def execute_cancel(self, *args, **kwargs):
            raise ActionBackendError("gateway_failure", "模拟动作后端失败")

    service, backend = make_service(
        refunds=False, status="pending", backend=FailingBackend(raw_data(refunds=False, status="pending"))
    )
    result = service.request_cancel(
        order_id="ORD-1001", user_id="customer-1", request_id="req-12"
    , principal=customer('customer-1'))

    assert result.status is ActionStatus.FAILED
    assert result.error_code == "gateway_failure"


def test_illegal_state_transition_is_rejected():
    service, _ = make_service(refunds=False, total="800.00")
    pending = service.request_refund(
        order_id="ORD-1001", user_id="customer-1", request_id="req-13", amount="600"
    , principal=customer('customer-1'))
    pending.action.status = ActionStatus.PENDING
    result = service.reject(
        action_id=pending.action_id, user_id="customer-1", request_id="reject-13"
    , principal=customer('customer-1'))

    assert result.status is ActionStatus.PENDING
    assert result.error_code == "invalid_state_transition"


class _ToolUseBlock:
    type = "tool_use"
    id = "toolu_refund_1"
    name = "request_refund"
    input = {"order_id": "ORD-1001"}


class _TextBlock:
    type = "text"
    text = "退款请求已进入处理流程。"


class _WriteToolClient:
    def __init__(self):
        self.calls = []
        self.responses = [
            type("Response", (), {"content": [_ToolUseBlock()]})(),
            type("Response", (), {"content": [_TextBlock()]})(),
        ]

    class Messages:
        def __init__(self, owner):
            self.owner = owner

        async def create(self, **kwargs):
            self.owner.calls.append(kwargs)
            return self.owner.responses.pop(0)

    @property
    def messages(self):
        return self.Messages(self)


def test_agent_write_tool_round_trip_uses_action_service():
    service, backend = make_service(refunds=False)
    client = _WriteToolClient()
    agent = BillingAgent(client, "test-model")
    agent.set_shared_tools(build_action_tools(service))
    request = Request(
        message="申请退款",
        user_id="customer-1",
        conv_id="conv-write",
        request_id="req-agent-write",
        intent=IntentCategory.REFUND,
        intent_group="billing",
        urgency=UrgencyLevel.MEDIUM,
    principal=customer('customer-1'))

    response = asyncio.run(agent.handle(request))

    assert response.success is True
    assert response.tools_used == ["request_refund"]
    assert len(backend.calls) == 1
    tool_payload = json.loads(client.calls[1]["messages"][-1]["content"][0]["content"])
    assert tool_payload["status"] == "completed"
    assert tool_payload["action"]["policy_version"] == "refund-cancel-v1"
    assert response.tool_traces[0]["action_result"]["status"] == "completed"
    assert response.tool_traces[0]["action_result"]["policy_decision"] == "allow"
    assert response.tool_traces[0]["action_result"]["execution_simulated"] is True


def test_agent_max_tool_rounds_returns_observed_action_receipt_once():
    service, backend = make_service(refunds=False)
    client = _WriteToolClient()
    client.responses = [type("Response", (), {"content": [_ToolUseBlock()]})() for _ in range(3)]
    # Repeated identical calls here exercise the round-limit receipt path, not
    # duplicate detection (covered separately in H3-1).
    agent = BillingAgent(client, "test-model", harness=HarnessConfig(duplicate_call_limit=10))
    agent.set_shared_tools(build_action_tools(service))
    response = asyncio.run(agent.handle(Request(
        message="申请退款", user_id="customer-1", conv_id="conv-max-tool",
        request_id="req-max-tool", intent=IntentCategory.REFUND,
    principal=customer('customer-1'))))
    assert response.success is True
    assert "动作已完成" in response.content
    assert len(backend.calls) == 1
    assert response.tools_used == ["request_refund"] * 3
    assert all(trace["action_result"]["status"] == "completed" for trace in response.tool_traces)


def test_agent_model_failure_after_action_preserves_action_receipt_and_trace():
    service, backend = make_service(refunds=False)
    class FailingMessages:
        calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return type("Response", (), {"content": [_ToolUseBlock()]})()
            raise RuntimeError("demo model unavailable after action")

    client = type("FailingClient", (), {"messages": FailingMessages()})()
    agent = BillingAgent(client, "test-model")
    agent.set_shared_tools(build_action_tools(service))
    response = asyncio.run(agent.handle(Request(
        message="申请退款", user_id="customer-1", conv_id="conv-model-fail",
        request_id="req-model-fail", intent=IntentCategory.REFUND,
    principal=customer('customer-1'))))
    assert response.success is True
    assert "动作已完成" in response.content
    assert response.tools_used == ["request_refund"]
    assert len(backend.calls) == 1
