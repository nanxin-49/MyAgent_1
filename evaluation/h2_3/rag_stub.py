"""Deterministic RAG stub for the H2-3 offline suite.

It maps exact case questions to expected retrieval results. It is not a
retrieval-quality experiment and never connects to Chroma.
"""
from __future__ import annotations

from typing import Any

from agents.tools import make_tool


def _usable(query: str, spec: dict) -> dict:
    reference = spec.get("reference") or f"{spec['document_id']}#chunk-0"
    citation = {
        "reference": reference,
        "document_id": spec["document_id"],
        "title": spec.get("title", ""),
        "source": spec.get("source", "demo:cartcare-default"),
        "policy_version": spec.get("policy_version"),
        "content_hash": spec.get("content_hash", "h2-3-stub"),
    }
    hit = {
        "document_id": spec["document_id"],
        "title": spec.get("title", ""),
        "source": spec.get("source", "demo:cartcare-default"),
        "policy_version": spec.get("policy_version"),
        "chunk_index": 0,
        "score": 0.9,
        "content": spec.get("content", ""),
        "citation": citation,
    }
    return {"success": True, "query": query, "top_k": 5, "results": [hit],
            "citations": [citation], "retrieval_status": "usable",
            "answer_guidance": "deterministic H2-3 stub evidence"}


def _refusal(query: str, status: str) -> dict:
    return {"success": True, "query": query, "top_k": 5, "results": [],
            "citations": [], "retrieval_status": status,
            "answer_guidance": "deterministic H2-3 stub: no citable evidence"}


def make_rag_tool(mapping: dict[str, dict[str, Any]]):
    def search(req, args):
        query = str(args.get("query") or "").strip()
        spec = mapping.get(query)
        if spec is None:
            return _refusal(query, "low_confidence")
        if spec.get("status", "usable") == "usable":
            return _usable(query, spec)
        return _refusal(query, spec.get("status", "no_answer"))

    return make_tool(
        "search_knowledge_base",
        "H2-3 deterministic knowledge stub",
        {"query": {"type": "string", "minLength": 1}, "top_k": {"type": "integer"}},
        search,
        required=["query"],
    )
