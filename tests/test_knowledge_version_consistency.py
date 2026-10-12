import pytest
from datetime import datetime, timezone
from tests.test_rag_contract import knowledge_base, POLICY, manager_for
import asyncio


def test_audit_same_version_replacement():
    kb = knowledge_base()
    kb.add_documents([{**POLICY, 'content': 'Refund window is 7 days.'}])
    kb.add_documents([{**POLICY, 'content': 'Refund window is 30 days.'}])
    hits = kb.search('refund', 10)
    assert [h['content'] for h in hits] == ['Refund window is 30 days.']
    assert kb.doc_count == 1
    kb.add_documents([{**POLICY, 'content': 'Refund window is 30 days.'}])
    assert kb.doc_count == 1


def test_explicit_successor_and_unrelated_document():
    kb = knowledge_base()
    kb.add_documents([POLICY, {**POLICY, 'document_id': 'other'}])
    kb.add_documents([{**POLICY, 'policy_version': 'v2', 'supersedes': ['refund-cancel-v1'], 'content': '30 days'}])
    hits = kb.search('refund', 10)
    assert {(h['document_id'], h['policy_version']) for h in hits} == {('other', 'refund-cancel-v1'), (POLICY['document_id'], 'v2')}


@pytest.mark.parametrize('field,value', [('expires_at', '2020-01-01T00:00:00Z'), ('publication_status', 'revoked')])
def test_retired_not_usable(field, value):
    kb = knowledge_base()
    doc = {**POLICY, field: value}
    if field == 'expires_at':
        doc['effective_at'] = '2019-01-01T00:00:00Z'
    kb.add_documents([doc])
    assert kb.search('refund') == []


def test_cached_knowledge_cannot_survive_replacement():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    manager = manager_for(kb)
    manager._tools['knowledge_search'].cache_ttl = 600
    asyncio.run(manager.search_with_rewrite('knowledge_search', 'refund'))
    kb.add_documents([{**POLICY, 'content': '30 days'}])
    result = asyncio.run(manager.search_with_rewrite('knowledge_search', 'refund'))
    assert [h['content'] for h in result.data] == ['30 days']

from tests.test_rag_contract import FakeCollection
from mcp.knowledge_base import KnowledgeBase
from mcp.rag_contract import KnowledgeDocument, build_hit, RetrievalHit
from api import main as api
from fastapi import HTTPException
from pydantic import ValidationError
import hashlib


class FailingCollection(FakeCollection):
    fail = None

    def upsert(self, **kwargs):
        is_manifest = kwargs['metadatas'][0].get('record_type') == 'publication'
        import json
        ready = is_manifest and json.loads(kwargs['documents'][0])['state'] == 'ready'
        if self.fail == 'manifest' and is_manifest:
            raise RuntimeError('synthetic manifest failure')
        if self.fail == 'commit' and ready:
            raise RuntimeError('synthetic commit failure')
        if self.fail in {'partial', 'silent_partial'} and not is_manifest:
            super().upsert(**{k: v[:1] for k, v in kwargs.items()})
            if self.fail == 'partial':
                raise RuntimeError('synthetic partial write')
            return
        if self.fail == 'write' and not is_manifest:
            raise RuntimeError('synthetic write failure')
        super().upsert(**kwargs)

    def delete(self, **kwargs):
        if self.fail == 'delete':
            raise RuntimeError('synthetic delete failure')
        if self.fail == 'silent_delete':
            return
        super().delete(**kwargs)


def failing_kb():
    kb = knowledge_base()
    kb._collection = FailingCollection()
    return kb


@pytest.mark.parametrize('mode', ['write', 'partial', 'silent_partial', 'delete', 'silent_delete', 'commit'])
def test_failure_blocks_old_and_partial_chunks_until_retry(mode):
    kb = failing_kb()
    kb.add_documents([POLICY, {**POLICY, 'document_id': 'unrelated'}])
    kb._collection.fail = mode
    replacement = {**POLICY, 'content': 'new policy。' * 100}
    with pytest.raises(RuntimeError):
        kb.add_documents([replacement])
    # Durable state is observed by a new KB instance, not just an in-memory flag.
    restarted = knowledge_base()
    restarted._collection = kb._collection
    assert {h['document_id'] for h in restarted.search('refund', 10)} == {'unrelated'}
    kb._collection.fail = None
    kb.add_documents([replacement])
    hits = restarted.search('refund', 10)
    actual = [h for h in hits if h['document_id'] == POLICY['document_id']]
    assert len(actual) == len(kb._chunk_text(replacement['content']))
    assert all('new policy' in h['content'] for h in actual)


