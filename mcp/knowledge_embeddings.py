"""Versioned, dependency-free lexical vectors for the small demo knowledge base.

This is a transparent character n-gram baseline, not a pretrained semantic model.
Documents and queries use the same feature space. A title boost is applied only
when preparing document text so short FAQ questions can match document titles.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter


EMBEDDING_VERSION = "char-bigram-1024-v1"
DIMENSIONS = 1024


def _features(text: str) -> Counter[str]:
    normalized = "".join(character for character in text.lower() if character.isalnum())
    if not normalized:
        raise ValueError("embedding text must contain letters or digits")
    return Counter(normalized[index:index + 2] for index in range(len(normalized) - 1)) or Counter({normalized: 1})


def _vector(features: Counter[str]) -> list[float]:
    values = [0.0] * DIMENSIONS
    for feature, count in features.items():
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        values[index] += float(count) * (1.0 if digest[4] & 1 else -1.0)
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def embed_query(query: str) -> list[float]:
    return _vector(_features(query))


def embed_document(title: str, content: str) -> list[float]:
    features = _features(content)
    for feature, count in _features(title).items():
        features[feature] += 6 * count
    return _vector(features)
