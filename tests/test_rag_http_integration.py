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
        assert hit["citation"]["reference"] == "http-refund-policy-v1@integration-v1#chunk-0"
        assert "7 天" in hit["content"]
    finally:
        kb._client.delete_collection(kb._collection_name)
