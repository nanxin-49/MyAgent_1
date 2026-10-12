"""N07 deterministic reproduction through the real rerank parser, no model/service."""
import asyncio
from types import SimpleNamespace
import pytest
from tests.test_rag_contract import knowledge_base, POLICY, manager_for
from mcp.tool_manager import MCPToolManager


class FakeMessages:
    def __init__(self, output):
        self.output = output
        self.calls = 0
    async def create(self, **kwargs):
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(content=[SimpleNamespace(type='text', text=self.output)])


def setup(output='[1,0]', count=2):
    kb = knowledge_base()
    kb.add_documents([{**POLICY, 'document_id': f'policy-{i}', 'content': f'policy content {i}'} for i in range(count)])
    manager = manager_for(kb)
    # Restore the executable parser; helper normally stubs rerank.
    manager._rerank = MCPToolManager._rerank.__get__(manager)
    messages = FakeMessages(output)
    manager._client = SimpleNamespace(messages=messages)
    return kb, manager, messages


def run(manager, top_k=1):
    return asyncio.run(manager.search_with_rewrite('knowledge_search', 'policy', top_k=top_k))


def test_audit_empty_array_uses_verified_fallback_without_claiming_rerank():
    kb, manager, _ = setup('[]')
    result = run(manager)
    assert result.retrieval_status == 'usable' and len(result.data) == len(result.citations) == 1
    assert result.reranked is False
    assert result.data[0]['document_id'] == 'policy-0'


def test_skipped_rerank_does_not_claim_execution():
    _, manager, messages = setup(count=1)
    result = run(manager)
    assert result.reranked is False
    assert messages.calls == 0


def test_service_failure_does_not_claim_successful_rerank():
    _, manager, _ = setup(RuntimeError('synthetic SDK failure'))
    result = run(manager)
    assert result.reranked is False
    assert result.retrieval_status == 'usable' and len(result.citations) == 1


def test_normal_empty_recall_is_successful_no_answer():
    _, manager, messages = setup(count=0)
    result = run(manager)
    assert result.success is True
    assert result.retrieval_status == 'no_answer'
    assert result.data == result.citations == []
    assert result.reranked is False and messages.calls == 0


@pytest.mark.parametrize('output', ['not JSON', '{}', 'null', '42', '"[1,0]"',
    '[0]', '[99,0]', '[-1,0]', '[0,0]', '[0,null]', '[false,1]', '[0,"1"]', '[0,1.0]',
    '[0,1] trailing text', '```json\n[1,0]\n```'])
def test_malformed_sort_is_rejected_as_a_whole(output):
    _, manager, _ = setup(output)
    result = run(manager)
    assert result.success and result.retrieval_status == 'usable'
    assert result.reranked is False and result.rerank_status == 'invalid_output_fallback'
    assert [h['document_id'] for h in result.data] == ['policy-0']
    assert result.citations == [result.data[0]['citation']]


def test_valid_order_top_k_and_hashes():
    import hashlib
    _, manager, messages = setup('[2,0,1]', count=3)
    result = run(manager, top_k=2)
    assert result.success and result.reranked and result.rerank_status == 'ranked'
    assert messages.calls == 1
    assert [h['document_id'] for h in result.data] == ['policy-2', 'policy-0']
    for hit, citation in zip(result.data, result.citations):
        assert citation == hit['citation']
        assert citation['content_hash'] == hashlib.sha256(hit['content'].encode()).hexdigest()


def test_timeout_uses_checked_fallback_with_false_reranked():
    _, manager, _ = setup()
    class SlowMessages:
        cancelled = False
        async def create(self, **kwargs):
            try:
                await asyncio.sleep(1)
            finally:
                self.cancelled = True
    slow = SlowMessages()
    manager._client.messages = slow
    manager._tools['knowledge_search'].timeout_s = .01
    from mcp.tool_manager import ToolResult
    hits = manager._tools['knowledge_search'].handler.__self__.search('policy', 2)
    async def immediate_recall(*args, **kwargs):
        return ToolResult(True, hits, 'knowledge_search')
    manager.call = immediate_recall
    result = run(manager)
    assert slow.cancelled
    assert result.rerank_status == 'timeout_fallback' and result.reranked is False
    assert result.retrieval_status == 'usable' and len(result.citations) == 1


