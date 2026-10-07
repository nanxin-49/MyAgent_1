"""Opt-in real Redis/Chroma memory boundary test; never a mock substitute."""
import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import load_dotenv

from memory.conversation_memory import MemoryManager, MsgRole


@pytest.mark.skipif(os.getenv("CARTCARE_TEST_LIVE_MEMORY") != "1", reason="requires live Redis/Chroma")
def test_live_memory_isolation_compression_and_long_term_metadata():
    load_dotenv()
    configured = urlsplit(os.environ["REDIS_URL"])
    auth = configured.netloc.rsplit("@", 1)[0] + "@" if "@" in configured.netloc else ""
    redis_url = urlunsplit((configured.scheme, f"{auth}127.0.0.1:6379",
                            configured.path, configured.query, configured.fragment))

    async def scenario():
        memory = MemoryManager(redis_url=redis_url, chroma_host="127.0.0.1", chroma_port=8001)
        suffix = uuid.uuid4().hex
        alice, bob, session, other = (f"t11-a-{suffix}", f"t11-b-{suffix}",
                                      f"t11-c-{suffix}", f"t11-d-{suffix}")
        try:
            await memory.add_message(alice, session, MsgRole.USER,
                                     "订单号 ORD-T11-123，咨询退款政策。请用中文回复")
            await memory.update_profile(alice, session)
            assert (await memory._get_profile(alice))["preferences"] == {"reply_language": "中文"}
            assert await memory._redis.ttl(memory._wm_key(alice, session)) > 0
            for index in range(14):
                await memory.add_message(alice, session, MsgRole.USER, f"继续第 {index} 轮")
            context = await memory.get_context(alice, session, "退款政策")
            assert len(context.recent_messages) == 5
            assert "ORD-T11-123" in context.summary
            assert "退款政策" in " ".join(context.relevant_history) or "refund_policy" in " ".join(context.relevant_history)
            assert await memory._redis.ttl(memory._summary_key(alice, session)) > 0
            assert not (await memory.get_context(bob, session, "退款政策")).relevant_history
            assert not (await memory.get_context(bob, session, "退款政策")).recent_messages
            assert not (await memory.get_context(alice, other, "订单号")).recent_messages
            records = await asyncio.to_thread(memory._episodic.get, where={"user_id": alice})
            assert records["metadatas"] and all(
                all(field in meta for field in ("user_id", "conv_id", "source", "memory_type", "created_at", "expires_at"))
                for meta in records["metadatas"])
            await memory.delete_session(alice, session)
            assert not (await memory.get_context(alice, session)).recent_messages
            assert (await memory._get_profile(alice))["preferences"]["reply_language"] == "中文"
            await memory.delete_user_memory(alice)
            assert not await memory._get_profile(alice)
        finally:
            await memory.delete_user_memory(alice)
            await memory.delete_user_memory(bob)
            await memory.close()

    asyncio.run(scenario())
