"""Single command execution boundary for sensitive actions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .backend import BusinessActionBackend
from .models import ActionType


class ActionExecutor:
    """Calls only the injected command backend; no LLM or policy decisions here."""

    def __init__(self, backend: BusinessActionBackend) -> None:
        self._backend = backend

    def execute(
        self,
        action_type: ActionType,
        order_id: str,
        *,
        user_id: str,
        amount: Decimal | None,
        action_id: str,
    ) -> dict[str, Any]:
        if action_type is ActionType.REFUND:
            if amount is None:
                raise ValueError("refund action 缺少 amount")
            return self._backend.execute_refund(
                order_id, customer_id=user_id, amount=amount, action_id=action_id
            )
        if action_type is ActionType.CANCEL_ORDER:
            return self._backend.execute_cancel(
                order_id, customer_id=user_id, action_id=action_id
            )
        raise ValueError(f"不支持的 action_type: {action_type}")


__all__ = ["ActionExecutor"]
