"""Isolated defect probes; no real model, Redis, Chroma, or payment calls.

Run from repo root: uv run python docs/engineering/audit_20261011_probe.py
Assertions intentionally confirm current defects, not desired behavior.
"""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import runpy
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)

from api import main as api
from agents.support_agent import SupportRuntime
from agents.tools import build_action_tools, build_business_tools
from core.tool_contract import RiskLevel, RetryPolicy, execute_tool
from evaluation.prepare_online_eval import prepare
from evaluation.topology_experiment import isolated_business
from fastapi.testclient import TestClient
from mcp.knowledge_base import KnowledgeBase
from mcp.tool_manager import MCPToolManager, ToolResult
from memory.conversation_memory import MsgRole
from evaluation.evaluator import EndToEndEvaluator
from monitor.performance_monitor import PerformanceMonitor
from providers import OrderProvider
from providers.errors import ProviderError
from providers.mock_backend import InMemoryBusinessBackend
from redis.exceptions import ConnectionError as RedisConnectionError
from tests.test_topology_comparison import FakeClient, NOW

fixture_helpers = runpy.run_path(str(ROOT / "tests/test_action_service.py"))
observations = []


def record(issue, **details):
    observations.append({"issue": issue, "evidence_kind": "isolated_fake_dependency_reproduction",
                         "defect_reproduced": True, **details})


def action_probes():
    service, backend = fixture_helpers["make_service"]()
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="audit-1", amount="10", idempotency_key="audit-key")
    changed = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="audit-2", amount="20", idempotency_key="audit-key")
    leaked = service.request_refund(order_id="ORD-1001", user_id="customer-2",
        request_id="audit-3", amount="10", idempotency_key=first.action.idempotency_key)
    assert first.status.value == changed.status.value == leaked.status.value == "completed"
    assert changed.action_id == leaked.action_id == first.action_id
    assert str(changed.action.amount) == "10" and leaked.action.user_id == "customer-1"
    assert len(backend.calls) == 1
    record("IDEMPOTENCY", mismatched_amount_requested="20", returned_amount=str(changed.action.amount),
        internal_key_cross_user_returned_owner=leaked.action.user_id, backend_executions=len(backend.calls),
        qualification="Cross-user reproduction requires the returned internal key; ordinary same external key is scoped.")
    raw = service._business_backend
    assert raw.get_order("ORD-1001")["status"] == "refund_pending"
    assert raw.get_refund_for_order("ORD-1001") is None
    record("REFUND_READ_WRITE", action_status=first.status.value,
        execution_status=first.action.execution_result["status"],
        order_status=raw.get_order("ORD-1001")["status"], refund_record=None)


class FakeKnowledgeCollection:
    def __init__(self): self.rows = {}
    def upsert(self, ids, documents, metadatas, embeddings):
        for key, content, metadata in zip(ids, documents, metadatas):
            self.rows[key] = (content, metadata)
    def count(self): return len(self.rows)
    def query(self, **kwargs):
        rows = list(self.rows.values())[:kwargs["n_results"]]
        return {"documents": [[r[0] for r in rows]], "metadatas": [[r[1] for r in rows]],
                "distances": [[0.0 for _ in rows]]}


def knowledge_probe():
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb.min_score, kb._collection = .35, FakeKnowledgeCollection()
    doc = {"document_id": "audit-policy", "title": "refund policy", "source": "audit:synthetic",
           "doc_type": "policy", "policy_version": "v1", "effective_at": "2020-01-01T00:00:00Z"}
    kb.add_documents([{**doc, "content": "Refund window is 7 days."}])
    kb.add_documents([{**doc, "content": "Refund window is 30 days."}])
    hits = kb.search("refund", 10)
    refs = [h["citation"]["reference"] for h in hits]
    assert kb.doc_count == 2 and len(set(refs)) == 1
    kb.add_documents([{**doc, "policy_version": "v2", "content": "Refund window is 90 days."}])
    hits = kb.search("refund", 10)
    assert len(hits) == 3 and all(h["retrieval_status"] == "usable" for h in hits)
    record("KNOWLEDGE_UPDATE", stored_chunks=len(hits),
        same_version_conflicting_reference=refs[0],
        usable_policy_versions=[h["policy_version"] for h in hits],
        qualification="Fake distances force recall; this confirms lifecycle/citation defects, not real ranking quality.")


def provider_probe():
    data = fixture_helpers["raw_data"]()
    del data["orders"]["ORD-1001"]["total_amount"]
    data["orders"]["ORD-1001"]["audit_sensitive_marker"] = "SYNTHETIC-OWNER-DATA"
    provider = OrderProvider(InMemoryBusinessBackend(data))
    try:
        provider.get_order("ORD-1001", customer_id="customer-2")
    except ProviderError as exc:
        details = exc.to_dict()
        assert "SYNTHETIC-OWNER-DATA" in json.dumps(details)
        record("PROVIDER_ERROR_LEAK", error_code=exc.code,
            synthetic_other_owner_input_visible=True,
            qualification="Requires malformed backend record; normal valid records enforce ownership.")
    else:
        raise AssertionError("expected malformed-record failure")


