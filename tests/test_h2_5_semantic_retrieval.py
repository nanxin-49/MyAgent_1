"""H2-5: lookup adapter, BM25/RRF, calibration reuse, and report helpers."""
import hashlib
from pathlib import Path

import pytest

from evaluation.h2_5 import run_semantic_retrieval as runner
from evaluation.h2_5.embedding_adapter import (
    LookupEmbedding, patched_knowledge_module,
)
from evaluation.h2_5.hybrid import BM25, rrf_order, tokenize
from evaluation.rag_quality.dev_calibration import select_threshold

ROOT = Path(__file__).resolve().parents[1]


def _payload(**overrides):
    vector = [0.1] * 4
    payload = {
        "schema": "cartcare.h2_5.embedding_vectors", "version": 1,
        "embedding_version": "test-embedding-v1",
        "model": {"model_id": "test/model", "revision": "abc",
                  "weights_sha256": "deadbeef", "dimensions": 4},
        "chunks": {"c1": {"vector": vector, "title": "退款政策",
                          "content_sha256": hashlib.sha256(b"x").hexdigest()}},
        "publications": {"pub1": {"vector": vector, "title": "publication",
                                  "content_sha256": "p1"}},
        "queries": {"怎么退款": {"vector": vector, "latency_ms": 12.5,
                                  "split": "test", "case_id": "c1"}},
    }
    payload.update(overrides)
    return payload


def test_lookup_adapter_is_fail_closed_and_restores_module(monkeypatch):
    import mcp.knowledge_base as knowledge_base
    original = (knowledge_base.embed_document, knowledge_base.embed_query,
                knowledge_base.EMBEDDING_VERSION)
    embedder = LookupEmbedding(_payload())
    assert embedder.embed_query("怎么退款") == [0.1] * 4
    assert embedder.embed_document("退款政策", "x") == [0.1] * 4
    with pytest.raises(KeyError):
        embedder.embed_query("未知问题")
    with pytest.raises(KeyError):
        embedder.embed_document("退款政策", "different content")
    with patched_knowledge_module(embedder):
        assert knowledge_base.EMBEDDING_VERSION == "test-embedding-v1"
        assert knowledge_base.embed_query("怎么退款") == [0.1] * 4
    assert (knowledge_base.embed_document, knowledge_base.embed_query,
            knowledge_base.EMBEDDING_VERSION) == original


def test_lookup_adapter_rejects_bad_dimensions_and_non_finite_values():
    bad = _payload()
    bad["queries"]["怎么退款"]["vector"] = [0.1, 0.2]
    with pytest.raises(ValueError):
        LookupEmbedding(bad)
    nonfinite = _payload()
    nonfinite["queries"]["怎么退款"]["vector"] = [float("nan")] * 4
    with pytest.raises(ValueError):
        LookupEmbedding(nonfinite)


def test_bm25_ranks_matching_document_and_is_deterministic():
    documents = {
        "refund": "退款政策：订单创建后七天内可以申请退款。",
        "logistics": "物流配送说明：标准配送三到五个工作日。",
        "account": "账户安全：定期修改密码并绑定手机。",
    }
    bm25 = BM25(documents)
    first = bm25.scores("退款")
    second = bm25.scores("退款")
    assert first == second
    assert first["refund"] > first["logistics"]
    assert all(value == 0.0 for value in bm25.scores("").values())
    assert tokenize("退款政策") == ["退款", "款政", "政策"]


def test_rrf_orders_union_and_ignores_unknown_chunks():
    hits = [
        {"frozen_chunk_id": "a", "score": 0.9},
        {"frozen_chunk_id": "b", "score": 0.8},
        {"frozen_chunk_id": "c", "score": 0.7},
    ]
    bm25 = {"b": 10.0, "c": 5.0}
    ordered = rrf_order(hits, bm25)
    assert [item["frozen_chunk_id"] for item in ordered] == ["b", "c", "a"]
    unknown = rrf_order([{"frozen_chunk_id": None, "score": 1.0}], {"a": 1.0})
    assert unknown == []


def test_calibration_selection_respects_false_positive_constraint():
    def point(threshold, recall, fp, mrr):
        return {"threshold": threshold,
                "Recall@5": {"numerator": recall, "denominator": 8},
                "no_answer_false_positive_rate": {"numerator": fp, "denominator": 8},
                "MRR": {"numerator": mrr, "denominator": 8},
                "citation_evidence_precision": {"numerator": recall, "denominator": recall}}
    curve = [point(0.2, 5, 5, 4.0), point(0.5, 2, 1, 2.0), point(0.7, 1, 0, 1.0)]
    chosen = select_threshold(curve)
    assert chosen["threshold"] == 0.5
    assert select_threshold([point(0.2, 5, 8, 5.0)]) is None


def test_summary_with_embedding_adds_quantiles():
    summary = {"Recall@5": {"value": 1.0}}
    rows = [{"query_embedding_latency_ms": value} for value in (10, 20, 30)]
    output = runner._summary_with_embedding(summary, rows)
    assert output["query_embedding_latency_ms"]["p50"] == 20
    assert output["query_embedding_latency_ms"]["count"] == 3
    assert output["Recall@5"]["value"] == 1.0


def test_collection_metadata_binds_semantic_model_and_b0_version():
    model = {"embedding_version": "bge-test", "dimensions": 512,
             "model_id": "BAAI/test", "revision": "rev",
             "weights_sha256": "sha"}
    semantic = runner._collection_metadata("semantic", "run", model)
    assert semantic["embedding_version"] == "bge-test"
    assert semantic["weights_sha256"] == "sha"
    assert semantic["dimensions"] == 512
    b0 = runner._collection_metadata("b0", "run", None)
    assert b0["embedding_version"] == "char-bigram-1024-v1"
    assert b0["dimensions"] == 1024


def test_locked_b0_calibration_reference_is_020():
    reference = runner._b0_calibration_reference()
    assert reference["status"] == "locked"
    assert reference["selected_threshold"] == 0.2
    assert reference["test_scores_consumed"] is False
