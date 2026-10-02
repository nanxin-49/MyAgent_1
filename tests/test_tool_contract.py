"""T08 contract tests for both local tool execution paths."""

import asyncio

import pytest

from agents.agent_orchestrator import GeneralAgent
from agents.tools import build_action_tools, build_business_tools, build_shared_rag_tools, make_tool
from core.tool_contract import RetryPolicy, RiskLevel, execute_tool, validate_tool_input
from mcp.tool_manager import MCPToolManager, Tool
from providers.mock_backend import InMemoryBusinessBackend


SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 2},
        "count": {"type": "integer"},
        "amount": {"type": "number"},
        "enabled": {"type": "boolean"},
    },
    "required": ["query"],
    "additionalProperties": False,
}


@pytest.mark.parametrize("params", [
    {}, {"query": "a"}, {"query": 1}, {"query": "ok", "secret": True},
    {"query": "ok", "count": True}, {"query": "ok", "count": 1.5},
    {"query": "ok", "amount": True}, {"query": "ok", "enabled": 1},
    [],
])
def test_agent_and_mcp_reject_same_invalid_arguments(params):
    spec = make_tool("example", "example", SCHEMA["properties"], lambda req, args: {},
                     required=SCHEMA["required"])
    # make_tool intentionally builds the same JSON schema structure; override
    # minLength stays part of the supplied properties.
    manager = MCPToolManager(api_key="test")
    tool = Tool("example", "example", lambda args, context: {}, SCHEMA)
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(spec, params)
    with pytest.raises(ValueError):
        manager._validate_params(tool, params)
    manager.register(tool)
    result = asyncio.run(manager.call("example", params))
    assert result.success is False
    assert result.error_code == "invalid_arguments"
    assert tool.stats.total == 0


def test_valid_number_integer_and_optional_fields_match():
    params = {"query": "ok", "count": 2, "amount": 2.5, "enabled": False}
    assert validate_tool_input(SCHEMA, params) == params


def test_read_timeout_has_typed_result_and_does_not_use_fallback_for_validation():
    async def slow():
        await asyncio.sleep(0.03)
        return {"success": True}

    spec = make_tool("slow", "slow", {}, lambda req, args: slow(), timeout_s=0.001)
    result = asyncio.run(execute_tool(spec, {}, slow))
    assert result.success is False
    assert result.error_code == "timeout"
    assert result.error_type == "timeout"
    assert result.retryable is True
    assert result.attempts == 1


def test_retryable_read_failure_retries_once():
    calls = 0

    def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"success": False, "error": {"code": "dependency_failure", "message": "down"},
                    "source": "business_provider"}
        return {"success": True, "data": "restored"}

    spec = make_tool("read", "read", {}, lambda req, args: flaky(),
                     retry_policy=RetryPolicy(max_attempts=2))
    result = asyncio.run(execute_tool(spec, {}, flaky))
    assert result.success is True
    assert result.attempts == calls == 2


def test_nonretryable_domain_error_keeps_code_and_type():
    calls = 0

    def denied():
        nonlocal calls
        calls += 1
        return {"success": False, "error": {"code": "unauthorized", "message": "not owner"},
                "source": "business_provider"}

    spec = make_tool("read", "read", {}, lambda req, args: denied(),
                     retry_policy=RetryPolicy(max_attempts=3))
    result = asyncio.run(execute_tool(spec, {}, denied))
    assert result.success is False
    assert result.error_code == "unauthorized"
    assert result.error_type == "provider"
    assert result.retryable is False
    assert result.attempts == calls == 1


@pytest.mark.parametrize("risk", [RiskLevel.WRITE, RiskLevel.DANGEROUS])
def test_state_changing_tool_is_never_retried_by_runtime(risk):
    calls = 0

    def failing():
        nonlocal calls
        calls += 1
        return {"success": False, "error_code": "dependency_failure", "action_id": "act_1"}

    spec = make_tool("action", "action", {}, lambda req, args: failing(),
                     risk_level=risk, retry_policy=RetryPolicy(max_attempts=4),
                     idempotent=False, timeout_s=0.001)
    result = asyncio.run(execute_tool(spec, {}, failing))
    assert result.success is False
    assert result.error_code == "dependency_failure"
    assert result.error_type == "action"
    assert result.retryable is False
    assert result.attempts == calls == 1


