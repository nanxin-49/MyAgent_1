"""Deterministic BM25 + reciprocal-rank fusion for the H2-5 hybrid group."""
from __future__ import annotations

import math
from collections import Counter

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Character bigrams over lowercase alphanumerics, matching B0's feature space."""
    normalized = "".join(character for character in (text or "").lower()
                         if character.isalnum())
    if not normalized:
        return []
    if len(normalized) == 1:
        return [normalized]
    return [normalized[index:index + 2] for index in range(len(normalized) - 1)]


class BM25:
    def __init__(self, documents: dict[str, str], *, k1: float = DEFAULT_K1,
                 b: float = DEFAULT_B):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        self.k1, self.b = k1, b
        self._tokens = {key: tokenize(value) for key, value in documents.items()}
        self._lengths = {key: len(tokens) for key, tokens in self._tokens.items()}
        self._avgdl = (sum(self._lengths.values()) / len(self._lengths)
                       if self._lengths else 0.0)
        document_frequency: Counter[str] = Counter()
        for tokens in self._tokens.values():
            document_frequency.update(set(tokens))
        total = len(self._tokens)
        self._idf = {term: math.log(1 + (total - count + 0.5) / (count + 0.5))
                     for term, count in document_frequency.items()}

    def scores(self, query: str) -> dict[str, float]:
        terms = tokenize(query)
        if not terms or not self._tokens or self._avgdl <= 0:
            return {key: 0.0 for key in self._tokens}
        output = {}
        for key, tokens in self._tokens.items():
            counts = Counter(tokens)
            length = self._lengths[key]
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                idf = self._idf.get(term, 0.0)
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / self._avgdl)
                score += idf * frequency * (self.k1 + 1) / denominator
            output[key] = score
        return output


def rrf_order(semantic_hits: list[dict], bm25_scores: dict[str, float],
              *, k: int = RRF_K) -> list[dict]:
    """Fuse semantic and BM25 rankings; return semantic hit dicts in RRF order.

    ``semantic_hits`` must carry ``frozen_chunk_id`` and be sorted by score
    descending (or will be sorted here). BM25 ties break by chunk id for
    determinism. Hits without a known chunk id are ignored.
    """
    if k < 1:
        raise ValueError("RRF k must be >= 1")
    semantic = sorted(semantic_hits, key=lambda item: (
        -float(item.get("score") or 0.0), str(item.get("frozen_chunk_id"))))
    semantic_rank = {item["frozen_chunk_id"]: rank for rank, item in enumerate(semantic, 1)
                     if item.get("frozen_chunk_id")}
    bm25_rank = {key: rank for rank, (key, score) in enumerate(
        sorted(bm25_scores.items(), key=lambda pair: (-pair[1], pair[0])), 1)
        if score > 0}
    fused = []
    for item in semantic:
        chunk_id = item.get("frozen_chunk_id")
        if not chunk_id:
            continue
        score = (1.0 / (k + semantic_rank[chunk_id])
                 + (1.0 / (k + bm25_rank[chunk_id]) if chunk_id in bm25_rank else 0.0))
        fused.append((score, item))
    fused.sort(key=lambda pair: (-pair[0], str(pair[1].get("frozen_chunk_id"))))
    return [item for _, item in fused]