def http_probes():
    class FailingWriteMemory:
        async def get_context(self, *args, **kwargs):
            return SimpleNamespace(recent_messages=[], to_prompt_text=lambda: "")
        async def add_message(self, *args): raise RuntimeError("synthetic memory write outage")
    tools, service, backend = isolated_business(prepare(NOW)[0], NOW)
    runtime = SupportRuntime("test", "test", client=FakeClient("request_cancel_order",
        {"order_id": "ORD-T09-CANCEL"}))
    runtime.set_shared_tools(tools)
    saved = api._orchestrator, api._memory, api._action_service
    try:
        api._orchestrator, api._memory, api._action_service = runtime, FailingWriteMemory(), service
        http = TestClient(api.app, raise_server_exceptions=False)  # no lifespan/external services
        response = http.post("/chat", json={"message": "cancel order", "user_id": "customer-1"})
        assert response.status_code == 500 and len(backend.calls) == 1
        actions = list(service._store._actions.values())
        assert actions[0].status.value == "completed"
        record("ACTION_SUCCESS_MEMORY_FAILURE", http_status=response.status_code,
            action_status=actions[0].status.value, backend_executions=len(backend.calls))
        traces = http.get("/trace/tools")
        assert traces.status_code == 200 and len(traces.json()["items"]) == 1
        record("TRACE_NO_AUTH", http_status=traces.status_code,
            headers_have_credentials=False, retrieved_trace_count=len(traces.json()["items"]))
        pending_service, pending_backend = fixture_helpers["make_service"](total="800")
        pending = pending_service.request_refund(order_id="ORD-1001", user_id="customer-1",
            request_id="audit-approval", amount="600")
        assert pending.status.value == "awaiting_approval"
        api._action_service = pending_service
        approval = http.post(f"/actions/{pending.action_id}/approve", json={"user_id": "customer-1"})
        assert approval.status_code == 200 and approval.json()["status"] == "completed"
        assert len(pending_backend.calls) == 1
        record("APPROVAL_CLIENT_IDENTITY", http_status=approval.status_code,
            trusted_principal_or_reviewer_supplied=False, action_status=approval.json()["status"],
            qualification="Known demo approval adapter limitation; owner checks exist but caller identity is untrusted.")
        class FailingReadMemory:
            async def get_context(self, *args, **kwargs): raise RedisConnectionError("synthetic Redis outage")
        api._memory = FailingReadMemory()
        health = http.get("/health")
        chat = http.post("/chat", json={"message": "order", "user_id": "customer-1"})
        assert health.status_code == 200 and chat.status_code == 503
        record("HEALTH_READINESS", health_http_status=health.status_code, chat_http_status=chat.status_code,
            dependency="synthetic Redis read failure")
        http.close()
    finally:
        api._orchestrator, api._memory, api._action_service = saved


async def timeout_probe():
    events, lock = [], threading.Lock()
    def slow_read():
        with lock: events.append("started")
        time.sleep(.15)
        with lock: events.append("completed")
        return {"success": True}
    contract = SimpleNamespace(input_schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.READ, idempotent=True, timeout_s=.02, retry_policy=RetryPolicy(2))
    result = await execute_tool(contract, {}, slow_read)
    completed_at_return = events.count("completed")
    await asyncio.sleep(.2)
    assert result.error_code == "timeout" and result.attempts == 2
    assert completed_at_return == 0 and events.count("completed") == 2
    record("READ_TIMEOUT_WORKERS", attempts=result.attempts, completed_at_return=completed_at_return,
        completed_after_return=events.count("completed"))


async def monitor_probe():
    orchestrator = SimpleNamespace(supports_routing=False, get_stats=lambda: {
        "support": {"success_rate": 1.0, "avg_ms": 4000}})
    monitor = PerformanceMonitor(orchestrator, SimpleNamespace(get_stats=lambda: {}), prometheus_port=None)
    assert monitor._prom == {}
    record("PROM_DEFAULT", registered_business_metrics=list(monitor._prom))
    class Metric:
        def __init__(self): self.observations = []
        def labels(self, **kwargs): return self
        def set(self, value): pass
        def observe(self, value): self.observations.append(value)
    latency = Metric()
    monitor._prom = {"agent_success_rate": Metric(), "agent_latency_ms": latency}
    for _ in range(3): await monitor._collect()
    assert latency.observations == [4000, 4000, 4000] and len(monitor._alerts) == 3
    record("PROM_DISTRIBUTION_ALERTS", request_latency_histogram_observations=latency.observations,
        new_requests_during_collections=0, duplicate_alerts=len(monitor._alerts))


