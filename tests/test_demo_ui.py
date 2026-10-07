"""Demo HTTP contract with fake SDK/Memory; not real-model integration evidence."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import main
from agents.support_agent import SupportRuntime
from agents.agent_orchestrator import Request
from agents.tools import build_shared_rag_tools
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient
from tests.test_topology_comparison import NOW
from evaluation.prepare_online_eval import prepare
from evaluation.topology_experiment import isolated_business


def test_demo_static_smoke():
    http = TestClient(main.app)
    assert http.get('/demo').status_code == 200
    assert 'CartCare' in http.get('/demo').text
    assert http.get('/demo-assets/demo.js').status_code == 200
    assert http.get('/demo-assets/style.css').status_code == 200
    scenarios = http.get('/demo-assets/scenarios.json').json()
    assert len(scenarios) == 10
    assert next(c for c in scenarios if c['id'] == 'ownership_violation')['user_id'] == 'customer-2'


@pytest.mark.parametrize('status', ['usable', 'low_confidence', 'no_answer', 'degraded'])
def test_chat_trace_rendering_contract(monkeypatch, status):
    citation = {'reference': 'demo-policy@v1#chunk-0', 'document_id': 'demo-policy',
                'source': 'demo:policy', 'policy_version': 'v1', 'chunk_index': 0}
    class Rag:
        async def search_with_rewrite(self, *args, **kwargs):
            return SimpleNamespace(success=status != 'degraded', retrieval_status=status,
                citations=[citation], data=[{'document_id': 'demo-policy', 'title': '退款政策',
                    'chunk_index': 0, 'citation': citation, 'content': '7 天'}], reranked=False)
    class Memory(EmptyMemory):
        async def get_context(self, *args, **kwargs):
            return SimpleNamespace(recent_messages=[], relevant_history=['private topic'],
                user_profile={'reply_preference': 'private preference'}, summary='private summary',
                to_prompt_text=lambda: 'private memory')
    runtime = SupportRuntime('test', 'test', client=FakeClient('search_knowledge_base', {'query': '退款政策'}))
    runtime.set_shared_tools(build_shared_rag_tools(Rag()))
    monkeypatch.setattr(main, '_orchestrator', runtime)
    monkeypatch.setattr(main, '_memory', Memory())
    http = TestClient(main.app)
    body = http.post('/chat', json={'message': '退款政策', 'user_id': 'customer-1'}).json()
    envelope = http.get('/trace/tool/' + body['request_id']).json()
    assert envelope['found']
    trace = envelope['trace']
    assert trace['request_id'] == body['request_id']
    assert trace['topology'] == 'single' and trace['agent_type'] == 'support'
    for field in ['primary_agent', 'supporting_agents', 'routing_reason', 'routing_confidence']:
        assert body[field] is None and trace[field] is None
    call = trace['tool_calls'][0]
    assert call['request_id'] == body['request_id']
    assert call['risk_level'] == 'read' and call['validated_input'] == {'query': '退款政策'}
    assert call['retrieval_status'] == body['retrieval_status'] == status
    assert trace['memory']['relevant_history_count'] == 1
    assert trace['memory']['profile_field_count'] == 1
    assert trace['memory']['summary_present']
    assert trace['memory']['write_status'] == 'completed'
    assert trace['memory']['profile_update_status'] == 'scheduled_unobserved'
    assert trace['request_latency_ms'] >= trace['latency_ms'] - 0.1
    assert 'private' not in str(trace)
    if status == 'usable':
        assert body['citations'] == [citation]
        assert call['retrieval_hits'][0]['title'] == '退款政策'
    else:
        assert not body['citations'] and not call['citations'] and not call['retrieval_hits']


def test_memory_write_failure_is_not_rendered_as_completed(monkeypatch):
    class BrokenMemory(EmptyMemory):
        async def add_message(self, *args):
            raise RuntimeError('write failure')
    client = FakeClient('unused', {})
    client.responses = [SimpleNamespace(content=[SimpleNamespace(type='text', text='回复')])]
    runtime = SupportRuntime('test', 'test', client=client)
    monkeypatch.setattr(main, '_orchestrator', runtime)
    monkeypatch.setattr(main, '_memory', BrokenMemory())
    http = TestClient(main.app, raise_server_exceptions=False)
    assert http.post('/chat', json={'message': '你好'}).status_code == 500
    trace = http.get('/trace/tools').json()['items'][0]
    assert trace['memory']['write_status'] == 'failed'
    assert trace['memory']['profile_update_status'] == 'not_scheduled'


def test_demo_reject_and_resume_http_contract(monkeypatch):
    tools, service, backend = isolated_business(prepare(NOW)[0], NOW)
    runtime = SupportRuntime('test', 'test', client=FakeClient('request_refund', {
        'order_id': 'ORD-T09-REFUND-APPROVAL', 'amount': 600}))
    runtime.set_shared_tools(tools)
    monkeypatch.setattr(main, '_orchestrator', runtime)
    monkeypatch.setattr(main, '_memory', EmptyMemory())
    monkeypatch.setattr(main, '_action_service', service)
    http = TestClient(main.app)
    chat = http.post('/chat', json={'message': '退款', 'user_id': 'customer-1'}).json()
    original = http.get('/trace/tool/' + chat['request_id']).json()['trace']['tool_calls'][0]
    action = original['action_result']
    assert original['risk_level'] == 'dangerous'
    assert action['policy_decision'] == 'require_approval'
    path = '/actions/' + action['action_id']
    command = {'user_id': 'customer-1', 'request_id': chat['request_id']}
    assert http.post(path + '/resume', json=command).json()['status'] == 'awaiting_approval'
    assert http.post(path + '/reject', json=command).json()['status'] == 'rejected'
    assert http.post(path + '/resume', json=command).json()['status'] == 'rejected'
    assert http.get(path, params={'user_id': 'customer-1'}).json()['status'] == 'rejected'
    assert not backend.calls
    snapshot = http.get('/trace/tool/' + chat['request_id']).json()['trace']['tool_calls'][0]
    assert snapshot['action_result']['status'] == 'awaiting_approval'


@pytest.mark.parametrize('tool,args,field', [
    ('inspect_request_context', {}, 'context_available'),
    ('create_handoff_summary', {'reason': 'needs review'}, 'reason'),
])
def test_helper_trace_returns_observed_output_without_raw_context(tool, args, field):
    import asyncio
    runtime = SupportRuntime('test', 'test', client=FakeClient(tool, args))
    result = asyncio.run(runtime.run(Request('hello', 'demo', 'conv', context='PRIVATE_MEMORY')))
    call = result.tool_traces[0]
    assert field in call['helper_result']
    assert call['success']
    assert 'PRIVATE_MEMORY' not in str(call)