def test_mcp_rag_call_keeps_cache_and_retries_dependency_failure():
    calls = 0

    async def search(params, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary outage")
        return [{"content": params["query"]}]

    manager = MCPToolManager(api_key="test")
    manager.register(Tool("knowledge_search", "demo rag", search,
                          {"type": "object", "properties": {"query": {"type": "string", "minLength": 1}},
                           "required": ["query"], "additionalProperties": False},
                          cache_ttl=30, retry_policy=RetryPolicy(max_attempts=2)))
    # An untyped OSError is deliberately not retried.
    first = asyncio.run(manager.call("knowledge_search", {"query": "policy"}))
    assert first.success is False
    assert first.error_code == "execution_failure"
    second = asyncio.run(manager.call("knowledge_search", {"query": "policy"}))
    third = asyncio.run(manager.call("knowledge_search", {"query": "policy"}))
    assert second.success is True and second.data == [{"content": "policy"}]
    assert third.cached is True
    assert calls == 2


def test_mcp_retryable_typed_failure_retries_and_write_never_caches():
    calls = 0

    class DependencyFailure(Exception):
        code = "dependency_failure"

    async def handler(params, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise DependencyFailure("unavailable")
        return ["ok"]

    manager = MCPToolManager(api_key="test")
    manager.register(Tool("read", "read", handler,
                          {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                          retry_policy=RetryPolicy(max_attempts=2)))
    result = asyncio.run(manager.call("read", {}))
    assert result.success is True
    assert result.attempts == calls == 2

    writes = 0

    async def write(params, context):
        nonlocal writes
        writes += 1
        raise DependencyFailure("uncertain outcome")

    manager.register(Tool("write", "write", write,
                          {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                          cache_ttl=30, risk_level=RiskLevel.DANGEROUS,
                          retry_policy=RetryPolicy(max_attempts=4), idempotent=False))
    failed = asyncio.run(manager.call("write", {}))
    assert failed.error_code == "dependency_failure"
    assert failed.attempts == writes == 1


def test_mcp_timeout_and_nonretryable_error_keep_stable_codes():
    fallback_calls = 0

    def fallback(params, context, error):
        nonlocal fallback_calls
        fallback_calls += 1
        return ["degraded"]

    async def slow(params, context):
        await asyncio.sleep(0.02)

    manager = MCPToolManager(api_key="test")
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    manager.register(Tool("slow", "slow", slow, schema, timeout_s=0.001, fallback=fallback))
    timeout = asyncio.run(manager.call("slow", {}))
    assert timeout.error_code == "timeout"
    assert timeout.retryable is True
    assert fallback_calls == 1

    async def denied(params, context):
        return {"success": False, "error": {"code": "unauthorized", "message": "not owner"},
                "source": "business_provider"}

    manager.register(Tool("denied", "denied", denied, schema, fallback=fallback,
                          retry_policy=RetryPolicy(max_attempts=3)))
    rejected = asyncio.run(manager.call("denied", {}))
    assert rejected.success is False
    assert rejected.error_code == "unauthorized"
    assert rejected.error_type == "provider"
    assert rejected.attempts == 1
    assert fallback_calls == 1


def test_agent_rag_adapter_preserves_search_with_rewrite_path():
    manager = MCPToolManager(api_key="test")

    async def search(params, context):
        return [{"content": params["query"], "score": 0.9,
                 "document_id": "doc_demo", "title": "演示政策", "source": "demo-policy",
                 "doc_type": "policy", "chunk_index": 0, "total_chunks": 1,
                 "policy_version": "demo-v1", "effective_at": "2026-09-01T00:00:00+00:00",
                 "retrieval_status": "usable",
                 "citation": {"reference": "doc_demo@demo-v1#chunk-0", "document_id": "doc_demo",
                              "chunk_index": 0, "source": "demo-policy", "policy_version": "demo-v1"}}]

    async def rewrite(query, n=3):
        return [query]

    async def rerank(query, items, top_k):
        return items[:top_k]

    manager.rewrite_query = rewrite
    manager._rerank = rerank
    manager.register(Tool("knowledge_search", "search", search,
                          {"type": "object", "properties": {
                              "query": {"type": "string", "minLength": 1},
                              "top_k": {"type": "integer"}},
                           "required": ["query"], "additionalProperties": False}))
    adapter = build_shared_rag_tools(manager)["search_knowledge_base"]
    result = asyncio.run(execute_tool(adapter, {"query": "退货规则"},
                                      lambda: adapter.handler(None, {"query": "退货规则"})))
    assert result.success is True
    assert result.data["results"][0]["source"] == "demo-policy"
    assert result.data["reranked"] is True


def test_registered_business_and_action_metadata_preserve_boundaries():
    class NoopActionService:
        pass

    backend = InMemoryBusinessBackend({"products": {}, "orders": {}, "inventory": {},
                                       "shipments": {}, "refunds": {}})
    assert all(tool.risk_level is RiskLevel.READ for tool in build_business_tools(backend).values())
    for tool in build_action_tools(NoopActionService()).values():
        assert tool.risk_level is RiskLevel.DANGEROUS
        assert tool.retry_policy.max_attempts == 1
        assert tool.timeout_s is None
        assert tool.idempotent is False


def test_write_tool_schema_rejects_extra_identity_and_boolean_amount():
    class NoopActionService:
        pass

    refund = build_action_tools(NoopActionService())["request_refund"]
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(refund, {"order_id": "ORD-1", "user_id": "other"})
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(refund, {"order_id": "ORD-1", "amount": True})
