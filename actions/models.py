"""Pending sensitive business actions and their externally visible results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from policies.models import PolicyDecision


class ActionType(str, Enum):
    REFUND = "refund"
    CANCEL_ORDER = "cancel_order"


class ActionStatus(str, Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class PendingAction(BaseModel):
    """Durable-shaped state passed between request, approval, and resume."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    action_type: ActionType
    user_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    amount: Decimal | None = None
    policy_decision: PolicyDecision
    policy_version: str = Field(min_length=1)
    status: ActionStatus
    created_at: datetime
    updated_at: datetime
    idempotency_key: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    error_code: str | None = None
    error_message: str | None = None
    execution_result: dict[str, Any] | None = None


class ActionResult(BaseModel):
    """Stable Tool/API result; awaiting approval is an accepted pause."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    status: ActionStatus
    action_id: str | None = None
    action: PendingAction | None = None
    error_code: str | None = None
    message: str | None = None
    reused: bool = False

    def to_tool_result(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


__all__ = ["ActionResult", "ActionStatus", "ActionType", "PendingAction"]
