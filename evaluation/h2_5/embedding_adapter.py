"""Lookup adapter for precomputed bge vectors; evaluation-only, no production edit."""
from __future__ import annotations

import hashlib
import math
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _doc_key(title: str, content_hash: str) -> str:
    return f"{title}\0{content_hash}"


class LookupEmbedding:
    """Fail-closed lookup of precomputed document/query vectors."""

    def __init__(self, payload: dict[str, Any]):
        model = payload.get("model") or {}
        if payload.get("schema") != "cartcare.h2_5.embedding_vectors":
            raise ValueError("unsupported embedding vector schema")
        self.embedding_version = payload["embedding_version"]
        self.model = dict(model)
        self.dimensions = int(model.get("dimensions") or 0)
        if self.dimensions < 1:
            raise ValueError("embedding dimensions missing")
        self._documents: dict[str, list[float]] = {}
        for source in ("chunks", "publications"):
            for item_id, item in (payload.get(source) or {}).items():
                vector = list(item["vector"])
                self._validate(vector, f"{source} {item_id}")
                self._documents[_doc_key(item["title"], item["content_sha256"])] = vector
        self._queries: dict[str, list[float]] = {}
        self._query_meta: dict[str, dict[str, Any]] = {}
        for query, item in (payload.get("queries") or {}).items():
            vector = list(item["vector"])
            self._validate(vector, f"query {query!r}")
            self._queries[query] = vector
            self._query_meta[query] = {k: item.get(k) for k in ("latency_ms", "split", "case_id")}
        if not self._documents or not self._queries:
            raise ValueError("embedding payload has no document or query vectors")

    def _validate(self, vector: list[float], label: str) -> None:
        if len(vector) != self.dimensions:
            raise ValueError(f"{label} dimension {len(vector)} != {self.dimensions}")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in vector):
            raise ValueError(f"{label} contains non-finite values")

    def embed_document(self, title: str, content: str) -> list[float]:
        key = _doc_key(title, _content_hash(content))
        vector = self._documents.get(key)
        if vector is None:
            raise KeyError("unknown document text; refusing to fabricate a vector")
        return list(vector)

    def embed_query(self, query: str) -> list[float]:
        vector = self._queries.get(query)
        if vector is None:
            raise KeyError(f"unknown query {query!r}; refusing to fabricate a vector")
        return list(vector)

    def query_latency_ms(self, query: str) -> float | None:
        return (self._query_meta.get(query) or {}).get("latency_ms")


@contextmanager
def patched_knowledge_module(embedder: LookupEmbedding):
    """Temporarily replace KnowledgeBase's embedding seam; restore on exit."""
    import mcp.knowledge_base as knowledge_base
    original = (knowledge_base.embed_document, knowledge_base.embed_query,
                knowledge_base.EMBEDDING_VERSION)
    knowledge_base.embed_document = embedder.embed_document
    knowledge_base.embed_query = embedder.embed_query
    knowledge_base.EMBEDDING_VERSION = embedder.embedding_version
    try:
        yield knowledge_base
    finally:
        (knowledge_base.embed_document, knowledge_base.embed_query,
         knowledge_base.EMBEDDING_VERSION) = original


def load_vectors(path: str | Path) -> tuple[LookupEmbedding, dict[str, Any]]:
    import json
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return LookupEmbedding(payload), payload
