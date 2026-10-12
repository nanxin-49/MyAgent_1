"""Opt-in real Chroma HTTP integration; set CARTCARE_RUN_CHROMA_HTTP_TEST=1."""

from __future__ import annotations

import os
import uuid

import pytest

from mcp.knowledge_base import KnowledgeBase


@pytest.mark.skipif(os.getenv("CARTCARE_RUN_CHROMA_HTTP_TEST") != "1",
                    reason="requires a real Chroma HTTP server")
def test_real_http_seed_query_metadata_and_citation():
    kb = KnowledgeBase(
        chroma_host=os.getenv("CHROMA_HOST", "127.0.0.1"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8001")),
        collection_name=f"cartcare_rag_it_{uuid.uuid4().hex[:12]}",
        seed_defaults=False,
    )
    try:
        assert kb.add_documents([{
            "document_id": "http-refund-policy-v1", "title": "退款政策",
            "source": "demo:integration/refund-policy", "doc_type": "policy",
            "policy_version": "integration-v1", "effective_at": "2026-09-01T00:00:00Z",
            "content": "演示退款政策：订单创建后 7 天内且状态符合要求时可以申请退款。",
        }]) == 1
        hit = kb.search("退款政策是什么？", top_k=1)[0]
        assert hit["retrieval_status"] == "usable"
        assert hit["document_id"] == "http-refund-policy-v1"
        assert hit["source"] == "demo:integration/refund-policy"
        assert hit["policy_version"] == "integration-v1"
        assert hit["effective_at"].startswith("2026-09-01")
        assert hit["citation"]["reference"].startswith("http-refund-policy-v1@integration-v1#chunk-0~")
        assert "7 天" in hit["content"]
    finally:
        kb._client.delete_collection(kb._collection_name)


@pytest.mark.skipif(os.getenv("CARTCARE_RUN_CHROMA_HTTP_TEST") != "1",
                    reason="requires a real Chroma HTTP server")
def test_real_http_version_replacement_and_activation(monkeypatch):
    from datetime import datetime, timezone
    import mcp.knowledge_base as module
    kb = KnowledgeBase(
        chroma_host=os.getenv('CHROMA_HOST', '127.0.0.1'),
        chroma_port=int(os.getenv('CHROMA_PORT', '8001')),
        collection_name=f'cartcare_n06_it_{uuid.uuid4().hex[:12]}', seed_defaults=False)
    doc = {'document_id': 'refund-policy', 'title': '退款政策', 'source': 'test:n06/policy',
           'doc_type': 'policy', 'policy_version': 'v1', 'effective_at': '2020-01-01T00:00:00Z',
           'content': '退款政策：7 天内退货。'}
    try:
        kb.add_documents([doc])
        before = kb.search('退款政策', 1)[0]
        replacement = {**doc, 'content': '退款政策：30 天内退货。'}
        kb.add_documents([replacement])
        kb.add_documents([replacement])
        assert kb.doc_count == 1
        after = kb.search('退款政策', 1)[0]
        assert after['retrieval_status'] == 'usable' and '30 天' in after['content']
        assert before['citation']['reference'] != after['citation']['reference']
        successor = {**doc, 'policy_version': 'v2', 'supersedes': ['v1'],
                     'effective_at': '2030-01-01T00:00:00Z', 'expires_at': '2031-01-01T00:00:00Z',
                     'content': '退款政策：90 天内退货。'}
        kb.add_documents([successor, {**doc, 'document_id': 'unrelated'}])
        assert {h['policy_version'] for h in kb.search('退款政策', 10)} == {'v1'}
        class Clock(datetime):
            value = datetime(2030, 1, 1, tzinfo=timezone.utc)
            @classmethod
            def now(cls, tz=None):
                return cls.value
        monkeypatch.setattr(module, 'datetime', Clock)
        hits = kb.search('退款政策', 10)
        assert {(h['document_id'], h['policy_version']) for h in hits} == {('refund-policy', 'v2'), ('unrelated', 'v1')}
        assert all(h['retrieval_status'] == 'usable' for h in hits)
        Clock.value = datetime(2032, 1, 1, tzinfo=timezone.utc)
        assert {h['document_id'] for h in kb.search('退款政策', 10)} == {'unrelated'}
    finally:
        kb._client.delete_collection(kb._collection_name)
