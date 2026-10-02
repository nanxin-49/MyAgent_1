"""T07 RAG contract tests. No Chroma server or model API is required."""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from agents.agent_orchestrator import GeneralAgent, Request
from agents.tools import build_shared_rag_tools
from api.main import collect_rag_evidence, render_rag_citations
from api import main as api_main
from mcp.knowledge_base import KnowledgeBase
from mcp.rag_contract import KnowledgeDocument, RetrievalHit, RetrievalStatus, build_hit
from mcp.tool_manager import MCPToolManager, Tool


class FakeCollection:
    def __init__(self):
        self.rows = {}
        self.distance = 0.1
        self.metadata = {"dataset_kind": "demo"}

    def upsert(self, *, ids, documents, metadatas, embeddings):
        assert len(ids) == len(embeddings)
        assert all(len(vector) == 1024 for vector in embeddings)
        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            self.rows[chunk_id] = (document, metadata)

    def count(self):
        return len(self.rows)

    def get(self, *, include):
        return {"metadatas": [metadata for _, metadata in self.rows.values()]}

    def query(self, *, query_embeddings, n_results, include):
        assert len(query_embeddings) == 1 and len(query_embeddings[0]) == 1024
        rows = list(self.rows.values())[:n_results]
        return {"documents": [[row[0] for row in rows]],
                "metadatas": [[row[1] for row in rows]],
                "distances": [[self.distance for _ in rows]]}


def knowledge_base():
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb._collection = FakeCollection()
    kb.min_score = 0.35
    return kb


POLICY = {
    "document_id": "refund-policy-2026",
    "title": "模拟退款政策",
    "content": "示例政策说明。订单七天内可请求退款。",
    "source": "demo:policy/refund",
    "doc_type": "policy",
    "policy_version": "refund-cancel-v1",
    "effective_at": "2026-09-01T00:00:00+00:00",
}


def test_metadata_ingestion_round_trip_and_policy_citation():
    kb = knowledge_base()
    assert kb.add_documents([POLICY]) == 1
    stored = next(iter(kb._collection.rows.values()))[1]
    assert stored["document_id"] == "refund-policy-2026"
    assert stored["source"] == "demo:policy/refund"
    assert stored["doc_type"] == "policy"
    assert stored["chunk_index"] == 0
    assert stored["total_chunks"] == 1
    assert stored["policy_version"] == "refund-cancel-v1"
    assert stored["effective_at"].startswith("2026-09-01")

    hit = kb.search("退款", 3)[0]
    assert hit["retrieval_status"] == "usable"
    assert hit["score_kind"] == "one_minus_chroma_distance"
    assert hit["citation"] == {
        "reference": "refund-policy-2026@refund-cancel-v1#chunk-0", "document_id": "refund-policy-2026",
        "chunk_index": 0, "source": "demo:policy/refund", "policy_version": "refund-cancel-v1",
    }
    assert hit["policy_version"] == "refund-cancel-v1"
    assert hit["effective_at"].startswith("2026-09-01")


def test_default_demo_documents_import_with_explicit_provenance():
    kb = knowledge_base()
    kb._load_default_docs()
    assert len(kb._collection.rows) >= 6
    policy_rows = [meta for _, meta in kb._collection.rows.values() if meta["doc_type"] == "policy"]
    assert policy_rows
    assert all(meta["source"].startswith("demo:") for meta in policy_rows)
    assert all(meta["policy_version"] == "refund-cancel-v1" for meta in policy_rows)


@pytest.mark.parametrize("change", [
    {"source": ""}, {"doc_type": "policy", "policy_version": None},
    {"doc_type": "policy", "effective_at": None},
    {"doc_type": "policy", "effective_at": "2026-09-01T00:00:00"},
    {"doc_type": "unknown"}, {"content": "  "},
])
def test_malformed_document_metadata_is_rejected_before_write(change):
    kb = knowledge_base()
    with pytest.raises(ValidationError):
        kb.add_documents([{**POLICY, **change}])
    assert kb._collection.rows == {}


