"""Prompt contract: generic grounding and explicit-action rules must stay present.

These assertions are a regression guard, not proof that the model follows them;
the real-model H1-1 E2E is the behavioural evidence.
"""
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from tests.auth_helpers import customer
from tests.test_topology_comparison import FakeClient


def _prompt(message="退款"):
    runtime = SupportRuntime("test", "test", client=FakeClient("unused", {}))
    request = Request(message, "customer-1", "test", principal=customer("customer-1"))
    return runtime.make_agent()._build_system_prompt(request)


def test_prompt_requires_knowledge_grounding_for_static_policy():
    prompt = _prompt("退款需要满足什么条件？")
    assert "静态政策、FAQ、流程和规则类问题" in prompt
    assert "应先调用 search_knowledge_base" in prompt
    assert "没有可用引用时只说明无法确认" in prompt


def test_prompt_submits_explicit_refund_request_without_reconfirmation():
    prompt = _prompt("为订单 ORD-1 申请退款 600 元")
    assert "明确给出订单号、金额并直接要求申请退款" in prompt
    assert "视为已授权提交" in prompt
    assert "先调用 get_order 和 get_refund_status 核对" in prompt
    assert "条件明确不满足时说明原因，不提交" in prompt
    assert "条件满足或无法确定时，直接调用 request_refund 提交" in prompt
    assert "不要再次询问是否确认" in prompt
    assert "是否批准、拒绝或执行仍由后端" in prompt