def test_first_manifest_failure_does_not_mutate_existing_content():
    kb = failing_kb()
    kb.add_documents([POLICY])
    original = kb._snapshot()
    kb._collection.fail = 'manifest'
    with pytest.raises(RuntimeError):
        kb.add_documents([{**POLICY, 'content': '30 days'}])
    assert kb._snapshot() == original
    assert kb.search('refund')[0]['content'] == POLICY['content']


def test_future_successor_before_at_and_after_activation(monkeypatch):
    import mcp.knowledge_base as module
    kb = knowledge_base()
    kb.add_documents([POLICY])
    activation = datetime(2030, 1, 1, tzinfo=timezone.utc)
    successor = {**POLICY, 'policy_version': 'v2', 'effective_at': activation.isoformat(),
                 'expires_at': '2031-01-01T00:00:00Z', 'supersedes': [POLICY['policy_version']], 'content': '30 days'}
    kb.add_documents([successor])
    class Clock(datetime):
        value = datetime(2029, 1, 1, tzinfo=timezone.utc)
        @classmethod
        def now(cls, tz=None):
            return cls.value
    monkeypatch.setattr(module, 'datetime', Clock)
    assert [h['policy_version'] for h in kb.search('refund', 1)] == [POLICY['policy_version']]
    Clock.value = activation
    active = kb.search('refund', 1)
    assert [h['policy_version'] for h in active] == ['v2']
    assert active[0]['retrieval_status'] == 'usable'
    Clock.value = datetime(2032, 1, 1, tzinfo=timezone.utc)
    assert kb.search('refund') == []  # No resurrection of superseded v1.


def test_failed_successor_does_not_fallback_to_retired_predecessor():
    kb = failing_kb()
    kb.add_documents([POLICY])
    kb._collection.fail = 'write'
    with pytest.raises(RuntimeError):
        kb.add_documents([{**POLICY, 'policy_version': 'v2', 'supersedes': [POLICY['policy_version']]}])
    assert kb.search('refund') == []


def test_supersession_is_explicit_not_lexicographic():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    kb.add_documents([{**POLICY, 'policy_version': 'aaa', 'content': 'different applicable interval'}])
    assert len(kb.search('refund', 10)) == 2
    kb.add_documents([{**POLICY, 'policy_version': 'z', 'supersedes': [POLICY['policy_version']]}])
    assert {h['policy_version'] for h in kb.search('refund', 10)} == {'aaa', 'z'}


@pytest.mark.parametrize('change', [
    {'policy_version': ''}, {'policy_version': None}, {'effective_at': None},
    {'expires_at': '2020-01-01'}, {'expires_at': POLICY['effective_at']},
    {'publication_status': 'unknown'}, {'supersedes': ['']},
    {'supersedes': [POLICY['policy_version']]}, {'supersedes': ['absent']},
])
def test_invalid_version_metadata_does_not_change_storage(change):
    kb = knowledge_base()
    with pytest.raises(ValueError):
        kb.add_documents([{**POLICY, **change}])
    assert kb._snapshot() == {}


def test_legacy_rows_and_stale_chunks_do_not_occupy_top_k():
    kb = knowledge_base()
    meta = {'document_id': POLICY['document_id'], 'title': POLICY['title'], 'source': POLICY['source'],
            'doc_type': 'policy', 'chunk_index': 0, 'total_chunks': 1,
            'policy_version': POLICY['policy_version'], 'effective_at': POLICY['effective_at']}
    kb._collection.rows['legacy'] = ('7 days', meta)
    kb.add_documents([{**POLICY, 'document_id': 'current', 'content': '30 days'}])
    assert kb.search('refund', 1)[0]['content'] == '30 days'
    assert 'legacy' in kb._collection.rows  # No bulk historical deletion.
    kb.add_documents([{**POLICY, 'content': '90 days'}])
    assert 'legacy' not in kb._collection.rows  # Exact identity replacement only.


def test_same_version_hash_changes_and_citation_tracks_content():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    before = kb.search('refund')[0]
    kb.add_documents([{**POLICY, 'content': '30 days'}])
    after = kb.search('refund')[0]
    assert before['citation']['reference'] != after['citation']['reference']
    assert after['citation']['content_hash'] == hashlib.sha256(b'30 days').hexdigest()
    after['content'] = '7 days'
    with pytest.raises(ValidationError):
        RetrievalHit.model_validate(after)


@pytest.mark.parametrize('status', ['revoked', 'expired'])
def test_build_hit_rejects_retired_metadata(status):
    kb = knowledge_base()
    kb.add_documents([POLICY])
    content, meta = next(row for row in kb._snapshot().values() if row[1].get('record_type') == 'chunk')
    meta = meta.copy()
    if status == 'revoked':
        meta['publication_status'] = status
    else:
        meta['effective_at'] = '2019-01-01T00:00:00Z'
        meta['expires_at'] = '2020-01-01T00:00:00Z'
    hit = build_hit(content, meta, 0, min_score=.35)
    assert hit.retrieval_status.value == 'low_confidence' and hit.citation is None
    assert hit.reason_code == status


