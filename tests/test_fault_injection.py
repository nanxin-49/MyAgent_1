"""H2-2 evaluation-only fault injection."""
import asyncio
import pytest

from agents.tools import make_tool
from evaluation.fault_injection import (FaultInjector, InjectedToolFailure, ToolFault,
                                        wrap_tools)


def spec(handler):
    return make_tool("get_order", "demo", {"order_id": {"type": "string"}},
                     handler, required=["order_id"])


def invoke(tools, args=None):
    return asyncio.run(tools.handler(None, args or {"order_id": "ORD-1001"}))


def test_not_found_on_second_call_is_one_shot():
    injector = FaultInjector([ToolFault("get_order", "not_found", on_call=2)])
    tools = wrap_tools({"get_order": spec(lambda req, args: {"success": True, "data": {}})},
                       injector)["get_order"]
    assert invoke(tools)["success"] is True
    failed = invoke(tools)
    assert failed["success"] is False and failed["error"]["code"] == "not_found"
    assert injector.events == [{"tool": "get_order", "call_index": 2,
                                "kind": "not_found", "error_code": "not_found"}]


def test_timeout_and_execution_failure_raise_typed_errors():
    timeout = wrap_tools({"get_order": spec(lambda req, args: {"success": True})},
                         FaultInjector([ToolFault("get_order", "timeout")]))["get_order"]
    with pytest.raises(asyncio.TimeoutError):
        invoke(timeout)
    failure = wrap_tools({"get_order": spec(lambda req, args: {"success": True})},
                         FaultInjector([ToolFault("get_order", "execution_failure")]))["get_order"]
    with pytest.raises(InjectedToolFailure):
        invoke(failure)


def test_sticky_fault_and_invalid_arguments_payload():
    sticky = wrap_tools({"get_order": spec(lambda req, args: {"success": True})},
                        FaultInjector([ToolFault("get_order", "dependency_failure",
                                                 on_call=1, mode="sticky")]))["get_order"]
    assert invoke(sticky)["error"]["code"] == "dependency_failure"
    assert invoke(sticky)["error"]["code"] == "dependency_failure"
    invalid = wrap_tools({"get_order": spec(lambda req, args: {"success": True})},
                         FaultInjector([ToolFault("get_order", "invalid_arguments")]))["get_order"]
    assert invoke(invalid)["error_code"] == "invalid_arguments"


def test_rag_adapter_fault_shape():
    rag = make_tool("search_knowledge_base", "demo", {"query": {"type": "string"}},
                    lambda req, args: {"success": True, "results": []}, required=["query"])
    wrapped = wrap_tools({"search_knowledge_base": rag},
                         FaultInjector([ToolFault("search_knowledge_base", "dependency_failure")])
                         )["search_knowledge_base"]
    payload = asyncio.run(wrapped.handler(None, {"query": "退款"}))
    assert payload["success"] is False
    assert payload["retrieval_status"] == "degraded"
    assert payload["error_code"] == "dependency_failure"