@pytest.mark.parametrize('change', ['update', 'revoke', 'supersede'])
@pytest.mark.parametrize('output', ['[1,0]', '[]', RuntimeError('synthetic failure')])
def test_n06_versions_cannot_reenter_through_ranking_or_fallback(change, output):
    kb, manager, _ = setup()
    async def create(**kwargs):
        for i in range(2):
            doc = {**POLICY, 'document_id': f'policy-{i}', 'content': f'policy content {i}'}
            if change == 'update':
                doc['content'] = 'replacement content'
            elif change == 'revoke':
                doc['publication_status'] = 'revoked'
            else:
                doc.update(policy_version='v2', supersedes=[POLICY['policy_version']])
            kb.add_documents([doc])
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(content=[SimpleNamespace(type='text', text=output)])
    manager._client.messages.create = create
    result = run(manager)
    assert result.success and result.retrieval_status == 'no_answer'
    assert result.data == result.citations == []
    assert result.reranked is (output == '[1,0]')


def test_revalidation_service_failure_is_degraded():
    kb, manager, _ = setup()
    async def broken(hits):
        raise RuntimeError('synthetic Chroma read failure')
    kb.validate_hits_async = broken
    result = run(manager)
    assert not result.success and result.retrieval_status == 'degraded'
    assert result.data == result.citations == []
    assert result.reranked is True  # Model ordering did complete before validation failed.


def test_partial_revalidation_retains_only_current_evidence():
    kb, manager, _ = setup()
    original_create = manager._client.messages.create
    async def create(**kwargs):
        kb.add_documents([{**POLICY, 'document_id': 'policy-1', 'content': 'new content'}])
        return await original_create(**kwargs)
    manager._client.messages.create = create
    result = run(manager)
    # Ranking's chosen Top-1 is gone; do not reintroduce omitted candidates automatically.
    assert result.retrieval_status == 'no_answer' and result.data == result.citations == []


@pytest.mark.parametrize('mode', ['empty', 'low', 'legacy', 'broken'])
def test_no_usable_recall_has_no_hits_or_citations(mode):
    kb, manager, messages = setup(count=0 if mode == 'empty' else 2)
    if mode == 'low':
        kb._collection.distance = .9
    if mode == 'legacy':
        kb._collection.rows = {'legacy': ('unknown', {'title': 'legacy'})}
    if mode == 'broken':
        def broken(**kwargs):
            raise RuntimeError('synthetic Chroma failure')
        kb._collection.query = broken
    result = run(manager)
    assert result.data == result.citations == [] and not result.reranked
    assert messages.calls == 0
    assert result.retrieval_status == {'empty': 'no_answer', 'low': 'low_confidence',
                                      'legacy': 'degraded', 'broken': 'degraded'}[mode]
    assert result.success is (mode in {'empty', 'low'})


def test_dependency_fallback_is_not_promoted_even_with_valid_citation():
    from mcp.tool_manager import ToolResult
    kb, manager, _ = setup()
    hits = kb.search('policy', 2)
    async def fallback_call(*args, **kwargs):
        return ToolResult(True, hits, 'knowledge_search', error_code='dependency_failure')
    manager.call = fallback_call
    result = run(manager)
    assert not result.success and result.retrieval_status == 'degraded'
    assert result.data == result.citations == []


@pytest.mark.parametrize('mode', ['foreign', 'bad_hash', 'missing_citation', 'blank_content'])
def test_final_evidence_is_checked_against_original_candidates(mode):
    from mcp.tool_manager import RerankResult
    _, manager, _ = setup()
    async def tampered(query, items, top_k):
        import copy
        hit = copy.deepcopy(items[0])
        if mode == 'foreign':
            hit['title'] = 'unknown injected source'
        elif mode == 'bad_hash':
            hit['content'] = 'invented content'
        elif mode == 'missing_citation':
            hit['citation'] = None
        else:
            hit['content'] = ''
        return RerankResult([hit], False, 'invalid_output_fallback')
    manager._rerank = tampered
    result = run(manager)
    assert result.retrieval_status == 'degraded' and not result.success
    assert result.data == result.citations == []


