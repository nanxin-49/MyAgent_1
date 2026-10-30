"""H4-2 child process: stop at a crash point and wait for an external kill."""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from actions import (
    ActionService, ActionStatus, InMemoryBusinessActionBackend,
    RedisActionStore, RedisCheckpointStore,
)
from agents.support_agent import SupportResult
from core.checkpoint import CheckpointService
from core.checkpoint_resume import CheckpointResumer
from providers.mock_backend import InMemoryBusinessBackend
from tests.auth_helpers import customer, reviewer

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
ORDER = "ORD-H23-APPROVAL-1"
USER = "customer-1"


def crash_point(label: str) -> None:
    Path(os.environ["H42_READY"]).write_text(label, encoding="utf-8")
    while True:
        time.sleep(0.2)


class CrashOnApprovedStore(RedisActionStore):
    def save(self, action):
        saved = super().save(action)
        if action.status is ActionStatus.APPROVED:
            crash_point("approved_saved")
        return saved


class CrashAfterCommitBackend(InMemoryBusinessActionBackend):
    def execute_refund(self, order_id, *, customer_id, amount, action_id):
        receipt = super().execute_refund(
            order_id, customer_id=customer_id, amount=amount, action_id=action_id)
        crash_point("backend_committed")
        return receipt


class CrashAfterReceiptStore(RedisActionStore):
    def save(self, action):
        saved = super().save(action)
        if (action.status is ActionStatus.EXECUTING
                and action.execution_result is not None):
            crash_point("receipt_saved")
        return saved


class CrashAfterMemory:
    def __init__(self, inner) -> None:
        self._inner = inner

    async def add_message_once(self, *args, **kwargs):
        appended = await self._inner.add_message_once(*args, **kwargs)
        crash_point("memory_written")
        return appended

    async def add_message(self, *args, **kwargs):
        return await self._inner.add_message(*args, **kwargs)


def memory_manager(redis_url: str):
    """Exercise the real Redis working-memory method without touching Chroma."""
    from memory.conversation_memory import MemoryManager
    import redis.asyncio as aioredis

    memory = MemoryManager.__new__(MemoryManager)
    memory._redis = aioredis.from_url(redis_url, decode_responses=True)
    memory._context_compression = False
    return memory


def checkpoint_result(action, request_id: str) -> SupportResult:
    return SupportResult(
        request_id=request_id, response="等待审批", escalated=False, latency_ms=0,
        tools_used=["request_refund"],
        tool_traces=[{"tool_name": "request_refund", "action_result": {
            "action_id": action.action_id, "status": action.status.value,
            "error_code": action.error_code}}],
        model_calls=[], steps=[{"step": 1}], stop_reason="awaiting_approval")


def main() -> None:
    point = os.environ["H42_POINT"]
    request_id = os.environ["H42_REQUEST"]
    conv_id = os.environ["H42_CONV"]
    redis_url = os.environ["H42_REDIS_URL"]
    fixture = json.loads(
        Path(os.environ["H42_FIXTURE"]).read_text(encoding="utf-8"))
    read = InMemoryBusinessBackend(fixture)
    store_cls = {
        "during_approval": CrashOnApprovedStore,
        "after_receipt": CrashAfterReceiptStore,
    }.get(point, RedisActionStore)
    backend_cls = (CrashAfterCommitBackend if point == "during_execution"
                   else InMemoryBusinessActionBackend)
    write = backend_cls(read.state)
    store = store_cls(redis_url, prefix=os.environ["H42_APREFIX"])
    checkpoints = RedisCheckpointStore(
        redis_url, prefix=os.environ["H42_CPREFIX"])
    service = ActionService(business_backend=read, action_backend=write,
                            store=store, clock=lambda: NOW)
    checkpoint_service = CheckpointService(checkpoints)

    action = service.request_refund(
        order_id=ORDER, user_id=USER, request_id=request_id, amount="800.00",
        principal=customer(USER))
    assert action.status is ActionStatus.AWAITING_APPROVAL
    checkpoint_service.record_result(
        checkpoint_result(action, request_id), conv_id=conv_id, user_id=USER)

    if point == "before_approval":
        crash_point("before_approval")

    approved = service.approve(
        action_id=action.action_id, user_id=USER, request_id=request_id,
        principal=reviewer(USER))
    if point in {"during_approval", "during_execution", "after_receipt"}:
        raise SystemExit(f"expected crash at {point}, got {approved.status.value}")
    assert approved.status is ActionStatus.COMPLETED

    if point == "after_execution":
        crash_point("after_execution")

    if point == "after_memory":
        memory = memory_manager(redis_url)
        resumer = CheckpointResumer(
            checkpoint_service, service, CrashAfterMemory(memory))
        asyncio.run(resumer.resume(
            request_id, user_id=USER, principal=customer(USER)))
        raise SystemExit("expected crash after memory write")

    raise SystemExit(f"unknown crash point: {point}")


if __name__ == "__main__":
    main()
