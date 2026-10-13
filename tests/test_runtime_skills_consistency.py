"""Real SkillManager/SupportRuntime prompt delivery, Fake SDK, no HTTP/model/DB.

This verifies instructions reaching the SDK boundary, not model obedience.
"""
import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agents.agent_orchestrator import Request
from agents.support_agent import AllRoleSkills, SingleSupportAgent, SupportRuntime
from core.skill_loader import SkillManager
from policies import PolicyDecisionType, PolicyEngine
from providers.models import Order
from tests.auth_helpers import customer
from tests.test_policy_engine import provider_order, with_order, EVALUATED_AT

ROOT = Path(__file__).resolve().parents[1]


class CaptureSDK:
    def __init__(self):
        self.messages = self
        self.calls = []
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return NS(content=[NS(type='text',text='仅用于提示词注入测试的固定回复。')])


def capture(message):
    manager = SkillManager(str(ROOT/'skills'), max_prompt_chars=5000)
    manager.load()
    sdk = CaptureSDK()
    runtime = SupportRuntime('fake-key','fake-model',skill_manager=manager,client=sdk)
    req = Request(message,'customer-1','skills-test',principal=customer('customer-1'))
    result = asyncio.run(runtime.run(req))
    return manager,sdk,runtime,req,result


def dynamic(message):
    _,sdk,_,_,_ = capture(message)
    assert len(sdk.calls) == 1
    return sdk.calls[0]['system'].split('[动态 Skills]\n',1)[1]


def test_runtime_loads_only_three_real_skills_and_ignores_legacy_role_labels():
    manager,sdk,runtime,req,result = capture('退款')
    assert not manager.errors and len(manager.skills)==3
    assert {Path(s.path).parent.name for s in manager.skills} == {'billing_support','general_customer_service','technical_support'}
    assert manager.prompt_for('退款','support') == ''
    assert '账单退款处理规范' in AllRoleSkills(manager).prompt_for('退款','support')
    assert '账单退款处理规范' in sdk.calls[0]['system']
    assert isinstance(runtime.make_agent(),SingleSupportAgent)
    assert runtime.supports_routing is False and req.intent is None
    assert runtime.make_agent()._build_role_packet(req)==''
    assert result.agent_type.value=='support'


@pytest.mark.parametrize('old_instruction', [
    '退款金额以实际支付金额和平台规则为准',
    '如果涉及已使用服务、虚拟商品、活动价、企业合同、部分退款，必须说明需要人工审核',
    '说明退款通过后通常原路退回',
    '取消订阅通常只影响后续续费',
])
def test_conflicting_billing_instruction_never_reaches_sdk(old_instruction):
    assert old_instruction not in dynamic('退款发票订阅')


def test_refund_money_and_approval_context_reaches_sdk():
    prompt = dynamic('退款订单')
    for text in ('order.total_amount','部分退款不自动要求人工审核','超过500元','恰好500元',
                 'reviewer','review_customers','非申请人','执行前','模拟退款申请',
                 '同键同参数','未实现币种准入或换算校验'):
        assert text in prompt
    assert 'paid_amount' not in Order.model_fields


def test_general_single_static_live_action_and_owner_boundaries_reach_sdk():
    prompt = dynamic('订单会员客服')
    assert '识别是否需要专属 Agent' not in prompt
    for text in ('SingleSupportAgent','静态知识','Provider','ActionService',
                 '会员与积分','运费报价','未找到可访问','模拟记录','request_handoff','缺少证据'):
        assert text in prompt


def test_technical_does_not_offer_unimplemented_password_or_real_escalation():
    prompt = dynamic('401 登录失败')
    assert '可以建议重置密码或重新授权' not in prompt
    for text in ('SingleSupportAgent','未实现密码重置','不能单独证明','模拟记录','request_handoff'):
        assert text in prompt


def test_all_three_skills_critical_boundaries_survive_actual_default_budget():
    manager,sdk,_,_,_ = capture('订单退款接口500发票会员')
    system = sdk.calls[0]['system']
    for name in ('账单退款处理规范','通用客服接待规范','技术支持处理规范'):
        assert name in system
    for text in ('order.total_amount','review_customers','未实现会员与积分','未实现密码重置'):
        assert text in system
    assert all(len(s.content)<=3200 for s in manager.skills)
    assert sum(len(s.to_prompt_block()) for s in manager.skills)+4 <= manager.max_prompt_chars


def test_explicit_handoff_bypasses_model_even_when_skill_matches():
    manager,sdk,runtime,req,result = capture('请转人工客服')
    assert manager.prompt_for(req.message,None)
    assert sdk.calls==[] and result.escalated and result.handoff.handoff_created
    assert '模拟人工交接记录' in result.response and '不代表真实客服已接单' in result.response
    record = runtime.handoff_service.get(result.handoff.handoff_id,req.principal)
    assert record['simulated'] is True


@pytest.mark.parametrize('amount,decision', [(None,'require_approval'),('100','allow'),
    ('500','allow'),('500.01','require_approval'),('801','deny'),('0','deny')])
def test_skill_explained_amount_boundary_uses_real_unchanged_policy(amount,decision):
    order = with_order(provider_order(), total_amount=Decimal('800'))
    result = PolicyEngine().evaluate_refund(order,customer_id='customer-1',evaluated_at=EVALUATED_AT,amount=amount)
    assert result.decision.value==decision
    prompt=dynamic('退款')
    assert 'order.total_amount' in prompt
    assert '部分退款不自动要求人工审核' in prompt


def test_no_match_does_not_fabricate_skill_injection():
    _,sdk,_,_,_ = capture('xyzq')
    assert '[动态 Skills]' not in sdk.calls[0]['system']
