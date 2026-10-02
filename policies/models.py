"""Typed inputs and outputs for deterministic refund/cancel policy checks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from providers.models import Order, RefundRecord


class PolicyDecisionType(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class _PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    order: Order
    customer_id: str
    evaluated_at: datetime
    amount: Decimal | None = None
    existing_refund: RefundRecord | None = None


class RefundPolicyInput(_PolicyInput):
    """Provider facts and caller identity required for a refund decision."""


class CancelPolicyInput(_PolicyInput):
    """Provider facts and caller identity required for a cancel decision."""


class PolicyDecision(BaseModel):
    """Stable policy result designed for later Tool/HITL consumption."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["refund", "cancel"]
    decision: PolicyDecisionType
    reason_code: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    order_id: str | None = None
    amount: Decimal | None = None
    evaluated_at: datetime
    requires_approval: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CancelPolicyInput",
    "PolicyDecision",
    "PolicyDecisionType",
    "RefundPolicyInput",
]