def test_direct_optional_rerank_does_not_claim_success_on_invalid_output():
    _, manager, _ = setup('[]')
    manager._tools['knowledge_search'].supports_rerank = True
    result = asyncio.run(manager.call('knowledge_search', {'query': 'policy', 'top_k': 2}, rerank_top_k=1))
    assert result.retrieval_status == 'usable' and result.reranked is False
    assert result.rerank_status == 'invalid_output_fallback'
    assert len(result.data) == len(result.citations) == 1


@pytest.mark.parametrize('output,count,expected_status', [('[]', 2, 'invalid_output_fallback'),
    ('[1,0]', 2, 'ranked'), ('[0]', 1, 'not_needed'), ('[]', 0, 'no_candidates')])
def test_agent_tool_payload_and_trace_preserve_actual_rerank(output, count, expected_status):
    import json
    from agents.agent_orchestrator import GeneralAgent, Request
    from agents.tools import build_shared_rag_tools
    _, manager, _ = setup(output, count=count)
    class Messages:
        calls = []
        async def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return SimpleNamespace(content=[{'type': 'tool_use', 'id': 'rag-n07',
                    'name': 'search_knowledge_base', 'input': {'query': 'policy', 'top_k': 1}}])
            return SimpleNamespace(content=[{'type': 'text', 'text': '请按检索状态核验知识。'}])
    messages = Messages()
    agent = GeneralAgent(SimpleNamespace(messages=messages), 'fake')
    agent.set_shared_tools(build_shared_rag_tools(manager))
    response = asyncio.run(agent.handle(Request(message='policy', user_id='u', conv_id='c')))
    trace = response.tool_traces[0]
    payload = json.loads(messages.calls[1]['messages'][-1]['content'][0]['content'])
    assert trace['rerank_status'] == payload['rerank_status'] == expected_status
    assert trace['reranked'] == payload['reranked'] == (expected_status == 'ranked')
    assert trace['result_success'] is True
    assert trace['retrieval_status'] == ('usable' if count else 'no_answer')
    if not count:
        assert trace['retrieval_hits'] == trace['citations'] == []
        assert payload['results'] == payload['citations'] == []
        assert '不要' in payload['answer_guidance']


def test_partial_version_revalidation_keeps_valid_member_when_top_k_allows():
    kb, manager, _ = setup('[2,1,0]', count=3)
    original = manager._client.messages.create
    async def create(**kwargs):
        kb.add_documents([{**POLICY, 'document_id': 'policy-2', 'content': 'replacement'}])
        return await original(**kwargs)
    manager._client.messages.create = create
    result = run(manager, top_k=2)
    assert result.retrieval_status == 'usable' and result.reranked
    assert [h['document_id'] for h in result.data] == ['policy-1']
    assert result.citations == [result.data[0]['citation']]


def test_cached_generic_optional_rerank_retains_fallback_status():
    from mcp.tool_manager import Tool
    manager = MCPToolManager(api_key='fake')
    async def handler(params, context):
        return [{'text': 'first'}, {'text': 'second'}]
    manager.register(Tool('generic_search', 'search', handler,
        {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
        cache_ttl=600, supports_rerank=True))
    messages = FakeMessages('[]')
    manager._client = SimpleNamespace(messages=messages)
    first = asyncio.run(manager.call('generic_search', {'query': 'q'}, rerank_top_k=1))
    second = asyncio.run(manager.call('generic_search', {'query': 'q'}, rerank_top_k=1))
    assert messages.calls == 1 and second.cached
    assert first.rerank_status == second.rerank_status == 'invalid_output_fallback'
    assert first.reranked is second.reranked is False


@pytest.mark.parametrize('output,count', [('[]', 2), ('[]', 0)])
def test_search_api_projects_contract_without_conflating_no_answer(monkeypatch, output, count):
    from api import main as api
    _, manager, _ = setup(output, count=count)
    monkeypatch.setattr(api, '_tool_manager', manager)
    result = asyncio.run(api.search(query='policy', top_k=1))
    assert result['success'] is True and result['reranked'] is False
    assert result['rerank_status'] == ('invalid_output_fallback' if count else 'no_candidates')
    assert result['retrieval_status'] == ('usable' if count else 'no_answer')
    assert len(result['results']) == len(result['citations']) == (1 if count else 0)
