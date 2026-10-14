"""ANS24-ROUTE: requested creation vs. read-only handoff explanations.

Fake SDK/TestClient only; production lifespan and live dependencies never run.
"""
import pytest

from agents.agent_orchestrator import Request
from core.handoff import HandoffService, explicit_handoff
from tests.auth_helpers import customer
from tests.test_handoff import setup


REQUESTS = [
    '请帮我转人工客服。',
    '我想联系人工客服。',
    '可以帮我转人工客服吗？',
    '请问能否帮我联系人工客服？',
    '是否能帮我转人工客服？',
    'Please transfer to a human.',
    '模拟记录成功是否说明已转人工客服？请帮我转人工客服。',
    '请帮我转人工客服确认记录是否已经完成。',
]
QUESTIONS = [
    '模拟记录成功是否说明已转人工客服？',
    '订单查询：模拟人工交接记录创建成功是否说明已转人工客服？',
    '记录创建成功是不是代表已联系人工客服？',
    '交接回执是否意味着已转接人工客服？',
    '现在是否已经帮我转人工客服？',
    '有没有联系人工客服？',
    '转人工客服成功了吗？',
    '转人工客服是什么意思？',
    '转人工客服的条件是什么？',
    '“转人工客服”是什么意思？',
    '记录上写着“转人工客服”，这是什么意思？',
    '什么情况下需要人工客服？',
    'How does transfer to a human work?',
    '我不需要人工客服，请说明模拟交接记录是什么意思。',
    '请查询订单ORD-1001。',
    '退款政策的500元审批规则是什么？',
]

pytestmark = pytest.mark.usefixtures('authenticated_http')


@pytest.mark.parametrize('message,expected',[(m,True) for m in REQUESTS]+[(m,False) for m in QUESTIONS])
def test_chat_creates_only_for_current_creation_request(monkeypatch,message,expected):
    http,runtime,sdk = setup(monkeypatch,text='请提供订单号。')
    before = (len(runtime.handoff_service._records),len(runtime.handoff_service._attempts))
    body = http.post('/chat',json={'message':message,'conv_id':'route-regression'}).json()
    trace = runtime.get_tool_trace(body['request_id'])
    assert explicit_handoff(message) is expected
    assert body['handoff']['handoff_created'] is expected
    assert body['escalated'] is expected
    assert (len(runtime.handoff_service._records),len(runtime.handoff_service._attempts)) == (
        before[0]+int(expected),before[1]+int(expected))
    if expected:
        assert sdk.calls==[]
        assert trace['tool_calls'][0]['tool_use_id']=='deterministic_handoff_gate'
        assert body['handoff']['handoff_id'] in runtime.handoff_service._records
    else:
        assert len(sdk.calls)==1
        assert trace['tool_calls']==[]


@pytest.mark.parametrize('message',[QUESTIONS[0],QUESTIONS[4],QUESTIONS[6]])
def test_model_explicit_tool_request_cannot_bypass_read_only_question(monkeypatch,message):
    http,runtime,sdk = setup(monkeypatch,tool='request_handoff',args={'reason_code':'explicit_request'})
    body = http.post('/chat',json={'message':message}).json()
    assert not body['handoff']['handoff_created']
    assert runtime.handoff_service._records==runtime.handoff_service._attempts=={}
    trace = runtime.get_tool_trace(body['request_id'])
    assert trace['tool_calls'][0]['handoff_result']['error_code']=='handoff_policy_rejected'


def test_service_keeps_valid_request_owner_and_idempotent_result():
    service = HandoffService()
    req = Request('请帮我转人工客服。','customer-1','route-session',
        principal=customer(),handoff_key='same-request')
    first = service.request(req,'explicit_request')
    second = service.request(req,'explicit_request')
    assert first.handoff_created and second.reused and second.handoff_id==first.handoff_id
    assert len(service._records)==len(service._attempts)==1
    assert service.get(first.handoff_id,customer('customer-2')) is None
