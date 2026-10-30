"""H4-2 opt-in crash test: kill a real process at four recovery windows."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import pytest
import redis

pytestmark = pytest.mark.usefixtures("authenticated_http")

from fastapi.testclient import TestClient

from actions import (
    ActionService, ActionStatus, InMemoryBusinessActionBackend,
    RedisActionStore, RedisCheckpointStore,
)
from api import main
from core.checkpoint import CheckpointService
from core.checkpoint_resume import CheckpointResumer
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer, reviewer

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
FIXTURE = ROOT / "evaluation/h2_3/fixture.json"
ORDER = "ORD-H23-APPROVAL-1"
USER = "customer-1"
POINTS = [
    "before_approval",
    "during_approval",
    "during_execution",
    "after_receipt",
    "after_execution",
    "after_memory",
]


def _redis_url() -> str:
    configured = urlsplit(os.environ["REDIS_URL"])
    auth = (configured.netloc.rsplit("@", 1)[0] + "@"
            if "@" in configured.netloc else "")
    return urlunsplit((configured.scheme, f"{auth}127.0.0.1:6379",
                       configured.path, configured.query, configured.fragment))


def _service(store):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    read = InMemoryBusinessBackend(fixture)
    write = InMemoryBusinessActionBackend(read.state)
    service = ActionService(business_backend=read, action_backend=write,
                            store=store, clock=lambda: NOW)
    return service, write


def _memory_manager(url: str):
    """Real MemoryManager.add_message_once against Redis; Chroma is not used."""
    from memory.conversation_memory import MemoryManager
    import redis.asyncio as aioredis

    memory = MemoryManager.__new__(MemoryManager)
    memory._redis = aioredis.from_url(url, decode_responses=True)
    memory._context_compression = False
    return memory


def _wm_key(conv_id: str) -> str:
    return f"wm:{quote(USER, safe='')}:{quote(conv_id, safe='')}"


def _once_pattern(conv_id: str) -> str:
    return f"wm:once:{quote(USER, safe='')}:{quote(conv_id, safe='')}:*"


def _run_child(point: str, env: dict, ready: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.h4_2_child"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 30
    try:
        while time.time() < deadline:
            if ready.exists():
                break
            if proc.poll() is not None:
                _, err = proc.communicate()
                pytest.fail(f"{point}: child exited before crash point: {err[-800:]}")
            time.sleep(0.05)
        else:
            pytest.fail(f"{point}: child did not reach crash point")
        proc.kill()
        _, err = proc.communicate(timeout=10)
        assert proc.returncode != 0, err
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


def _resume(url: str, checkpoints, service, request_id: str):
    async def run():
        memory = _memory_manager(url)
        try:
            resumer = CheckpointResumer(checkpoints, service, memory)
            return await resumer.resume(
                request_id, user_id=USER, principal=customer(USER))
        finally:
            await memory._redis.aclose()
    return asyncio.run(run())


def _http(monkeypatch, service, checkpoints):
    monkeypatch.setattr(main, "_action_service", service)
    monkeypatch.setattr(main, "_checkpoint_service", checkpoints)
    return TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"})


@pytest.mark.skipif(
    os.getenv("CARTCARE_TEST_LIVE_ACTIONS") != "1" or not os.getenv("REDIS_URL"),
    reason="requires live Redis and CARTCARE_TEST_LIVE_ACTIONS=1")
def test_memory_add_message_once_is_atomic_and_idempotent():
    url = _redis_url()
    suffix = uuid.uuid4().hex
    user_id = f"h42-user-{suffix}"
    conv_id = f"conv-h42-memory-{suffix}"
    cleanup = redis.Redis.from_url(url, decode_responses=True)
    try:
        async def run():
            from memory.conversation_memory import MsgRole
            memory = _memory_manager(url)
            try:
                first = await memory.add_message_once(
                    user_id, conv_id, MsgRole.ASSISTANT, "恢复回执",
                    metadata={"source": "checkpoint_resume"},
                    idempotency_key="checkpoint_resume:req-memory")
                second = await memory.add_message_once(
                    user_id, conv_id, MsgRole.ASSISTANT, "恢复回执",
                    metadata={"source": "checkpoint_resume"},
                    idempotency_key="checkpoint_resume:req-memory")
                return first, second
            finally:
                await memory._redis.aclose()

        assert asyncio.run(run()) == (True, False)
        key = f"wm:{quote(user_id, safe='')}:{quote(conv_id, safe='')}"
        assert cleanup.llen(key) == 1
        once_pattern = f"wm:once:{quote(user_id, safe='')}:{quote(conv_id, safe='')}:*"
        assert len(list(cleanup.scan_iter(match=once_pattern))) == 1

        async def delete():
            from types import SimpleNamespace
            memory = _memory_manager(url)
            memory._episodic = SimpleNamespace(delete=lambda **kwargs: None)
            try:
                await memory.delete_session(user_id, conv_id)
            finally:
                await memory._redis.aclose()

        asyncio.run(delete())
        assert cleanup.llen(key) == 0
        assert list(cleanup.scan_iter(match=once_pattern)) == []
    finally:
        for pattern in (
            f"wm:{quote(user_id, safe='')}:{quote(conv_id, safe='')}",
            f"summary:{quote(user_id, safe='')}:{quote(conv_id, safe='')}",
            f"wm:once:{quote(user_id, safe='')}:{quote(conv_id, safe='')}:*",
        ):
            for key in cleanup.scan_iter(match=pattern):
                cleanup.delete(key)
        cleanup.close()


@pytest.mark.skipif(
    os.getenv("CARTCARE_TEST_LIVE_ACTIONS") != "1" or not os.getenv("REDIS_URL"),
    reason="requires live Redis and CARTCARE_TEST_LIVE_ACTIONS=1")
@pytest.mark.parametrize("point", POINTS)
def test_process_crash_recovery(point, monkeypatch, tmp_path):
    url = _redis_url()
    suffix = uuid.uuid4().hex
    action_prefix = f"h42-actions-{suffix}"
    checkpoint_prefix = f"h42-checkpoints-{suffix}"
    request_id = f"req-h42-{suffix}"
    conv_id = f"conv-h42-{suffix}"
    ready = tmp_path / f"{point}.ready"
    cleanup = redis.Redis.from_url(url, decode_responses=True)
    env = {
        **os.environ,
        "H42_POINT": point,
        "H42_REQUEST": request_id,
        "H42_CONV": conv_id,
        "H42_REDIS_URL": url,
        "H42_APREFIX": action_prefix,
        "H42_CPREFIX": checkpoint_prefix,
        "H42_FIXTURE": str(FIXTURE),
        "H42_READY": str(ready),
    }
    try:
        _run_child(point, env, ready)

        store = RedisActionStore(url, prefix=action_prefix)
        checkpoint_store = RedisCheckpointStore(url, prefix=checkpoint_prefix)
        try:
            service, backend = _service(store)
            checkpoints = CheckpointService(checkpoint_store)
            checkpoint = checkpoints.get(request_id)
            assert checkpoint is not None
            action_id = checkpoint.actions[0].action_id
            action = service.get(action_id, user_id=USER, principal=customer(USER))

            http = _http(monkeypatch, service, checkpoints)
            before = http.get(f"/checkpoints/{request_id}").json()

            if point == "before_approval":
                assert action.status is ActionStatus.AWAITING_APPROVAL
                assert before["status"] == "awaiting_approval"
                approved = service.approve(
                    action_id=action_id, user_id=USER, request_id=request_id,
                    principal=reviewer(USER))
                assert approved.status is ActionStatus.COMPLETED
                assert len(backend.calls) == 1
                expected = "completed"
            elif point == "during_approval":
                assert action.status is ActionStatus.APPROVED
                assert before["status"] == "executing"
                expected = "completed"
            elif point == "during_execution":
                assert action.status is ActionStatus.EXECUTING
                assert action.action.execution_attempted_at is not None
                assert action.action.execution_result is None
                assert before["status"] == "executing"
                expected = "failed"
            elif point == "after_receipt":
                assert action.status is ActionStatus.EXECUTING
                assert action.action.execution_result is not None
                assert before["status"] == "executing"
                expected = "completed"
            elif point == "after_execution":
                assert action.status is ActionStatus.COMPLETED
                assert before["status"] == "completed"
                expected = "completed"
            else:  # after_memory
                assert action.status is ActionStatus.COMPLETED
                assert before["status"] == "completed"
                assert cleanup.llen(_wm_key(conv_id)) == 1
                expected = "completed"

            outcome = _resume(url, checkpoints, service, request_id)
            assert outcome is not None
            assert outcome.status == expected
            assert checkpoints.get(request_id).resumed_at is not None

            if point in {"before_approval", "during_approval"}:
                assert len(backend.calls) == 1
                assert outcome.memory_write_status == "completed"
            elif point == "during_execution":
                assert len(backend.calls) == 0
                assert outcome.memory_write_status == "completed"
                assert "execution_unknown" in outcome.response
            else:
                assert len(backend.calls) == 0
                if point == "after_memory":
                    assert outcome.memory_write_status == "already_written"
                else:
                    assert outcome.memory_write_status == "completed"

            final = http.get(f"/checkpoints/{request_id}").json()
            assert final["status"] == expected
            receipt = http.get(f"/actions/{action_id}").json()
            assert receipt["status"] == expected
            assert cleanup.llen(_wm_key(conv_id)) == 1
        finally:
            store.close()
            checkpoint_store.close()
    finally:
        for pattern in (
            f"{action_prefix}:*", f"{checkpoint_prefix}:*",
            _wm_key(conv_id), f"summary:{quote(USER, safe='')}:{quote(conv_id, safe='')}",
            _once_pattern(conv_id),
        ):
            for key in cleanup.scan_iter(match=pattern):
                cleanup.delete(key)
        cleanup.close()
