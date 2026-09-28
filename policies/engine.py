"""Deterministic refund and cancel eligibility policies.

This module consumes already validated Provider models. It deliberately has no
Provider, backend, fixture, database, RAG, or write-action dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from providers.models import Order, OrderStatus, RefundRecord, RefundStatus

from .models import (
    CancelPolicyInput,
    PolicyDecision,
    PolicyDecisionType,
    RefundPolicyInput,
)


class PolicyEngine:
    """Evaluate refund/cancel constraints without executing an action."""

    POLICY_VERSION = "refund-cancel-v1"
    REFUND_WINDOW_DAYS = 7
    AUTO_APPROVAL_AMOUNT = Decimal("500.00")

    _REFUNDABLE_STATUSES = frozenset(
        {
            OrderStatus.PAID,
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        }
    )
    _CANCELLABLE_STATUSES = frozenset(
        {OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING}
    )
    _ACTIVE_REFUND_STATUSES = frozenset(
        {RefundStatus.REQUESTED, RefundStatus.APPROVED, RefundStatus.PROCESSING}
    )

    def __init__(
        self,
        *,
        policy_version: str = POLICY_VERSION,
        refund_window_days: int = REFUND_WINDOW_DAYS,
        auto_approval_amount: Decimal = AUTO_APPROVAL_AMOUNT,
    ) -> None:
        if not policy_version.strip():
            raise ValueError("policy_version 不能为空")
        if refund_window_days <= 0:
            raise ValueError("refund_window_days 必须大于 0")
        if auto_approval_amount <= 0:
            raise ValueError("auto_approval_amount 必须大于 0")
        if policy_version == self.POLICY_VERSION and (
            refund_window_days != self.REFUND_WINDOW_DAYS
            or Decimal(auto_approval_amount) != self.AUTO_APPROVAL_AMOUNT
        ):
            raise ValueError("变更规则参数时必须提供新的 policy_version")
        self.policy_version = policy_version
        self.refund_window_days = refund_window_days
        self.auto_approval_amount = Decimal(auto_approval_amount)

    def evaluate_refund(
        self,
        order: Any,
        *,
        customer_id: Any,
        evaluated_at: Any,
        amount: Any = None,
        existing_refund: Any = None,
    ) -> PolicyDecision:
        if not isinstance(order, Order) or (
            existing_refund is not None and not isinstance(existing_refund, RefundRecord)
        ):
            return self._invalid_input("refund", evaluated_at)
        try:
            context = RefundPolicyInput.model_validate(
                {
                    "order": order,
                    "customer_id": customer_id,
                    "evaluated_at": evaluated_at,
                    "amount": amount,
                    "existing_refund": existing_refund,
                }
            )
        except (ValidationError, TypeError, ValueError):
            return self._invalid_input("refund", evaluated_at)

        return self._evaluate_refund_context(context)

    def evaluate_cancel(
        self,
        order: Any,
        *,
        customer_id: Any,
        evaluated_at: Any,
        amount: Any = None,
    ) -> PolicyDecision:
        if not isinstance(order, Order):
            return self._invalid_input("cancel", evaluated_at)
        try:
            context = CancelPolicyInput.model_validate(
                {
                    "order": order,
                    "customer_id": customer_id,
                    "evaluated_at": evaluated_at,
                    "amount": amount,
                }
            )
        except (ValidationError, TypeError, ValueError):
            return self._invalid_input("cancel", evaluated_at)

        return self._evaluate_cancel_context(context)

    def _evaluate_refund_context(self, context: RefundPolicyInput) -> PolicyDecision:
        order = context.order
        base = self._base_kwargs("refund", order.order_id, context.evaluated_at)

        ownership = self._check_ownership(order.customer_id, context.customer_id)
        if ownership:
            return self._decision(PolicyDecisionType.DENY, ownership, "退款需要订单所有权验证", **base)

        time_error = self._check_time(order.created_at, context.evaluated_at)
        if time_error:
            return self._decision(PolicyDecisionType.DENY, time_error, "订单时间信息无法用于退款窗口判断", **base)

        if context.evaluated_at - order.created_at > timedelta(days=self.refund_window_days):
            return self._decision(
                PolicyDecisionType.DENY,
                "refund_window_expired",
                f"退款申请已超过 {self.refund_window_days} 天窗口",
                **base,
            )

        if order.status not in self._REFUNDABLE_STATUSES:
            return self._decision(
                PolicyDecisionType.DENY,
                "order_status_not_refundable",
                f"订单状态 {order.status.value} 不满足退款条件",
                **base,
            )

        if context.existing_refund is not None:
            if context.existing_refund.order_id != order.order_id:
                return self._decision(
                    PolicyDecisionType.DENY,
                    "refund_order_mismatch",
                    "退款记录与当前订单不匹配",
                    **base,
                )
            if context.existing_refund.customer_id != context.customer_id:
                return self._decision(
                    PolicyDecisionType.DENY,
                    "refund_ownership_mismatch",
                    "退款记录不属于当前客户",
                    **base,
                )
            if context.existing_refund.status == RefundStatus.COMPLETED:
                return self._decision(
                    PolicyDecisionType.DENY,
                    "refund_already_completed",
                    "该订单已经完成退款",
                    **base,
                )
            if context.existing_refund.status in self._ACTIVE_REFUND_STATUSES:
                return self._decision(
                    PolicyDecisionType.DENY,
                    "refund_already_in_progress",
                    "该订单已有进行中的退款记录",
                    **base,
                )

        requested_amount = context.amount if context.amount is not None else order.total_amount
        if requested_amount <= 0:
            return self._decision(
                PolicyDecisionType.DENY,
                "invalid_amount",
                "退款金额必须大于 0",
                amount=requested_amount,
                **base,
            )
        if requested_amount > order.total_amount:
            return self._decision(
                PolicyDecisionType.DENY,
                "amount_exceeds_order_total",
                "退款金额不能超过订单金额",
                amount=requested_amount,
                **base,
            )
        if requested_amount > self.auto_approval_amount:
            return self._decision(
                PolicyDecisionType.REQUIRE_APPROVAL,
                "amount_requires_approval",
                f"退款金额超过自动处理阈值 {self.auto_approval_amount}",
                amount=requested_amount,
                **base,
            )

        return self._decision(
            PolicyDecisionType.ALLOW,
            "refund_eligible",
            "订单状态、所有权、退款窗口和金额均符合退款条件",
            amount=requested_amount,
            **base,
        )

    def _evaluate_cancel_context(self, context: CancelPolicyInput) -> PolicyDecision:
        order = context.order
        base = self._base_kwargs("cancel", order.order_id, context.evaluated_at)

        ownership = self._check_ownership(order.customer_id, context.customer_id)
        if ownership:
            return self._decision(PolicyDecisionType.DENY, ownership, "取消订单需要订单所有权验证", **base)

        time_error = self._check_time(order.created_at, context.evaluated_at)
        if time_error:
            return self._decision(
                PolicyDecisionType.DENY,
                time_error,
                "订单时间信息无法用于取消资格判断",
                **base,
            )

        if order.status not in self._CANCELLABLE_STATUSES:
            return self._decision(
                PolicyDecisionType.DENY,
                "order_status_not_cancellable",
                f"订单状态 {order.status.value} 不允许取消",
                **base,
            )

        amount = context.amount if context.amount is not None else order.total_amount
        if amount <= 0 or amount > order.total_amount:
            return self._decision(
                PolicyDecisionType.DENY,
                "invalid_amount",
                "取消金额必须大于 0 且不能超过订单金额",
                amount=amount,
                **base,
            )
        if order.status == OrderStatus.PROCESSING:
            return self._decision(
                PolicyDecisionType.REQUIRE_APPROVAL,
                "processing_order_requires_approval",
                "订单已进入处理中，取消需要审批",
                amount=amount,
                **base,
            )
        if amount > self.auto_approval_amount:
            return self._decision(
                PolicyDecisionType.REQUIRE_APPROVAL,
                "amount_requires_approval",
                f"取消金额超过自动处理阈值 {self.auto_approval_amount}",
                amount=amount,
                **base,
            )

        return self._decision(
            PolicyDecisionType.ALLOW,
            "cancel_eligible",
            "订单状态、所有权和金额均符合取消条件",
            amount=amount,
            **base,
        )

    def _invalid_input(self, action: str, evaluated_at: Any) -> PolicyDecision:
        when = evaluated_at if isinstance(evaluated_at, datetime) else datetime(1970, 1, 1, tzinfo=timezone.utc)
        return self._decision(
            PolicyDecisionType.DENY,
            "invalid_policy_input",
            "Policy 输入缺少有效的结构化订单事实、身份、时间或金额",
            action=action,
            order_id=None,
            evaluated_at=when,
        )

    def _decision(
        self,
        decision: PolicyDecisionType,
        reason_code: str,
        explanation: str,
        *,
        action: str = "refund",
        order_id: str | None = None,
        amount: Decimal | None = None,
        evaluated_at: datetime,
    ) -> PolicyDecision:
        return PolicyDecision(
            action=action,  # type: ignore[arg-type]
            decision=decision,
            reason_code=reason_code,
            policy_version=self.policy_version,
            explanation=explanation,
            order_id=order_id,
            amount=amount,
            evaluated_at=evaluated_at,
            requires_approval=decision is PolicyDecisionType.REQUIRE_APPROVAL,
        )

    @staticmethod
    def _base_kwargs(action: str, order_id: str, evaluated_at: datetime) -> dict[str, Any]:
        return {"action": action, "order_id": order_id, "evaluated_at": evaluated_at}

    @staticmethod
    def _check_ownership(order_customer_id: str, customer_id: str) -> str | None:
        if not customer_id.strip():
            return "ownership_required"
        if order_customer_id != customer_id:
            return "ownership_mismatch"
        return None

    @staticmethod
    def _check_time(created_at: datetime, evaluated_at: datetime) -> str | None:
        if created_at.tzinfo is None or evaluated_at.tzinfo is None:
            return "invalid_order_time"
        if evaluated_at < created_at:
            return "invalid_order_time"
        return None


__all__ = ["PolicyEngine"]