def test_non_policy_document_has_stable_generated_id_without_policy_fields():
    doc = KnowledgeDocument.model_validate({"title": "FAQ", "content": "如何查订单", "source": "demo:faq", "doc_type": "faq"})
    same = KnowledgeDocument.model_validate({"title": "FAQ", "content": "如何查订单", "source": "demo:faq", "doc_type": "faq"})
    assert doc.document_id == same.document_id
    kb = knowledge_base()
    kb.add_documents([doc.model_dump(mode="json", exclude_none=True)])
    stored = next(iter(kb._collection.rows.values()))[1]
    assert "policy_version" not in stored
    assert "effective_at" not in stored


def test_low_score_and_future_policy_are_not_citable():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    kb._collection.distance = 0.9
    low = kb.search("退款")[0]
    assert low["retrieval_status"] == "low_confidence"
    assert low["reason_code"] == "low_score"
    assert low["citation"] is None

    future_meta = next(iter(kb._collection.rows.values()))[1].copy()
    future_meta["effective_at"] = "2099-01-01T00:00:00+00:00"
    future = build_hit("future policy", future_meta, 0.1, min_score=0.35,
                       now=datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert future.retrieval_status is RetrievalStatus.LOW_CONFIDENCE
    assert future.reason_code == "not_yet_effective"
    assert future.citation is None


def test_legacy_metadata_cannot_gain_a_fabricated_citation():
    hit = build_hit("old chunk", {"title": "旧文档", "chunk_index": "bad"}, 0.01,
                    min_score=0.35)
    assert hit.retrieval_status is RetrievalStatus.LOW_CONFIDENCE
    assert hit.reason_code == "missing_metadata"
    assert hit.citation is None
    assert hit.source == "unknown"


def test_citation_must_match_hit_provenance():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    hit = kb.search("退款")[0]
    hit["citation"]["source"] = "wrong-source"
    with pytest.raises(ValidationError):
        RetrievalHit.model_validate(hit)


def manager_for(kb, *, fallback=None):
    manager = MCPToolManager(api_key="test")

    async def rewrite(query, n=3):
        return [query, f"{query} 解释"]

    async def rerank(query, items, top_k):
        return items[:top_k]

    manager.rewrite_query = rewrite
    manager._rerank = rerank
    manager.register(Tool("knowledge_search", "search", kb.search_handler,
                          {"type": "object", "properties": {"query": {"type": "string", "minLength": 1},
                                                            "top_k": {"type": "integer"}},
                           "required": ["query"], "additionalProperties": False},
                          fallback=fallback))
    return manager


def test_rewrite_deduplicates_citations_and_returns_usable_result():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    result = asyncio.run(manager_for(kb).search_with_rewrite("knowledge_search", "退款"))
    assert result.success is True
    assert result.retrieval_status == "usable"
    assert result.reranked is True
    assert len(result.data) == len(result.citations) == 1
    assert result.citations[0]["policy_version"] == "refund-cancel-v1"


def test_low_confidence_no_answer_and_degraded_are_distinct():
    kb = knowledge_base()
    manager = manager_for(kb)
    empty = asyncio.run(manager.search_with_rewrite("knowledge_search", "未知问题"))
    assert empty.success is False and empty.retrieval_status == "no_answer"
    assert empty.citations == []

    kb.add_documents([POLICY])
    kb._collection.distance = 0.9
    low = asyncio.run(manager.search_with_rewrite("knowledge_search", "低可信问题"))
    assert low.success is False and low.retrieval_status == "low_confidence"
    assert low.citations == []

    class BrokenKB:
        async def search_handler(self, params, context):
            raise RuntimeError("Chroma unavailable")

    degraded_manager = manager_for(BrokenKB(), fallback=lambda params, context, error: [
        {"title": "降级结果", "content": "请稍后重试", "fallback": True}])
    degraded = asyncio.run(degraded_manager.search_with_rewrite("knowledge_search", "故障"))
    assert degraded.success is False and degraded.retrieval_status == "degraded"
    assert degraded.data == [] and degraded.citations == []


def test_agent_rag_tool_round_trip_exposes_only_usable_citations():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    manager = manager_for(kb)

    class Client:
        def __init__(self):
            self.calls = []

        class Messages:
            def __init__(self, owner):
                self.owner = owner

            async def create(self, **kwargs):
                self.owner.calls.append(kwargs)
                if len(self.owner.calls) == 1:
                    return type("Response", (), {"content": [{"type": "tool_use", "id": "rag-1",
                                                              "name": "search_knowledge_base", "input": {"query": "退款"}}]})()
                return type("Response", (), {"content": [{"type": "text", "text": "请查看模拟退款政策。"}]})()

        @property
        def messages(self):
            return self.Messages(self)

    client = Client()
    agent = GeneralAgent(client, "test-model")
    agent.set_shared_tools(build_shared_rag_tools(manager))
    response = asyncio.run(agent.handle(Request(message="退款", user_id="demo-user", conv_id="demo-conv")))
    assert response.success is True
    trace = response.tool_traces[0]
    assert trace["retrieval_status"] == "usable"
    assert trace["citations"][0]["reference"] == "refund-policy-2026@refund-cancel-v1#chunk-0"
    status, citations = collect_rag_evidence(response.tool_traces)
    assert status == "usable" and len(citations) == 1
    payload = json.loads(client.calls[1]["messages"][-1]["content"][0]["content"])
    assert payload["retrieval_status"] == "usable"
    assert payload["results"][0]["citation"]["source"] == "demo:policy/refund"


def test_agent_low_confidence_cannot_claim_knowledge_used():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    kb._collection.distance = 0.9
    tool = build_shared_rag_tools(manager_for(kb))["search_knowledge_base"]
    payload = asyncio.run(tool.handler(Request(message="退款", user_id="u", conv_id="c"), {"query": "退款"}))
    assert payload["success"] is False
    assert payload["retrieval_status"] == "low_confidence"
    assert payload["results"] == [] and payload["citations"] == []
    assert "不要" in payload["answer_guidance"]


def test_chat_citation_footer_only_uses_validated_usable_references():
    citation = {"reference": "policy-v1@refund-v1#chunk-0", "source": "demo:policy"}
    assert render_rag_citations("7 天退款窗口", [citation]).endswith(citation["reference"])
    assert render_rag_citations("知识库暂不可用", []) == "知识库暂不可用"
    assert render_rag_citations("参见 policy-v1@refund-v1#chunk-0", [citation]).count(
        citation["reference"]) == 1


def test_demo_reset_refuses_unknown_legacy_provenance(monkeypatch):
    kb = knowledge_base()
    kb._collection_name = KnowledgeBase.COLLECTION_NAME
    kb._collection.rows["legacy"] = ("old", {"title": "旧文档"})

    class Client:
        deleted = False

        def delete_collection(self, name):
            self.deleted = True

    kb._client = Client()
    with pytest.raises(ValueError, match="provenance"):
        kb.rebuild_demo_collection()
    assert kb._client.deleted is False


def test_api_ingestion_preserves_policy_metadata_and_invalidates_cache(monkeypatch):
    kb = knowledge_base()
    manager = manager_for(kb)
    manager._cache["stale"] = ([], 999999.0, False)
    monkeypatch.setattr(api_main, "_tool_manager", manager)
    body = api_main.BatchDocInput(documents=[api_main.DocInput(**POLICY)])
    response = asyncio.run(api_main.add_knowledge(body))
    assert response["added_chunks"] == 1
    assert manager._cache == {}
    assert next(iter(kb._collection.rows.values()))[1]["policy_version"] == "refund-cancel-v1"

    invalid = api_main.BatchDocInput(documents=[api_main.DocInput(
        title="bad policy", content="body", doc_type="policy")])
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_main.add_knowledge(invalid))
    assert error.value.status_code == 422


def test_json_upload_assigns_explicit_upload_source(monkeypatch):
    kb = knowledge_base()
    manager = manager_for(kb)
    monkeypatch.setattr(api_main, "_tool_manager", manager)

    class Upload:
        filename = "faq.json"

        async def read(self):
            return b'[{"title":"FAQ","content":"How to order?","doc_type":"faq"}]'

    response = asyncio.run(api_main.upload_knowledge(Upload()))
    assert response["added_chunks"] == 1
    assert next(iter(kb._collection.rows.values()))[1]["source"] == "upload:faq.json"