@pytest.mark.parametrize('endpoint', ['add', 'upload'])
def test_api_failure_is_not_success_and_exposes_fixed_error(monkeypatch, endpoint):
    kb = failing_kb()
    kb.add_documents([POLICY])
    manager = manager_for(kb)
    monkeypatch.setattr(api, '_tool_manager', manager)
    kb._collection.fail = 'write'
    doc = {**POLICY, 'content': '30 days'}
    class Upload:
        filename = 'policy.json'
        async def read(self):
            import json
            return json.dumps([doc]).encode()
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.add_knowledge(api.BatchDocInput(documents=[api.DocInput(**doc)])) if endpoint == 'add'
                    else api.upload_knowledge(Upload()))
    assert error.value.status_code == 503
    assert error.value.detail == {'error': 'knowledge_publication_failed', 'retry_required': True}
    assert kb.search('refund') == []


def test_generated_document_id_survives_content_edit():
    base = {'title': 'FAQ', 'source': 'demo:faq', 'content': '7 days'}
    assert KnowledgeDocument(**base).document_id == KnowledgeDocument(**{**base, 'content': '30 days'}).document_id


def test_publication_during_rerank_cannot_return_stale_evidence():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    manager = manager_for(kb)
    async def rerank(query, items, top_k):
        kb.add_documents([{**POLICY, 'content': '30 days'}])
        return items[:top_k]
    manager._rerank = rerank
    result = asyncio.run(manager.search_with_rewrite('knowledge_search', 'refund'))
    assert result.success is False and result.retrieval_status == 'no_answer'
    assert result.data == result.citations == []


def test_revocation_does_not_resurrect_predecessor_or_allow_unrevoking():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    v2 = {**POLICY, 'policy_version': 'v2', 'supersedes': [POLICY['policy_version']]}
    kb.add_documents([v2])
    kb.add_documents([{**v2, 'publication_status': 'revoked'}])
    assert kb.search('refund') == []
    with pytest.raises(ValueError):
        kb.add_documents([v2])
    with pytest.raises(ValueError):
        kb.add_documents([{**v2, 'supersedes': [], 'publication_status': 'revoked'}])


def test_shorter_same_version_update_removes_all_previous_chunks():
    kb = knowledge_base()
    kb.add_documents([{**POLICY, 'content': 'old。' * 600}])
    assert kb.doc_count > 1
    kb.add_documents([{**POLICY, 'content': '30 days'}])
    assert kb.doc_count == 1
    assert len(kb.search('refund', 1)) == 1


def test_partial_batch_reports_failure_without_undoing_completed_member():
    kb = failing_kb()
    original_upsert = kb._collection.upsert
    def upsert(**kwargs):
        if kwargs['metadatas'][0].get('document_id') == 'second':
            raise RuntimeError('second batch member failed')
        return original_upsert(**kwargs)
    kb._collection.upsert = upsert
    with pytest.raises(RuntimeError):
        kb.add_documents([POLICY, {**POLICY, 'document_id': 'second'}])
    assert {h['document_id'] for h in kb.search('refund', 10)} == {POLICY['document_id']}


def test_incomplete_committed_document_is_filtered_before_top_k():
    kb = knowledge_base()
    kb.add_documents([{**POLICY, 'content': 'old。' * 600}, {**POLICY, 'document_id': 'valid'}])
    missing = next(i for i, (_, m) in kb._snapshot().items()
                   if m.get('document_id') == POLICY['document_id'] and m.get('chunk_index') == 1)
    kb._collection.rows.pop(missing)
    assert kb.search('refund', 1)[0]['document_id'] == 'valid'


def test_silent_manifest_failure_is_detected_before_chunk_mutation():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    before = kb._snapshot()
    upsert = kb._collection.upsert
    def silent(**kwargs):
        if kwargs['metadatas'][0].get('record_type') != 'publication':
            upsert(**kwargs)
    kb._collection.upsert = silent
    with pytest.raises(RuntimeError, match='begin unconfirmed'):
        kb.add_documents([{**POLICY, 'content': '30 days'}])
    assert kb._snapshot() == before


def test_document_identity_collision_cannot_delete_another_source():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    before = kb._snapshot()
    with pytest.raises(ValueError):
        kb.add_documents([{**POLICY, 'source': 'other:tenant', 'content': '30 days'}])
    assert kb._snapshot() == before


def test_legacy_only_collection_requires_reviewed_republication():
    kb = knowledge_base()
    kb._collection.rows['legacy'] = ('7 days', {'title': 'unknown'})
    result = asyncio.run(manager_for(kb).search_with_rewrite('knowledge_search', 'refund'))
    assert result.success is False and result.retrieval_status == 'degraded'
    assert result.citations == []
