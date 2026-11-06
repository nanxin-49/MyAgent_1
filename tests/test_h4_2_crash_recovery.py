"""H4-2: deterministic recovery semantics and idempotent resume receipts."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("authenticated_http")

from fastapi.testclient import TestClient

from actions import (
    ActionService, ActionStatus, InMemoryActionStore, InMemoryBusinessActionBackend,
)
from actions.models import PendingAction
from agents.support_agent import SupportResult
from api import main
from core.checkpoint import (
    ActionCheckpoint, CheckpointAction, CheckpointService, CheckpointStatus,
    InMemoryCheckpointStore, reconcile_checkpoint,
)
from core.checkpoint_resume import CheckpointResumer
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer, reviewer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
FIXTURE = ROOT / "evaluation/h2_3/fixture.json"
APPROVAL_ORDER = "ORD-H23-APPROVAL-1"


def service_and_backend(*, store=None):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    read = InMemoryBusinessBackend(fixture)
    write = InMemoryBusinessActionBackend(read.state)
    service = ActionService(business_backend=read, action_backend=write,
                            store=store or InMemoryActionStore(), clock=lambda: NOW)
    return service, write


def awaiting(service):
    result = service.request_refund(
        order_id=APPROVAL_ORDER, user_id="customer-1", request_id="req-h42",
        amount="800.00", principal=customer("customer-1"))
    assert result.status is ActionStatus.AWAITING_APPROVAL
    return result.action


def store_action(service, action: PendingAction, **changes):
    for key, value in changes.items():
        setattr(action, key, value)
    service._store.save(action)
    return action


def result_with(action, request_id="req-h42"):
    return SupportResult(
        request_id=request_id, response="等待审批", escalated=False, latency_ms=0,
        tools_used=["request_refund"],
        tool_traces=[{"tool_name": "request_refund", "action_result": {
            "action_id": action.action_id, "status": action.status.value,
            "error_code": action.error_code}}],
        model_calls=[], steps=[{"step": 1}], stop_reason="awaiting_approval")


def record_checkpoint(checkpoint_service, action, request_id="req-h42"):
    return checkpoint_service.record_result(
        result_with(action, request_id=request_id),
        conv_id="conv-h42", user_id="customer-1")


def resume(service, action_id, request_id="req-h42"):
    return service.resume(action_id=action_id, user_id="customer-1",
                          request_id=request_id, principal=customer("customer-1"))


class RecordingStore(InMemoryActionStore):
    def __init__(self):
        super().__init__()
        self.saves = []

    def save(self, action):
        self.saves.append((action.status.value,
                           action.execution_attempted_at is not None,
                           action.execution_result is not None))
        return super().save(action)


class OnceMemory:
    """Minimal MemoryManager-like double with idempotent append."""

    def __init__(self):
        self.keys = set()
        self.writes = []

    async def add_message_once(self, user_id, conv_id, role, content, metadata=None, *,
                               idempotency_key):
        if idempotency_key in self.keys:
            return False
        self.keys.add(idempotency_key)
        self.writes.append(content)
        return True

    async def add_message(self, *args, **kwargs):
        self.writes.append(args[3] if len(args) > 3 else "")


class PlainMemory:
    def __init__(self):
        self.writes = []

    async def add_message(self, *args, **kwargs):
        self.writes.append(args[3] if len(args) > 3 else "")


def test_execution_persists_dispatch_and_receipt_before_completed():
    store = RecordingStore()
    service, backend = service_and_backend(store=store)
    result = service.request_refund(
        order_id="ORD-H23-ALLOW-1", user_id="customer-1", request_id="req-h42",
        principal=customer("customer-1"))
    assert result.status is ActionStatus.COMPLETED
    assert len(backend.calls) == 1
    assert ("executing", False, False) in store.saves
    assert ("executing", True, False) in store.saves
    assert ("executing", True, True) in store.saves
    assert store.saves[-1] == ("completed", True, True)


def test_executing_with_receipt_completes_without_second_execution():
    service, backend = service_and_backend()
    action = awaiting(service)
    store_action(service, action, status=ActionStatus.EXECUTING,
                 execution_attempted_at=NOW,
                 execution_result={"simulated": True, "status": "completed",
                                   "refund_id": "REF-" + action.action_id})
    resumed = resume(service, action.action_id)
    assert resumed.status is ActionStatus.COMPLETED
    assert resumed.action.execution_result["refund_id"] == "REF-" + action.action_id
    assert backend.calls == []
    again = resume(service, action.action_id)
    assert again.status is ActionStatus.COMPLETED
    assert again.reused is True
    assert backend.calls == []


def test_executing_after_dispatch_without_receipt_fails_unknown():
    service, backend = service_and_backend()
    action = awaiting(service)
    store_action(service, action, status=ActionStatus.EXECUTING,
                 execution_attempted_at=NOW)
    resumed = resume(service, action.action_id)
    assert resumed.status is ActionStatus.FAILED
    assert resumed.error_code == "execution_unknown"
    assert "不能确认" in resumed.message
    assert resumed.action.execution_result is None
    assert backend.calls == []
    again = resume(service, action.action_id)
    assert again.status is ActionStatus.FAILED
    assert again.reused is True
    assert backend.calls == []


def test_executing_before_dispatch_is_retried_once():
    service, backend = service_and_backend()
    action = awaiting(service)
    store_action(service, action, status=ActionStatus.EXECUTING,
                 execution_attempted_at=None)
    resumed = resume(service, action.action_id)
    assert resumed.status is ActionStatus.COMPLETED
    assert resumed.action.execution_result["simulated"] is True
    assert len(backend.calls) == 1


def test_reconcile_checkpoint_projects_observed_status_without_writing():
    checkpoint = ActionCheckpoint(
        request_id="req-h42", conv_id="conv-h42", user_id="customer-1",
        actions=[CheckpointAction(action_id="a1", tool_name="request_refund",
                                  status="awaiting_approval")],
        steps=[], status=CheckpointStatus.AWAITING_APPROVAL,
        remaining_actions=["a1"], created_at=NOW, updated_at=NOW)
    observed = {"a1": ("completed", None)}
    projected = reconcile_checkpoint(checkpoint, observed)
    assert projected.status is CheckpointStatus.COMPLETED
    assert projected.actions[0].status == "completed"
    assert projected.remaining_actions == []
    assert checkpoint.status is CheckpointStatus.AWAITING_APPROVAL


def test_resumer_is_idempotent_with_add_message_once():
    service, backend = service_and_backend()
    action = awaiting(service)
    checkpoints = CheckpointService(InMemoryCheckpointStore())
    record_checkpoint(checkpoints, action)
    approved = service.approve(action_id=action.action_id, user_id="customer-1",
                               request_id="req-h42", principal=reviewer("customer-1"))
    assert approved.status is ActionStatus.COMPLETED
    assert len(backend.calls) == 1

    memory = OnceMemory()
    resumer = CheckpointResumer(checkpoints, service, memory)

    first = asyncio.run(resumer.resume("req-h42", user_id="customer-1",
                                       principal=customer("customer-1")))
    assert first.status == "completed"
    assert first.memory_write_status == "completed"
    assert first.already_resumed is False
    assert len(memory.writes) == 1
    assert checkpoints.get("req-h42").resumed_at is not None

    again = asyncio.run(resumer.resume("req-h42", user_id="customer-1",
                                       principal=customer("customer-1")))
    assert again.status == "completed"
    assert again.already_resumed is True
    assert again.memory_write_status == "already_resumed"
    assert len(memory.writes) == 1
    assert len(backend.calls) == 1


def test_resumer_reports_already_written_after_memory_crash_window():
    service, backend = service_and_backend()
    action = awaiting(service)
    checkpoints = CheckpointService(InMemoryCheckpointStore())
    record_checkpoint(checkpoints, action)
    service.approve(action_id=action.action_id, user_id="customer-1",
                    request_id="req-h42", principal=reviewer("customer-1"))
    memory = OnceMemory()
    # Simulate a prior process that appended the receipt and died before mark_resumed.
    asyncio.run(memory.add_message_once(
        "customer-1", "conv-h42", "assistant", "已写入的回执",
        metadata={"source": "checkpoint_resume"},
        idempotency_key="checkpoint_resume:req-h42"))
    assert len(memory.writes) == 1
    assert checkpoints.get("req-h42").resumed_at is None

    resumer = CheckpointResumer(checkpoints, service, memory)
    outcome = asyncio.run(resumer.resume("req-h42", user_id="customer-1",
                                         principal=customer("customer-1")))
    assert outcome.status == "completed"
    assert outcome.memory_write_status == "already_written"
    assert outcome.already_resumed is False
    assert len(memory.writes) == 1
    assert checkpoints.get("req-h42").resumed_at is not None
    assert len(backend.calls) == 1


def test_resumer_falls_back_when_memory_has_no_add_message_once():
    service, _ = service_and_backend()
    action = awaiting(service)
    checkpoints = CheckpointService(InMemoryCheckpointStore())
    record_checkpoint(checkpoints, action)
    service.approve(action_id=action.action_id, user_id="customer-1",
                    request_id="req-h42", principal=reviewer("customer-1"))
    memory = PlainMemory()
    resumer = CheckpointResumer(checkpoints, service, memory)
    first = asyncio.run(resumer.resume("req-h42", user_id="customer-1",
                                       principal=customer("customer-1")))
    assert first.memory_write_status == "completed"
    assert len(memory.writes) == 1
    again = asyncio.run(resumer.resume("req-h42", user_id="customer-1",
                                       principal=customer("customer-1")))
    assert again.already_resumed is True
    assert len(memory.writes) == 1


def test_get_checkpoint_returns_reconciled_status(monkeypatch):
    service, backend = service_and_backend()
    action = awaiting(service)
    checkpoints = CheckpointService(InMemoryCheckpointStore())
    record_checkpoint(checkpoints, action)
    completed = service.approve(action_id=action.action_id, user_id="customer-1",
                                request_id="req-h42", principal=reviewer("customer-1"))
    assert completed.status is ActionStatus.COMPLETED
    assert checkpoints.get("req-h42").status is CheckpointStatus.AWAITING_APPROVAL

    monkeypatch.setattr(main, "_action_service", service)
    monkeypatch.setattr(main, "_checkpoint_service", checkpoints)
    http = TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})
    body = http.get("/checkpoints/req-h42").json()
    assert body["status"] == "completed"
    assert body["remaining_actions"] == []
    assert checkpoints.get("req-h42").status is CheckpointStatus.AWAITING_APPROVAL
