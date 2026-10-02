"""Validated knowledge metadata, retrieval hits and citations for CartCare RAG.

These models describe explanatory knowledge only. They never determine refund
or cancellation eligibility; that remains the PolicyEngine's responsibility.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DocumentType(str, Enum):
    POLICY = "policy"
    FAQ = "faq"
    GUIDE = "guide"
    PRODUCT_DOC = "product_doc"
    OTHER = "other"


class RetrievalStatus(str, Enum):
    USABLE = "usable"
    LOW_CONFIDENCE = "low_confidence"
    NO_ANSWER = "no_answer"
    DEGRADED = "degraded"


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str | None = None
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    doc_type: DocumentType = DocumentType.GUIDE
    policy_version: str | None = None
    effective_at: datetime | None = None

    @field_validator("document_id", "title", "content", "source", "policy_version")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("metadata field must not be blank")
        return value

    @model_validator(mode="after")
    def check_provenance(self) -> "KnowledgeDocument":
        if self.doc_type is DocumentType.POLICY:
            if not self.policy_version or self.effective_at is None:
                raise ValueError("policy documents require policy_version and effective_at")
        if self.effective_at is not None and self.effective_at.tzinfo is None:
            raise ValueError("effective_at must include a timezone")
        if self.document_id is None:
            digest = hashlib.sha256(
                f"{self.source}\0{self.title}\0{self.content}".encode("utf-8")
            ).hexdigest()[:20]
            self.document_id = f"doc_{digest}"
        return self


class ChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    doc_type: DocumentType
    chunk_index: int = Field(ge=0)
    total_chunks: int = Field(gt=0)
    policy_version: str | None = None
    effective_at: datetime | None = None

    @model_validator(mode="after")
    def check_chunk(self) -> "ChunkMetadata":
        if self.chunk_index >= self.total_chunks:
            raise ValueError("chunk_index must be below total_chunks")
        if self.doc_type is DocumentType.POLICY and (not self.policy_version or self.effective_at is None):
            raise ValueError("policy chunk lacks version or effective_at")
        if self.effective_at is not None and self.effective_at.tzinfo is None:
            raise ValueError("effective_at must include a timezone")
        return self


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    document_id: str
    chunk_index: int
    source: str
    policy_version: str | None = None


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    score: float
    score_kind: str = "one_minus_chroma_distance"
    document_id: str
    title: str
    source: str
    doc_type: str
    chunk_index: int
    total_chunks: int
    policy_version: str | None = None
    effective_at: datetime | None = None
    citation: Citation | None = None
    retrieval_status: RetrievalStatus
    reason_code: str | None = None

    @field_validator("score")
    @classmethod
    def finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value

    @model_validator(mode="after")
    def check_citation(self) -> "RetrievalHit":
        if self.doc_type == DocumentType.POLICY.value:
            if not self.policy_version or self.effective_at is None:
                raise ValueError("policy hits require version and effective_at")
            if self.effective_at.tzinfo is None:
                raise ValueError("policy effective_at must include a timezone")
        if self.retrieval_status is RetrievalStatus.USABLE:
            if self.citation is None:
                raise ValueError("usable hits require a citation")
            if (self.citation.document_id != self.document_id
                    or self.citation.chunk_index != self.chunk_index
                    or self.citation.source != self.source
                    or self.citation.policy_version != self.policy_version
                    or self.citation.reference != (
                        f"{self.document_id}{'@' + self.policy_version if self.policy_version else ''}#chunk-{self.chunk_index}"
                    )):
                raise ValueError("citation does not match hit provenance")
        elif self.citation is not None:
            raise ValueError("non-usable hits cannot carry a citation")
        return self


def build_hit(
    content: str,
    metadata: dict[str, Any] | None,
    distance: float,
    *,
    min_score: float,
    now: datetime | None = None,
) -> RetrievalHit:
    """Reject incomplete/legacy provenance as answer evidence, without inventing citations."""
    score = 1.0 - float(distance)
    if not math.isfinite(score):
        raise ValueError("Chroma returned a non-finite distance")
    try:
        chunk = ChunkMetadata.model_validate(metadata or {})
    except Exception:
        raw = metadata or {}
        raw_index = raw.get("chunk_index")
        raw_total = raw.get("total_chunks")
        return RetrievalHit(
            content=content, score=score, document_id=str(raw.get("document_id") or "legacy:unknown"),
            title=str(raw.get("title") or "未命名文档"), source="unknown",
            doc_type="unknown", chunk_index=raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else 0,
            total_chunks=raw_total if isinstance(raw_total, int) and not isinstance(raw_total, bool) else 0,
            retrieval_status=RetrievalStatus.LOW_CONFIDENCE,
            reason_code="missing_metadata",
        )

    effective = chunk.effective_at
    future_policy = (
        chunk.doc_type is DocumentType.POLICY
        and effective is not None
        and effective > (now or datetime.now(timezone.utc))
    )
    usable = score >= min_score and not future_policy and bool(content.strip())
    citation = None
    if usable:
        citation = Citation(
            reference=f"{chunk.document_id}{'@' + chunk.policy_version if chunk.policy_version else ''}#chunk-{chunk.chunk_index}",
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            source=chunk.source,
            policy_version=chunk.policy_version,
        )
    return RetrievalHit(
        content=content, score=score, document_id=chunk.document_id,
        title=chunk.title, source=chunk.source, doc_type=chunk.doc_type.value,
        chunk_index=chunk.chunk_index, total_chunks=chunk.total_chunks,
        policy_version=chunk.policy_version, effective_at=effective,
        citation=citation,
        retrieval_status=RetrievalStatus.USABLE if usable else RetrievalStatus.LOW_CONFIDENCE,
        reason_code="not_yet_effective" if future_policy else "low_score" if score < min_score else None,
    )
