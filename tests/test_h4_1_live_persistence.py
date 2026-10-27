"""H4-1 opt-in real Redis test: pending action and checkpoint survive a new instance."""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import redis

pytestmark = pytest.mark.usefixtures("authenticated_http")

from fastapi.testclient import TestClient

from actions import ActionService, InMemoryBusinessActionBackend, RedisActionStore, RedisCheckpointStore
from agents.support_agent import SupportResult
from api import main
from core.checkpoint import CheckpointService
from evaluation.topology_experiment import isolated_business
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer
from tests.test_support_production import EmptyMemory

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


class RecordingMemory(EmptyMemory):
    async def add_message(self, *args, **kwargs):
        await super().add_message(*args)


def _redis_url() -> str:
    configured = urlsplit(os.environ["REDIS_URL"])
    auth = (configured.netloc.rsplit("@", 1)[0] + "@"
            if "@" in configured.netloc else "")
    return urlunsplit((configured.scheme, f"{auth}127.0.0.1:6379",
                       configured.path, configured.query, configured.fragment))


def _fixture():
    return json.loads((ROOT / "evaluation/h2_3/fixture.json").read_text(encoding="utf-8"))


def _service(store):
    fixture = _fixture()
    read = InMemoryBusinessBackend(fixture)
    write = InMemoryBusinessActionBackend(read.state)
    return ActionService(business_backend=read, action_backend=write,
                         store=store, clock=lambda: NOW), write


def _result(action, request_id="req-h41-live"):
    return SupportResult(
        request_id=request_id, response="等待审批", escalated=False, latency_ms=0,
        tools_used=["request_refund"],
        tool_traces=[{"tool_name": "request_refund", "action_result": {
            "action_id": action.action_id, "status": action.status.value,
            "error_code": action.error_code}}],
        model_calls=[], steps=[{"step": 1}], stop_reason="awaiting_approval")


@pytest.mark.skipif(
    os.getenv("CARTCARE_TEST_LIVE_ACTIONS") != "1" or not os.getenv("REDIS_URL"),
    reason="requires live Redis and CARTCARE_TEST_LIVE_ACTIONS=1")
def test_real_process_restart_reads_pending_action_and_checkpoint(tmp_path):
    url = _redis_url()
    suffix = uuid.uuid4().hex
    action_prefix = f"h41-proc-actions-{suffix}"
    checkpoint_prefix = f"h41-proc-checkpoints-{suffix}"
    cleanup = redis.Redis.from_url(url, decode_responses=True)
    first_out = tmp_path / "first.json"
    second_out = tmp_path / "second.json"
    env = {
        **os.environ,
        "H41_REDIS_URL": url,
        "H41_APREFIX": action_prefix,
        "H41_CPREFIX": checkpoint_prefix,
        "H41_FIXTURE": str(ROOT / "evaluation/h2_3/fixture.json"),
        "H41_OUT": str(first_out),
    }
    first = """
import json, os
from datetime import datetime, timezone
from pathlib import Path
from actions import ActionService, InMemoryBusinessActionBackend, RedisActionStore, RedisCheckpointStore
from agents.support_agent import SupportResult
from core.checkpoint import CheckpointService
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
fixture = json.loads(Path(os.environ["H41_FIXTURE"]).read_text(encoding="utf-8"))
read = InMemoryBusinessBackend(fixture)
write = InMemoryBusinessActionBackend(read.state)
store = RedisActionStore(os.environ["H41_REDIS_URL"], prefix=os.environ["H41_APREFIX"])
checkpoints = RedisCheckpointStore(os.environ["H41_REDIS_URL"], prefix=os.environ["H41_CPREFIX"])
service = ActionService(business_backend=read, action_backend=write, store=store, clock=lambda: NOW)
action = service.request_refund(order_id="ORD-H23-APPROVAL-1", user_id="customer-1",
                                request_id="req-h41-proc", amount="800.00",
                                principal=customer("customer-1"))
result = SupportResult(request_id="req-h41-proc", response="", escalated=False, latency_ms=0,
    tools_used=["request_refund"],
    tool_traces=[{"tool_name": "request_refund", "action_result": {
        "action_id": action.action_id, "status": action.status.value,
        "error_code": action.error_code}}],
    model_calls=[], steps=[{"step": 1}], stop_reason="awaiting_approval")
CheckpointService(checkpoints).record_result(result, conv_id="conv-h41-proc", user_id="customer-1")
Path(os.environ["H41_OUT"]).write_text(json.dumps({
    "action_id": action.action_id, "request_id": "req-h41-proc",
    "status": action.status.value}), encoding="utf-8")
store.close(); checkpoints.close()
"""
    second = """
import json, os
from datetime import datetime, timezone
from pathlib import Path
from actions import ActionService, InMemoryBusinessActionBackend, RedisActionStore, RedisCheckpointStore
from core.checkpoint import CheckpointService
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer, reviewer
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
data = json.loads(Path(os.environ["H41_IN"]).read_text(encoding="utf-8"))
fixture = json.loads(Path(os.environ["H41_FIXTURE"]).read_text(encoding="utf-8"))
read = InMemoryBusinessBackend(fixture)
write = InMemoryBusinessActionBackend(read.state)
store = RedisActionStore(os.environ["H41_REDIS_URL"], prefix=os.environ["H41_APREFIX"])
checkpoints = RedisCheckpointStore(os.environ["H41_REDIS_URL"], prefix=os.environ["H41_CPREFIX"])
service = ActionService(business_backend=read, action_backend=write, store=store, clock=lambda: NOW)
checkpoint_service = CheckpointService(checkpoints)
before = service.get(data["action_id"], user_id="customer-1", principal=customer("customer-1"))
approved = service.approve(action_id=data["action_id"], user_id="customer-1",
                            request_id="req-h41-proc-approve", principal=reviewer("customer-1"))
checkpoint_service.update_for_action(data["action_id"], approved.status.value, approved.error_code)
after = checkpoint_service.get(data["request_id"])
Path(os.environ["H41_OUT"]).write_text(json.dumps({
    "before": before.status.value, "approved": approved.status.value,
    "checkpoint": after.status.value, "resumed": after.resumed_at is not None,
}), encoding="utf-8")
store.close(); checkpoints.close()
"""
    try:
        first_run = subprocess.run([sys.executable, "-c", first], cwd=ROOT, env=env,
                                   capture_output=True, text=True, timeout=60)
        assert first_run.returncode == 0, first_run.stderr[-1000:]
        assert json.loads(first_out.read_text(encoding="utf-8"))["status"] == "awaiting_approval"
        second_env = {**env, "H41_IN": str(first_out), "H41_OUT": str(second_out)}
        second_run = subprocess.run([sys.executable, "-c", second], cwd=ROOT,
                                    env=second_env, capture_output=True, text=True,
                                    timeout=60)
        assert second_run.returncode == 0, second_run.stderr[-1000:]
        outcome = json.loads(second_out.read_text(encoding="utf-8"))
        assert outcome == {"before": "awaiting_approval", "approved": "completed",
                           "checkpoint": "completed", "resumed": False}
    finally:
        for pattern in (f"{action_prefix}:*", f"{checkpoint_prefix}:*"):
            for key in cleanup.scan_iter(match=pattern):
                cleanup.delete(key)
        cleanup.close()


