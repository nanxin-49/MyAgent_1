"""H4-1: durable action checkpoints, owner visibility, and resume behavior."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("authenticated_http")

from fastapi.testclient import TestClient

from actions.models import ActionStatus
from agents.support_agent import SupportResult
from api import main
from core.checkpoint import (
    ActionCheckpoint, CheckpointAction, CheckpointService, CheckpointStatus,
    InMemoryCheckpointStore, checkpoint_status,
)
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


class RecordingMemory(EmptyMemory):
    async def add_message(self, *args, **kwargs):
        await super().add_message(*args)


def business():
    fixture = json.loads((ROOT / "evaluation/h2_3/fixture.json").read_text(encoding="utf-8"))
    return isolated_business(fixture, NOW)


def awaiting_refund():
    _, service, backend = business()
    result = service.request_refund(
        order_id="ORD-H23-APPROVAL-1", user_id="customer-1", request_id="req-h41",
        amount="800.00", principal=customer("customer-1"))
    assert result.status is ActionStatus.AWAITING_APPROVAL
    return service, backend, result


def result_with(action_result, request_id="req-h41"):
    return SupportResult(
        request_id=request_id, response="等待审批", escalated=False, latency_ms=0,
        tools_used=["request_refund"],
        tool_traces=[{"tool_name": "request_refund", "action_result": action_result}],
        model_calls=[], steps=[{"step": 1, "tools": [{"tool_name": "request_refund"}],
                                "stop_reason": None}],
        stop_reason="awaiting_approval",
    )


def action_payload(result):
    return {"action_id": result.action_id, "status": result.status.value,
            "error_code": result.error_code}


def test_record_result_only_creates_checkpoint_for_awaiting_action():
    service = CheckpointService(InMemoryCheckpointStore())
    awaiting = service.record_result(
        result_with({"action_id": "a1", "status": "awaiting_approval"}),
        conv_id="conv-1", user_id="customer-1")
    assert awaiting is not None
    assert awaiting.status is CheckpointStatus.AWAITING_APPROVAL
    assert [item.action_id for item in awaiting.actions] == ["a1"]
    assert awaiting.remaining_actions == ["a1"]
    assert awaiting.steps and "prompt" not in json.dumps(
        awaiting.model_dump(mode="json"), ensure_ascii=False)
    completed = service.record_result(
        result_with({"action_id": "a2", "status": "completed"}),
        conv_id="conv-2", user_id="customer-1")
    assert completed is None


def test_update_for_action_recomputes_status_and_is_idempotent():
    store = InMemoryCheckpointStore()
    service = CheckpointService(store)
    checkpoint = service.record_result(
        result_with({"action_id": "a1", "status": "awaiting_approval"}),
        conv_id="conv-1", user_id="customer-1")
    assert service.update_for_action("a1", "completed").status is CheckpointStatus.COMPLETED
    assert service.update_for_action("a1", "completed").status is CheckpointStatus.COMPLETED
    assert service.update_for_action("missing", "completed") is None

    two = service.record_result(
        SupportResult(
            request_id="req-two", response="", escalated=False, latency_ms=0,
            tools_used=["request_refund", "request_cancel_order"],
            tool_traces=[
                {"tool_name": "request_refund",
                 "action_result": {"action_id": "a2", "status": "awaiting_approval"}},
                {"tool_name": "request_cancel_order",
                 "action_result": {"action_id": "a3", "status": "awaiting_approval"}},
            ],
            model_calls=[], steps=[]),
        conv_id="conv-2", user_id="customer-1")
    assert two.status is CheckpointStatus.AWAITING_APPROVAL
    assert two.remaining_actions == ["a2", "a3"]
    partial = service.update_for_action("a2", "completed")
    assert partial.status is CheckpointStatus.AWAITING_APPROVAL
    terminal = service.update_for_action("a3", "rejected", "approval_rejected")
    assert terminal.status is CheckpointStatus.PARTIAL_COMPLETED
    assert terminal.remaining_actions == []


def test_checkpoint_status_combinations():
    def actions(*statuses):
        return [CheckpointAction(action_id=f"a{i}", tool_name="request_refund",
                                 status=status) for i, status in enumerate(statuses)]
    assert checkpoint_status(actions("awaiting_approval", "completed")) is CheckpointStatus.AWAITING_APPROVAL
    assert checkpoint_status(actions("approved")) is CheckpointStatus.EXECUTING
    assert checkpoint_status(actions("completed", "completed")) is CheckpointStatus.COMPLETED
    assert checkpoint_status(actions("rejected")) is CheckpointStatus.REJECTED
    assert checkpoint_status(actions("failed", "rejected")) is CheckpointStatus.FAILED


def test_http_checkpoint_is_owner_only_and_resume_is_idempotent(monkeypatch):
    service, backend, action = awaiting_refund()
    checkpoint_service = CheckpointService(InMemoryCheckpointStore())
    checkpoint_service.record_result(
        result_with(action_payload(action)), conv_id="conv-h41", user_id="customer-1")
    memory = RecordingMemory()
    monkeypatch.setattr(main, "_action_service", service)
    monkeypatch.setattr(main, "_checkpoint_service", checkpoint_service)
    monkeypatch.setattr(main, "_memory", memory)

    customer_http = TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})
    other_http = TestClient(main.app, headers={"Authorization": "Bearer test-customer-2"})
    reviewer_http = TestClient(main.app, headers={"Authorization": "Bearer test-reviewer"})

    assert other_http.get("/checkpoints/req-h41").status_code == 404
    checkpoint = customer_http.get("/checkpoints/req-h41").json()
    assert checkpoint["status"] == "awaiting_approval"
    assert checkpoint["remaining_actions"] == [action.action_id]

    waiting = customer_http.post("/checkpoints/req-h41/resume").json()
    assert waiting["status"] == "awaiting_approval"
    assert waiting["memory_write_status"] == "not_attempted"
    assert memory.writes == []

    approved = reviewer_http.post(
        f"/actions/{action.action_id}/approve",
        json={"user_id": "customer-1", "request_id": "req-h41"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"
    assert len(backend.calls) == 1
    assert customer_http.get("/checkpoints/req-h41").json()["status"] == "completed"

    resumed = customer_http.post("/checkpoints/req-h41/resume").json()
    assert resumed["status"] == "completed"
    assert resumed["memory_write_status"] == "completed"
    assert "已完成" in resumed["response"]
    assert len(memory.writes) == 1
    again = customer_http.post("/checkpoints/req-h41/resume").json()
    assert again["already_resumed"] is True
    assert again["memory_write_status"] == "already_resumed"
    assert len(memory.writes) == 1


def test_chat_creates_checkpoint_for_awaiting_action(monkeypatch):
    from agents.support_agent import SupportRuntime
    tools, service, _ = business()
    client = FakeClient("request_refund",
                        {"order_id": "ORD-H23-APPROVAL-1", "amount": 800})
    runtime = SupportRuntime("test", "test", client=client)
    runtime.set_shared_tools(tools)
    checkpoint_service = CheckpointService(InMemoryCheckpointStore())
    memory = RecordingMemory()
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_action_service", service)
    monkeypatch.setattr(main, "_checkpoint_service", checkpoint_service)
    monkeypatch.setattr(main, "_memory", memory)
    http = TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})
    body = http.post("/chat", json={"message": "退款", "conv_id": "conv-chat-h41"}).json()
    checkpoint = http.get(f"/checkpoints/{body['request_id']}").json()
    assert checkpoint["conv_id"] == "conv-chat-h41"
    assert checkpoint["status"] == "awaiting_approval"
    assert body["action_results"][0]["status"] == "awaiting_approval"


def test_memory_failure_keeps_checkpoint_resumable(monkeypatch):
    class BrokenMemory(RecordingMemory):
        async def add_message(self, *args, **kwargs):
            raise RuntimeError("memory unavailable")

    service, _, action = awaiting_refund()
    checkpoint_service = CheckpointService(InMemoryCheckpointStore())
    checkpoint_service.record_result(
        result_with(action_payload(action)), conv_id="conv-h41", user_id="customer-1")
    monkeypatch.setattr(main, "_action_service", service)
    monkeypatch.setattr(main, "_checkpoint_service", checkpoint_service)
    monkeypatch.setattr(main, "_memory", BrokenMemory())
    http = TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})
    reviewer = TestClient(main.app, headers={"Authorization": "Bearer test-reviewer"})
    reviewer.post(f"/actions/{action.action_id}/approve",
                  json={"user_id": "customer-1", "request_id": "req-h41"})
    failed = http.post("/checkpoints/req-h41/resume").json()
    assert failed["memory_write_status"] == "failed"
    assert "已完成" in failed["response"]
    assert checkpoint_service.get("req-h41").resumed_at is None

    memory = RecordingMemory()
    monkeypatch.setattr(main, "_memory", memory)
    retried = http.post("/checkpoints/req-h41/resume").json()
    assert retried["memory_write_status"] == "completed"
    assert retried["already_resumed"] is False
    assert len(memory.writes) == 1
