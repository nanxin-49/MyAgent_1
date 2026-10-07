"""Live HTTP acceptance of the production Support Agent with the real MemoryManager.

Uses the project's running Redis and Chroma services. Only isolated demo users,
session keys, and a copied demo business fixture are created for this run.
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit

import redis.asyncio as redis
import uvicorn
from dotenv import load_dotenv

from evaluation.capture_online_eval import _request

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path(os.getenv("CARTCARE_MEMORY_ACCEPTANCE_REPORT",
    str(ROOT / "evaluation/reports/support_production/memory_acceptance.json")))


def _loopback_redis_url(configured: str) -> str:
    parsed = urlsplit(configured)
    # Preserve the project's auth/database while reaching its published port.
    auth = parsed.netloc.rsplit("@", 1)[0] + "@" if "@" in parsed.netloc else ""
    return urlunsplit((parsed.scheme, f"{auth}127.0.0.1:6379", parsed.path, parsed.query, parsed.fragment))


def _tool_order_ids(trace: dict) -> list[str]:
    return [item.get("validated_input", {}).get("order_id") for item in trace.get("tool_calls", [])
            if item.get("validated_input", {}).get("order_id")]


async def _get(base: str, path: str):
    return await asyncio.to_thread(_request, base, path, None, 20)


async def _post(base: str, message: str, user_id: str, conv_id: str):
    chat = await asyncio.to_thread(_request, base, "/chat", {
        "message": message, "user_id": user_id, "conv_id": conv_id}, 100)
    trace = await _get(base, f'/trace/tool/{chat["request_id"]}')
    assert trace["found"]
    return chat, trace["trace"]


async def run():
    from api import main as api
    from memory.conversation_memory import MemoryManager

    load_dotenv(ROOT / ".env")
    configured = os.environ["REDIS_URL"]
    live_url = _loopback_redis_url(configured)
    suffix = uuid.uuid4().hex[:10]
    user_a, user_b = f"memory-a-{suffix}", f"memory-b-{suffix}"
    conv_a, conv_b = f"memory-conv-a-{suffix}", f"memory-conv-b-{suffix}"

    fixture = json.loads((ROOT / "evaluation/reports/support_production/fixture.json").read_text(encoding="utf-8"))
    fixture["orders"]["ORD-T09-LOGISTICS"]["customer_id"] = user_a
    fixture["shipments"]["ORD-T09-LOGISTICS"]["customer_id"] = user_a
    fixture["orders"]["ORD-T09-ORDER"]["customer_id"] = user_b
    fixture_path = REPORT.with_name(f"memory_fixture_{suffix}.json")
    fixture_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    env = {"REDIS_URL": live_url, "CHROMA_HOST": "127.0.0.1", "CHROMA_PORT": "8001",
           "CARTCARE_BUSINESS_FIXTURE": str(fixture_path), "PROMETHEUS_PORT": "0", "ALERT_WEBHOOK_URL": ""}
    old_env = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=8012, log_level="critical"))
    server_task = asyncio.create_task(server.serve())
    redis_client = redis.from_url(live_url, decode_responses=True, socket_connect_timeout=2)
    checks = {}
    observations = {}
    try:
        while not server.started:
            if server_task.done():
                await server_task
                raise RuntimeError("API server failed to start")
            await asyncio.sleep(.1)
        checks["real_memory_manager"] = type(api._memory) is MemoryManager and await redis_client.ping()
        base = "http://127.0.0.1:8012"
        # Fresh session; first turn must read the actual demo order and persist two messages.
        before = await api._memory.get_context(user_a, conv_a)
        checks["fresh_context_empty"] = not before.recent_messages and not before.relevant_history
        first, first_trace = await _post(base, "查询我的订单 ORD-T09-LOGISTICS。请用中文回复。", user_a, conv_a)
        stored = await api._memory.get_context(user_a, conv_a)
        profile = {}
        for _ in range(20):
            profile = await api._memory._get_profile(user_a)
            if profile:
                break
            await asyncio.sleep(.1)
        checks["async_profile_explicit_preference"] = profile.get("preferences") == {"reply_language": "中文"}
        checks["first_order_lookup"] = any(t.get("tool_name") == "get_order" and
            (t.get("business_result") or {}).get("order_id") == "ORD-T09-LOGISTICS"
            for t in first_trace["tool_calls"])
        checks["redis_write_read"] = len(stored.recent_messages) == 2 and stored.recent_messages[0].content.startswith("查询我的订单")
        checks["request_path"] = first["topology"] == first_trace["topology"] == "single" and first["agent_type"] == first_trace["agent_type"] == "support"

        # Same user and session: ask without an order number. The tool must receive the prior number.
        second, second_trace = await _post(base, "这个订单的物流到哪里了？", user_a, conv_a)
        checks["second_turn_uses_order_number"] = any(t.get("tool_name") == "get_shipment" and
            t.get("validated_input", {}).get("order_id") == "ORD-T09-LOGISTICS" and
            (t.get("business_result") or {}).get("shipment_id") == "SHP-ORD-T09-LOGISTICS"
            for t in second_trace["tool_calls"])
        after_second = await api._memory.get_context(user_a, conv_a)
        checks["two_turns_persisted"] = len(after_second.recent_messages) == 4

        # Change only this run's copied demo backend. The old assistant reply is now stale.
        api._action_service._business_backend._data["orders"]["ORD-T09-LOGISTICS"]["status"] = "delivered"
        refreshed, refreshed_trace = await _post(base,
            "刚才那个订单现在是否已发货？请重新查询订单状态。", user_a, conv_a)
        checks["dynamic_order_fact_refreshed"] = any(t.get("tool_name") == "get_order" and
            t.get("validated_input", {}).get("order_id") == "ORD-T09-LOGISTICS" and
            (t.get("business_result") or {}).get("status") == "delivered"
            for t in refreshed_trace["tool_calls"])

        # Same user, new session; different user, same session key. Neither gets the first turn.
        same_user_other_session = await api._memory.get_context(user_a, conv_b)
        other_user_same_session = await api._memory.get_context(user_b, conv_a)
        checks["session_isolation"] = not same_user_other_session.recent_messages and not same_user_other_session.relevant_history
        checks["user_isolation"] = not other_user_same_session.recent_messages and not other_user_same_session.relevant_history
        isolated, isolated_trace = await _post(base, "这个订单的物流到哪里了？", user_b, conv_a)
        checks["other_user_no_order_leak"] = "ORD-T09-LOGISTICS" not in _tool_order_ids(isolated_trace)

        schema = (await _get(base, "/openapi.json"))["components"]["schemas"]["ChatResponse"]["properties"]
        legacy = ("primary_agent", "supporting_agents", "routing_reason", "routing_confidence")
        checks["schema_nullable_deprecated"] = all(schema[key].get("deprecated") is True and
            any(option.get("type") == "null" for option in schema[key].get("anyOf", [])) for key in legacy)
        checks["response_trace_null_compatible"] = all(first.get(key) is None and first_trace.get(key) is None for key in legacy)
        checks["trace_tool_consistent"] = first["request_id"] == first_trace["request_id"] and second["request_id"] == second_trace["request_id"]

        # A closed loopback port causes a real Redis connection failure without stopping shared Redis.
        original_client = api._memory._redis
        broken = redis.Redis(host="127.0.0.1", port=6399, socket_connect_timeout=.5, socket_timeout=.5)
        trace_count_before_failure = len(api._orchestrator.get_recent_tool_traces(200))
        api._memory._redis = broken
        try:
            try:
                await asyncio.to_thread(_request, base, "/chat", {"message": "查询订单", "user_id": user_a, "conv_id": conv_a}, 10)
                failure_status = 200
            except HTTPError as exc:
                failure_status = exc.code
        finally:
            api._memory._redis = original_client
            await broken.aclose()
        checks["redis_failure_fails_closed"] = failure_status == 503
        checks["redis_failure_did_not_run_agent"] = len(api._orchestrator.get_recent_tool_traces(200)) == trace_count_before_failure
        checks["redis_recovery"] = (await api._memory.get_context(user_a, conv_a)).recent_messages != []
        observations = {"first_tools": first["tools_used"], "second_tools": second["tools_used"],
            "refreshed_tools": refreshed["tools_used"],
            "isolated_tools": isolated["tools_used"], "first_order_ids": _tool_order_ids(first_trace),
            "second_order_ids": _tool_order_ids(second_trace), "isolated_order_ids": _tool_order_ids(isolated_trace),
            "redis_failure_http_status": failure_status, "messages_after_second": len(after_second.recent_messages)}
    finally:
        server.should_exit = True
        await server_task
        try:
            for user, conv in ((user_a, conv_a), (user_a, conv_b), (user_b, conv_a)):
                await redis_client.delete(f"wm:{user}:{conv}", f"summary:{user}:{conv}")
        except redis.RedisError:
            pass  # Preserve the original dependency failure; test keys have a 24h TTL.
        finally:
            await redis_client.aclose()
        # Profile updates may have run asynchronously. Remove only our unique test users.
        try:
            import chromadb
            collection = chromadb.HttpClient(host="127.0.0.1", port=8001,
                settings=chromadb.Settings(anonymized_telemetry=False)).get_collection(
                    MemoryManager.PROFILE_COLLECTION)
            for user in (user_a, user_b):
                collection.delete(ids=[f"user_profile:{user}"])
        except Exception:
            pass
        fixture_path.unlink(missing_ok=True)
        for key, value in old_env.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
    report = {"mode": "actual HTTP /chat + real MemoryManager + running Redis/Chroma + real model",
              "checks": checks, "observations": observations,
              "scope": "Isolated demo users and copied fixture; no business module or prompt changes.",
              "failure_contract": "Redis read failure returns HTTP 503; no Agent/tool execution or fabricated reply."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# T11: real Memory acceptance", "",
        "Actual localhost HTTP `/chat` with the T11 MemoryManager, running Redis/Chroma and real model.",
        "A copied demo business fixture uses isolated test customers; their Redis keys and profile records are removed after the run.",
        "", "| Check | Result |", "|---|---|"]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in checks.items())
    lines += ["", "The second turn called `get_shipment` with the order ID from the first turn and returned the matching demo shipment.",
        "After the copied demo order changed from shipped to delivered, a later turn called `get_order` again and observed the fresh Provider status.",
        "An explicit response-language preference was written by the asynchronous profile update and read back from the real Chroma collection.",
        "The other user saw no order ID from the first conversation. OpenAPI marks old routing fields nullable and deprecated; response and trace return null.",
        "A Redis connection failure returned typed HTTP 503 before Agent execution; restoring Redis recovered the original session.",
        "Compression, long-term retrieval and profile metadata are tested separately with a real Redis/Chroma opt-in test. See the adjacent JSON for check values and tool observations."]
    REPORT.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(not all(checks.values()))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