async def rerank_probe():
    manager = MCPToolManager.__new__(MCPToolManager)
    manager._model = "fake"
    manager._client = FakeClient("unused", {})
    manager._client.responses = [SimpleNamespace(content=[SimpleNamespace(type="text", text="[]")])]
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb.min_score, kb._collection = .35, FakeKnowledgeCollection()
    kb.add_documents([{"title": f"policy {i}", "content": f"audit policy {i}",
        "source": f"audit:{i}"} for i in range(2)])
    hits = kb.search("policy", 2)
    async def rewrite(*args, **kwargs): return ["policy"]
    async def call(*args, **kwargs): return ToolResult(success=True, data=hits, tool_name="knowledge_search")
    manager.rewrite_query, manager.call = rewrite, call
    result = await manager.search_with_rewrite("knowledge_search", "policy", top_k=1)
    assert result.success and result.retrieval_status == "usable" and result.data == [] and result.citations == []
    record("RERANK_EMPTY_USABLE", model_rerank_output="[]", retrieval_status=result.retrieval_status,
        success=result.success, result_count=len(result.data), citation_count=len(result.citations))


async def memory_probes():
    helpers = runpy.run_path(str(ROOT / "tests/test_memory_boundary.py"))
    memory = helpers["manager"]()
    key = memory._wm_key("audit-user", "audit-session")
    def raw_message(content):
        return json.dumps({"role": "user", "content": content, "ts": NOW.isoformat(), "metadata": {}})
    for i in range(15): await memory._redis.lpush(key, raw_message(f"old message {i}"))
    previous_get = memory._redis.get
    async def interleaved_get(skey):
        # Pause compression after its snapshot, while six other writes arrive.
        for content in ["ORD-LOST-999", "new 1", "new 2", "new 3", "new 4", "new 5"]:
            await memory._redis.lpush(key, raw_message(content))
        return await previous_get(skey)
    memory._redis.get = interleaved_get
    await memory._compress("audit-user", "audit-session")
    remaining = await memory._get_working_memory("audit-user", "audit-session")
    summary = await previous_get(memory._summary_key("audit-user", "audit-session")) or ""
    assert all("ORD-LOST-999" not in m.content for m in remaining) and "ORD-LOST-999" not in summary
    record("MEMORY_COMPRESSION_RACE", concurrent_writes=6, retained_messages=len(remaining),
        first_concurrent_order_reference_lost=True,
        qualification="Controlled interleaving, not a measured frequency under real Redis traffic.")
    profile_memory = helpers["manager"]()
    await profile_memory.add_message("audit-user", "audit-session", MsgRole.USER, "请用英文回复")
    await profile_memory.add_message("audit-user", "audit-session", MsgRole.USER, "查下订单")
    await profile_memory.update_profile("audit-user", "audit-session")
    assert profile_memory._profile.rows == {}
    record("PROFILE_UPDATE_RACE", triggering_preference="English", persisted=False,
        qualification="Scheduled update runs after a later user message; it reads latest, not the triggering message.")


async def evaluator_probe():
    service, backend = fixture_helpers["make_service"](status="paid")
    tools = {**build_business_tools(service._business_backend), **build_action_tools(service)}
    runtime = SupportRuntime("test", "test", client=FakeClient("request_cancel_order",
        {"order_id": "ORD-1001"}))
    runtime.set_shared_tools(tools)
    evaluator = EndToEndEvaluator.__new__(EndToEndEvaluator)
    evaluator._orchestrator = runtime
    async def judge(*args, **kwargs):
        return SimpleNamespace(overall=1.0, relevance=1.0, clarity=1.0,
            completeness=1.0, helpfulness=1.0, judge_failed=False, error=None)
    evaluator._judge = SimpleNamespace(judge=judge)
    await evaluator._evaluate_dialog_case({"question": "cancel", "user_id": "customer-1"}, 0)
    assert len(backend.calls) == 1 and service._business_backend.get_order("ORD-1001")["status"] == "cancelled"
    record("EVAL_SHARED_STATE", backend_executions=len(backend.calls), business_order_status="cancelled",
        qualification="Reproduces evaluator using bound runtime; startup binds the same runtime as /chat.")


async def main():
    action_probes()
    knowledge_probe()
    provider_probe()
    http_probes()
    await timeout_probe()
    await monitor_probe()
    await rerank_probe()
    await memory_probes()
    await evaluator_probe()
    output = {"generated_at": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree": "uncommitted organization changes plus audit artifacts",
        "python": platform.python_version(), "platform": platform.platform(),
        "scope": "isolated fake dependencies; no live-service or real-model acceptance",
        "observations": observations}
    path = Path(__file__).with_name("audit-20261011-observations.json")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__": asyncio.run(main())