@pytest.mark.skipif(
    os.getenv("CARTCARE_TEST_LIVE_ACTIONS") != "1" or not os.getenv("REDIS_URL"),
    reason="requires live Redis and CARTCARE_TEST_LIVE_ACTIONS=1")
def test_pending_action_and_checkpoint_survive_new_redis_instances(monkeypatch):
    url = _redis_url()
    suffix = uuid.uuid4().hex
    action_prefix = f"h41-test-actions-{suffix}"
    checkpoint_prefix = f"h41-test-checkpoints-{suffix}"
    cleanup = redis.Redis.from_url(url, decode_responses=True)
    store_a = RedisActionStore(url, prefix=action_prefix)
    checkpoint_a = RedisCheckpointStore(url, prefix=checkpoint_prefix)
    try:
        service_a, backend_a = _service(store_a)
        action = service_a.request_refund(
            order_id="ORD-H23-APPROVAL-1", user_id="customer-1",
            request_id="req-h41-live", amount="800.00",
            principal=customer("customer-1"))
        assert action.status.value == "awaiting_approval"
        checkpoints_a = CheckpointService(checkpoint_a)
        assert checkpoints_a.record_result(
            _result(action), conv_id="conv-h41-live", user_id="customer-1") is not None
        store_a.close()
        checkpoint_a.close()

        # Simulate a fresh process: new stores/services, same Redis state.
        store_b = RedisActionStore(url, prefix=action_prefix)
        checkpoint_b = RedisCheckpointStore(url, prefix=checkpoint_prefix)
        try:
            service_b, backend_b = _service(store_b)
            checkpoint_service_b = CheckpointService(checkpoint_b)
            persisted = service_b.get(action.action_id, user_id="customer-1",
                                      principal=customer("customer-1"))
            assert persisted.status.value == "awaiting_approval"
            assert persisted.action is not None

            memory = RecordingMemory()
            monkeypatch.setattr(main, "_action_service", service_b)
            monkeypatch.setattr(main, "_checkpoint_service", checkpoint_service_b)
            monkeypatch.setattr(main, "_memory", memory)
            customer_http = TestClient(main.app,
                                       headers={"Authorization": "Bearer test-customer-1"})
            reviewer_http = TestClient(main.app,
                                       headers={"Authorization": "Bearer test-reviewer"})
            other_http = TestClient(main.app,
                                    headers={"Authorization": "Bearer test-customer-2"})

            assert other_http.get("/checkpoints/req-h41-live").status_code == 404
            assert customer_http.get("/checkpoints/req-h41-live").json()["status"] == "awaiting_approval"

            approved = reviewer_http.post(
                f"/actions/{action.action_id}/approve",
                json={"user_id": "customer-1", "request_id": "req-h41-live"})
            assert approved.status_code == 200
            assert approved.json()["status"] == "completed"
            assert len(backend_b.calls) == 1

            resumed = customer_http.post("/checkpoints/req-h41-live/resume").json()
            assert resumed["status"] == "completed"
            assert resumed["memory_write_status"] == "completed"
            assert len(memory.writes) == 1
            again = customer_http.post("/checkpoints/req-h41-live/resume").json()
            assert again["already_resumed"] is True
            assert len(memory.writes) == 1

            # The idempotency binding survives the new instance too.
            reused = service_b.request_refund(
                order_id="ORD-H23-APPROVAL-1", user_id="customer-1",
                request_id="req-h41-live-2", amount="800.00",
                principal=customer("customer-1"))
            assert reused.reused is True
            assert len(backend_b.calls) == 1
        finally:
            store_b.close()
            checkpoint_b.close()
        assert not backend_a.calls
    finally:
        for pattern in (f"{action_prefix}:*", f"{checkpoint_prefix}:*"):
            for key in cleanup.scan_iter(match=pattern):
                cleanup.delete(key)
        cleanup.close()
