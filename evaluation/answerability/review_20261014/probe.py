"""Actual authenticated /chat via TestClient, without lifespan/live dependencies.

All business, actions, memory, KB and handoff state is new and process-local.
SDK requests are immutable snapshots of what the fake boundary actually received.
"""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
from fastapi import HTTPException, Request as HTTPRequest
from pytest import MonkeyPatch

from agents.support_agent import SupportRuntime
from agents.tools import build_action_tools, build_business_tools, build_shared_rag_tools
from actions import ActionService, InMemoryBusinessActionBackend
from api import main as api
from core.auth import Principal, get_principal
from core.handoff import explicit_handoff
from core.skill_loader import SkillManager
from evaluation.answerability.harness import (
    ROOT, load_dataset, make_kb, manager_for, request, AdversarialSDK,
)
from providers.mock_backend import InMemoryBusinessBackend

OUT = ROOT/'evaluation/reports/hardening/A05/answerability-gold-review-20261014'
BASE_RULES = ('主题相关不等于事实充分','逐项','原始问题','不支持该功能','依赖故障')


def plain(value):
    if isinstance(value, dict):
        return {k:plain(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):
        return [plain(v) for v in value]
    if hasattr(value,'model_dump'):
        return plain(value.model_dump(mode='json'))
    if isinstance(value,NS):
        return plain(vars(value))
    return value


class RecordingSDK(AdversarialSDK):
    def __init__(self,case,mode='adversarial'):
        super().__init__(case)
        self.snapshots = []
        self.mode = mode

    async def create(self, **kwargs):
        self.snapshots.append(plain(copy.deepcopy(kwargs)))
        if self.mode == 'adversarial':
            return await super().create(**kwargs)
        self.calls.append(kwargs)
        if len(self.calls)==1 and self.mode=='truthful_rag':
            return NS(content=[NS(type='tool_use',id='rag',name='search_knowledge_base',
                input={'query':self.case['query']})])
        return NS(content=[NS(type='text',text='模拟人工交接记录创建成功不代表真人接单，也不代表通知已发送。')])


class IsolatedMemory:
    def __init__(self):
        self.writes = []

    async def get_context(self,*args,**kwargs):
        return NS(recent_messages=[],to_prompt_text=lambda:'')

    async def add_message(self,user,conv,role,text):
        self.writes.append({'user':user,'conv':conv,'role':role.value,'text':text})

    async def update_profile(self,*args):
        pass


def build(case,mode='adversarial'):
    kb = make_kb(case['scenario'])
    sdk = RecordingSDK(case,mode)
    skills = SkillManager(str(ROOT/'skills'),max_prompt_chars=5000)
    skills.load()
    runtime = SupportRuntime('fake-only','fake-model',skill_manager=skills,client=sdk)
    backend = InMemoryBusinessBackend(json.loads((ROOT/'tests/fixtures/business_provider_data.json').read_text(encoding='utf-8')),
        fail_operations={'get_order'} if case['scenario']=='provider_failure' else ())
    service = ActionService(business_backend=backend,action_backend=InMemoryBusinessActionBackend(backend.state))
    manager = manager_for(kb)
    runtime.set_shared_tools({**build_shared_rag_tools(manager),**build_business_tools(backend),**build_action_tools(service)})
    return runtime,sdk,backend,service,kb


def snapshot(runtime,backend,service,memory):
    return copy.deepcopy({'business':backend.state.data,'actions':plain(service._store._actions),
        'handoff_records':runtime.handoff_service._records,
        'handoff_attempts_count':len(runtime.handoff_service._attempts),'memory_writes':memory.writes})


def route_probe(query,mode='truthful_rag'):
    original = load_dataset()['cases'][23]
    case = {**original,'query':query}
    runtime,sdk,backend,service,kb = build(case,mode)
    memory = IsolatedMemory()
    before = snapshot(runtime,backend,service,memory)

    def authenticated(req: HTTPRequest):
        if req.headers.get('authorization')!='Bearer isolated-review-test-token':
            raise HTTPException(401,'isolated test authentication')
        # Customer only; do not use the older test fixture's extra admin role.
        return Principal('isolated-review-subject','customer-1',frozenset({'customer'}))

    with MonkeyPatch.context() as patch:
        patch.setitem(api.app.dependency_overrides,get_principal,authenticated)
        for name,value in {'_orchestrator':runtime,'_memory':memory,'_action_service':service,
                           '_tool_manager':None,'_skill_manager':None}.items():
            patch.setattr(api,name,value)
        # Not a context manager: no app lifespan or network listeners.
        http = TestClient(api.app,headers={'Authorization':'Bearer isolated-review-test-token'})
        try:
            response = http.post('/chat',json={'message':query,'conv_id':'isolated-review'})
        finally:
            http.close()
    body = response.json()
    trace = runtime.get_tool_trace(body.get('request_id',''))
    after = snapshot(runtime,backend,service,memory)
    return {'query':query,'scope':'independent process-local state + authenticated TestClient; no lifespan/live services',
        'matched_explicit_handoff':bool(explicit_handoff(query)),
        'matched_branch':'deterministic_handoff_gate' if explicit_handoff(query) else 'model_tool_loop',
        'http_status':response.status_code,'body':body,'trace':trace,'sdk_calls':len(sdk.snapshots),
        'sdk_requests':sdk.snapshots,'state_before':before,'state_after':after,
        'state_diff':{'business_changed':before['business']!=after['business'],
            'action_count_before':len(before['actions']),'action_count_after':len(after['actions']),
            'handoff_count_before':len(before['handoff_records']),'handoff_count_after':len(after['handoff_records']),
            'handoff_attempts_delta':after['handoff_attempts_count']-before['handoff_attempts_count'],
            'memory_writes_delta':len(after['memory_writes'])-len(before['memory_writes'])}}


async def delivery(case):
    runtime,sdk,backend,service,kb = build(case)
    req = request(case['query'],'customer-2' if case['scenario']=='cross_owner' else 'customer-1')
    constructed = runtime.make_agent()._build_system_prompt(req)
    before = len(runtime.handoff_service._records)
    result = await runtime.run(req)
    payloads = []
    for captured in sdk.snapshots:
        for message in captured['messages']:
            if isinstance(message['content'],list):
                for block in message['content']:
                    if isinstance(block,dict) and block.get('type')=='tool_result':
                        payloads.append(json.loads(block['content']))
    rag = next((p for p in payloads if 'retrieval_status' in p),None)
    trace = runtime.get_tool_trace(result.request_id)
    return {'id':case['id'],'query':case['query'],
        'explicit_gate':bool(explicit_handoff(case['query'])),
        'constructed_prompt_has_rules':all(s in constructed for s in BASE_RULES),
        'sdk_invoked':bool(sdk.snapshots),'support_sdk_calls':len(sdk.snapshots),
        'every_sdk_system_has_rules':bool(sdk.snapshots) and all(all(s in c.get('system','') for s in BASE_RULES) for c in sdk.snapshots),
        'final_sdk_contains_base_rules':bool(sdk.snapshots) and all(s in sdk.snapshots[-1].get('system','') for s in BASE_RULES),
        'rag_payload_answer_guidance_present':bool(rag and rag.get('answer_guidance')),
        'guidance_in_final_sdk_tool_message':bool(rag and rag.get('answer_guidance') and sdk.snapshots and
            rag['answer_guidance'] in json.dumps(sdk.snapshots[-1]['messages'],ensure_ascii=False)),
        'rag_payload':rag,'sdk_requests':sdk.snapshots,'trace':trace,'final_fake_response':result.response,
        'new_handoff_records':len(runtime.handoff_service._records)-before}


def main():
    # Probe variants are observations only; never replace a frozen Query.
    queries = [
        ('ANS-24-exact',load_dataset()['cases'][23]['query']),
        ('same-fact-question-variant','订单查询：模拟人工交接记录创建成功是否说明已转人工客服？'),
        ('explicit-request-control','请帮我转人工客服。'),
        ('negated-request-control','我不需要人工客服，请说明模拟交接记录是什么意思。'),
    ]
    routes = [{'probe_id':id,**route_probe(query)} for id,query in queries]
    (OUT/'handoff_routes.json').write_text(json.dumps(routes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows = [asyncio.run(delivery(c)) for c in load_dataset()['cases']]
    (OUT/'sdk_delivery_actual.json').write_text(json.dumps({'scope':'captured immutable actual Fake SDK requests; not model obedience',
        'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'route_probes':[{'id':r['probe_id'],'gate':r['matched_branch'],'sdk':r['sdk_calls'],
        'handoff_delta':r['state_diff']['handoff_count_after']-r['state_diff']['handoff_count_before'],
        'reply':r['body']['response']} for r in routes],
        'sdk_question_denominator':sum(r['sdk_invoked'] for r in rows)},ensure_ascii=False))


if __name__=='__main__':
    main()
