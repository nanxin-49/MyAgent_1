"""H4-3: controlled interleavings for Memory compression and profile updates."""
from __future__ import annotations

import asyncio
import json

from memory.conversation_memory import MsgRole
from tests.test_memory_boundary import RedisStore, manager


class PausingStore(RedisStore):
    """Pause the compression transaction immediately before ltrim."""

    def __init__(self) -> None:
        super().__init__()
        self.trim_started = asyncio.Event()
        self.release_trim = asyncio.Event()
        self.pause_once = True

    def pipeline(self, transaction=True):
        base = super().pipeline(transaction)
        store = self
        original = base.execute

        async def execute():
            if (store.pause_once
                    and any(command == "ltrim" for command, _ in base.calls)):
                store.pause_once = False
                store.trim_started.set()
                await store.release_trim.wait()
            return await original()

        base.execute = execute
        return base


def test_compression_never_drops_concurrent_messages():
    async def scenario():
        memory = manager()
        store = PausingStore()
        memory._redis = store
        memory._context_compression = False
        for index in range(15):
            await memory.add_message("u", "c", MsgRole.USER, f"消息 {index}")

        compressing = asyncio.create_task(memory._compress("u", "c"))
        await asyncio.wait_for(store.trim_started.wait(), timeout=1)
        writes = [
            asyncio.create_task(
                memory.add_message("u", "c", MsgRole.USER, f"并发 {index}"))
            for index in range(6)
        ]
        done, pending = await asyncio.wait(writes, timeout=0.05)
        assert not done, "concurrent writes must wait for compression"
        assert len(pending) == 6

        store.release_trim.set()
        await asyncio.gather(compressing, *writes)
        values = [
            json.loads(raw)["content"]
            for raw in memory._redis.values[memory._wm_key("u", "c")]
        ]
        assert len(values) == 11
        for index in range(6):
            assert f"并发 {index}" in values

    asyncio.run(scenario())


def test_profile_update_uses_triggering_message_not_latest_message():
    async def scenario():
        memory = manager()
        started = asyncio.Event()
        release = asyncio.Event()
        original = memory._get_profile

        async def slow_profile(user_id):
            started.set()
            await release.wait()
            return await original(user_id)

        memory._get_profile = slow_profile
        task = asyncio.create_task(
            memory.update_profile("u", "c", "请用中文回复"))
        await asyncio.wait_for(started.wait(), timeout=1)
        await memory.add_message("u", "c", MsgRole.USER, "请用英文回复")
        release.set()
        await task
        assert (await memory._get_profile("u"))["preferences"] == {
            "reply_language": "中文"}

    asyncio.run(scenario())


def test_profile_updates_serialize_read_modify_write():
    async def scenario():
        memory = manager()
        started = asyncio.Event()
        release = asyncio.Event()
        original = memory._get_profile
        reads = 0

        async def slow_profile(user_id):
            nonlocal reads
            reads += 1
            if reads == 1:
                started.set()
                await release.wait()
            return await original(user_id)

        memory._get_profile = slow_profile
        first = asyncio.create_task(
            memory.update_profile("u", "c", "请用中文回复"))
        await asyncio.wait_for(started.wait(), timeout=1)
        second = asyncio.create_task(
            memory.update_profile("u", "c", "请详细回复"))
        await asyncio.sleep(0.05)
        assert reads == 1, "second update must wait before reading the profile"

        release.set()
        await asyncio.gather(first, second)
        assert (await memory._get_profile("u"))["preferences"] == {
            "reply_language": "中文",
            "reply_detail": "详细",
        }

    asyncio.run(scenario())
