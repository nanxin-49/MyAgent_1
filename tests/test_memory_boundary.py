"""Deterministic T11 boundaries; real Redis/Chroma are tested separately."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from api import main as api
from memory.conversation_memory import MemoryManager, MsgRole
from memory.policy import compressed_summary, explicit_preferences, fresh_metadata


class RedisStore:
    def __init__(self):
        self.values, self.ttls, self.fail_pipeline = {}, {}, False

    async def lpush(self, key, value):
        self.values.setdefault(key, []).insert(0, value)

    async def expire(self, key, ttl):
        self.ttls[key] = ttl

    async def llen(self, key):
        return len(self.values.get(key, []))

    async def lrange(self, key, start, end):
        return self.values.get(key, [])[start:end + 1]

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.values[key], self.ttls[key] = value, ttl

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.ttls.pop(key, None)

    async def scan_iter(self, match):
        prefix = match[:-1]
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    def pipeline(self, transaction=True):
        assert transaction
        store = self
        class Pipeline:
            def __init__(self): self.calls = []
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def setex(self, *args): self.calls.append(("setex", args))
            def delete(self, *args): self.calls.append(("delete", args))
            def ltrim(self, *args): self.calls.append(("ltrim", args))
            def expire(self, *args): self.calls.append(("expire", args))
            async def execute(self):
                if store.fail_pipeline:
                    raise RedisConnectionError("transaction unavailable")
                for command, args in self.calls:
                    if command == "ltrim":
                        key, start, end = args
                        store.values[key] = store.values.get(key, [])[start:end + 1]
                    else:
                        await getattr(store, command)(*args)
        return Pipeline()


class Collection:
    def __init__(self):
        self.rows = {}
        self.fail = False

    def upsert(self, ids, documents, metadatas, embeddings):
        if self.fail: raise ConnectionError("Chroma unavailable")
        assert len(embeddings) == len(ids) and len(embeddings[0]) == 1024
        for key, document, metadata in zip(ids, documents, metadatas):
            self.rows[key] = (document, metadata)

    def get(self, ids):
        if self.fail: raise ConnectionError("Chroma unavailable")
        rows = [self.rows[key] for key in ids if key in self.rows]
        return {"documents": [doc for doc, _ in rows], "metadatas": [meta for _, meta in rows]}

    def query(self, query_embeddings, n_results, where, include):
        if self.fail: raise ConnectionError("Chroma unavailable")
        assert include == ["documents", "metadatas"]
        assert len(query_embeddings[0]) == 1024
        # Deliberately return all rows; Memory must enforce provenance again.
        rows = list(self.rows.values())[:n_results]
        return {"documents": [[doc for doc, _ in rows]],
                "metadatas": [[meta for _, meta in rows]]}

    def delete(self, ids=None, where=None):
        clauses = where.get("$and", [where]) if where else []
        for key, (_, meta) in list(self.rows.items()):
            if (ids and key in ids) or (where and all(
                all(meta.get(k) == v for k, v in clause.items()) for clause in clauses)):
                self.rows.pop(key)


def manager():
    memory = MemoryManager.__new__(MemoryManager)
    memory._redis = RedisStore()
    memory._episodic = Collection()
    memory._profile = Collection()
    return memory


def test_working_ttl_context_isolation_and_key_components():
    async def scenario():
        m = manager()
        await m.add_message("u:a", "b", MsgRole.USER, "订单号 ORD-ALPHA-123")
        assert m._wm_key("u:a", "b") != m._wm_key("u", "a:b")
        assert m._redis.ttls[m._wm_key("u:a", "b")] == 86400
        assert len((await m.get_context("u:a", "b")).recent_messages) == 1
        assert not (await m.get_context("u:a", "other")).recent_messages
        assert not (await m.get_context("u", "b")).recent_messages
        assert "ORD-ALPHA-123" in (await m.get_context("u:a", "b")).to_prompt_text()
    asyncio.run(scenario())


def test_compression_preserves_reference_pending_and_not_business_state():
    async def scenario():
        m = manager()
        for index in range(15):
            if index == 0: content = "我的订单号 ORD-ALPHA-123，我猜现在已发货"
            elif index == 2: content = "请用中文回复"
            elif index == 4: content = "请提供商品型号"  # An unresolved old clarification.
            else: content = f"普通消息 {index}"
            role = MsgRole.ASSISTANT if index == 4 else MsgRole.USER
            await m.add_message("u", "c", role, content)
        key, skey = m._wm_key("u", "c"), m._summary_key("u", "c")
        assert len(m._redis.values[key]) == 5
        summary = m._redis.values[skey]
        assert "ORD-ALPHA-123" in summary and "pending=product_model" in summary
        assert "已发货" not in summary and "reply_language=中文" in summary
        assert m._redis.ttls[skey] == 86400
        context = await m.get_context("u", "c")
        assert "状态必须重新查询" in context.to_prompt_text()
    asyncio.run(scenario())


def test_compression_transaction_failure_retains_raw_messages():
    async def scenario():
        m = manager()
        for index in range(14):
            await m.add_message("u", "c", MsgRole.USER, f"消息 {index}")
        m._redis.fail_pipeline = True
        try:
            await m.add_message("u", "c", MsgRole.USER, "订单号 ORD-ALPHA-123")
            assert False, "expected Redis failure"
        except RedisConnectionError:
            pass
        assert len(m._redis.values[m._wm_key("u", "c")]) == 15
        assert m._summary_key("u", "c") not in m._redis.values
    asyncio.run(scenario())


def test_episode_filter_expiry_source_and_no_raw_transcript():
    async def scenario():
        m = manager()
        await m._store_episodic("alice", "c1", ["refund_policy"])
        assert len(m._episodic.rows) == 1
        doc, meta = next(iter(m._episodic.rows.values()))
        assert "订单号" not in doc and "full_text" not in meta
        assert meta["user_id"] == "alice" and meta["conv_id"] == "c1"
        assert meta["source"] == "explicit_user_topic" and meta["memory_type"] == "support_topic"
        await m._store_episodic("alice", "c1", ["refund_policy"])
        assert len(m._episodic.rows) == 1  # Stable id deduplicates repeated compression.
        m._episodic.rows["wrong"] = ("other user", {**meta, "user_id": "bob"})
        m._episodic.rows["legacy"] = ("raw old transcript", {"user_id": "alice"})
        m._episodic.rows["unsourced_time"] = ("missing provenance time", {
            key: value for key, value in meta.items() if key != "created_at"})
        m._episodic.rows["expired"] = ("expired topic", {**meta,
            "expires_at": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()})
        assert await m._search_episodic("alice", "other-session", "退款政策") == [doc]
        assert await m._search_episodic("bob", "c1", "退款政策") == ["other user"]
        m._episodic.fail = True
        assert await m._search_episodic("alice", "c1", "退款政策") == []
    asyncio.run(scenario())


def test_profile_requires_explicit_preference_and_rejects_legacy_inference():
    async def scenario():
        m = manager()
        assert explicit_preferences("我猜订单已发货") == {}
        await m.add_message("u", "c", MsgRole.USER, "我的订单可能已发货")
        await m.update_profile("u", "c")
        assert not m._profile.rows
        m._profile.rows[m._profile_doc_id("u")] = (json.dumps({"preferences": ["订单已发货"]}),
            {"user_id": "u", "updated_at": "2026-10-07"})
        assert await m._get_profile("u") == {}
        await m.add_message("u", "c", MsgRole.USER, "请用中文回复，订单号 ORD-ALPHA-123")
        await m.update_profile("u", "c")
        assert await m._get_profile("u") == {"preferences": {"reply_language": "中文"}}
        doc, meta = m._profile.rows[m._profile_doc_id("u")]
        assert "ORD-ALPHA-123" not in doc and "explicit_user_statement" == meta["source"]
        before = dict(m._profile.rows)
        await m.add_message("u", "c", MsgRole.USER, "物流现在如何？")
        await m.update_profile("u", "c")
        assert m._profile.rows == before
        m._profile.fail = True
        assert await m._get_profile("u") == {}
    asyncio.run(scenario())


def test_internal_deletion_and_expiration():
    async def scenario():
        m = manager()
        await m.add_message("u", "c", MsgRole.USER, "请用中文回复")
        await m.update_profile("u", "c")
        await m._store_episodic("u", "c", ["refund_policy"])
        await m.delete_session("u", "c")
        assert not m._redis.values and not m._episodic.rows
        assert await m._get_profile("u")
        await m.delete_user_memory("u")
        assert await m._get_profile("u") == {}
        meta = {"user_id": "u", "memory_type": "user_profile", "source": "explicit_user_statement",
                "expires_at": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}
        assert not fresh_metadata(meta, user_id="u", memory_type="user_profile", source="explicit_user_statement")
    asyncio.run(scenario())


def test_redis_read_failure_returns_typed_503_before_agent(monkeypatch):
    class BrokenMemory:
        async def get_context(self, *args, **kwargs):
            raise RedisConnectionError("service unavailable")
    class NeverAgent:
        async def run(self, request):
            assert False, "Agent must not run after Memory read failure"
    monkeypatch.setattr(api, "_memory", BrokenMemory())
    monkeypatch.setattr(api, "_orchestrator", NeverAgent())
    response = TestClient(api.app).post("/chat", json={"message": "查询订单", "user_id": "u"})
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "memory_unavailable"
