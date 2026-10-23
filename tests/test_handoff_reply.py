"""REPLY offline regressions using unchanged, saved real model text.

No app lifespan, network API, live dependency, or model call is used.
"""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from core.llm_utils import extract_text_content
from tests.auth_helpers import customer
from tests.test_handoff import setup

E2E = Path(__file__).resolve().parents[1]/'evaluation/reports/hardening/A05/chat-e2e-20261014'


def real_failure(name):
    manifest = json.loads((E2E/'artifact_hashes.json').read_text(encoding='utf-8'))
    for file in (name,'model_ledger.json'):
        assert hashlib.sha256((E2E/file).read_bytes()).hexdigest()==manifest[file]
    saved = json.loads((E2E/name).read_text(encoding='utf-8'))
    ledger = json.loads((E2E/'model_ledger.json').read_text(encoding='utf-8'))
    lo,hi = saved['model_request_range']
    events = [e for e in ledger['events'] if lo<=e['number']<=hi]
    assert len(events)==1
    assert events[0]['tool_results_sent']==[]
    assert all(b['type']=='text' for b in events[0]['content'])
    return saved,extract_text_content(events[0]['content'])


class FixedTextSDK:
    def __init__(self,text):
        self.text,self.calls = text,[]
        self.messages = self

    async def create(self,**kwargs):
        self.calls.append(kwargs)
        return NS(content=[NS(type='text',text=self.text)])


def offline_replay(name):
    saved,raw = real_failure(name)
    sdk = FixedTextSDK(raw)
    runtime = SupportRuntime('offline-only','fixed-text',client=sdk)
    req = Request(saved['request']['message'],'customer-1','reply-offline',principal=customer())
    result = asyncio.run(runtime.run(req))
    from api.main import collect_rag_evidence,render_rag_citations
    status,citations = collect_rag_evidence(result.tool_traces)
    return saved,raw,result,runtime,sdk,render_rag_citations(result.response,citations)


@pytest.mark.parametrize('name',['case_03.json','case_08.json','repair_case10.json'])
def test_saved_real_model_body_and_format_survive_reply_processing(name):
    saved,raw,result,runtime,sdk,api_text = offline_replay(name)
    assert result.response==raw
    assert api_text==raw
    assert result.tool_traces==[] and len(sdk.calls)==1
    assert runtime.handoff_service._records==runtime.handoff_service._attempts=={}
    assert not result.escalated and not result.handoff.handoff_created


@pytest.mark.usefixtures('authenticated_http')
@pytest.mark.parametrize('name',['case_03.json','case_08.json','repair_case10.json'])
def test_fixed_real_text_through_actual_api_handler(monkeypatch,name):
    saved,raw = real_failure(name)
    http,runtime,sdk = setup(monkeypatch,text=raw)
    body = http.post('/chat',json={'message':saved['request']['message']}).json()
    assert body['response']==raw
    assert body['tools_used']==[] and body['handoff']['handoff_created'] is False
    assert runtime.handoff_service._records=={}


@pytest.mark.usefixtures('authenticated_http')
@pytest.mark.parametrize('text',[
    '单笔超过500元需要人工审核，恰好500元不因金额触发审批。',
    '模拟记录不代表真人客服已接单，也不代表已经发送通知。',
    '目前无法确认已有真人客服接手。',
    '不能保证真人客服已经接手。',
    '如果已创建人工交接记录，可查看编号；目前尚未确认。',
    '没有成功转接人工客服。',
    '已创建退款申请，需要人工审核；申请完成不代表资金到账。',
    'A simulated record does not mean we have created a handoff.',
    '订单为已发货状态；退款申请成功不代表资金到账。',
    '关于会员：\n\n当前未实现积分计算；可以说明能力边界。',
])
def test_correct_explanation_is_unchanged_without_unrelated_handoff_footer(monkeypatch,text):
    http,runtime,sdk = setup(monkeypatch,text=text)
    body = http.post('/chat',json={'message':'请解释当前业务规则。'}).json()
    assert body['response']==text
    assert not body['handoff']['handoff_created'] and runtime.handoff_service._records=={}


@pytest.mark.usefixtures('authenticated_http')
@pytest.mark.parametrize('text',[
    '已成功转接人工客服。',
    '我已经为您创建模拟人工交接记录。',
    '人工交接记录已创建成功。',
    '真人客服已经接单。',
    '已有真人客服接手了。',
    '无法确认真人接单，但我已经帮你创建交接记录。',
    'I have created a handoff record.',
    'You have already been transferred to a human specialist.',
])
def test_unconfirmed_completion_gets_whole_safe_reply_not_fragment_deletion(monkeypatch,text):
    http,runtime,sdk = setup(monkeypatch,text='**处理结果：**\n\n'+text+'\n\n请查看上述记录。')
    body = http.post('/chat',json={'message':'请查询订单。'}).json()
    assert body['response']=='本次未创建人工交接记录。'
    assert not body['handoff']['handoff_created'] and runtime.handoff_service._records=={}


@pytest.mark.usefixtures('authenticated_http')
def test_rejected_handoff_tool_cannot_turn_failed_receipt_into_success(monkeypatch):
    http,runtime,sdk = setup(monkeypatch,text='交接记录已创建成功，真人客服已接单。',
        tool='request_handoff',args={'reason_code':'explicit_request'})
    body = http.post('/chat',json={'message':'请解释退款政策。'}).json()
    assert body['response']=='本次未创建人工交接记录。'
    assert not body['handoff']['handoff_created'] and runtime.handoff_service._records=={}
    assert runtime.get_tool_trace(body['request_id'])['tool_calls'][0]['handoff_result']['error_code']=='handoff_policy_rejected'


@pytest.mark.usefixtures('authenticated_http')
def test_legal_created_handoff_is_only_simulated_receipt(monkeypatch):
    http,runtime,sdk = setup(monkeypatch,text='真人客服已经接单。')
    body = http.post('/chat',json={'message':'请帮我转人工客服。'}).json()
    assert body['handoff']['handoff_created'] and len(runtime.handoff_service._records)==1
    assert body['response'].startswith('已创建模拟人工交接记录。')
    assert '不代表真实客服已接单' in body['response'] and sdk.calls==[]
