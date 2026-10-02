"""Pending action, approval, idempotency, and resume service."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import RLock
from typing import Any, Callable

from policies import PolicyDecision, PolicyDecisionType, PolicyEngine
from providers import OrderProvider, RefundProvider
from providers.errors import BackendDependencyError, NotFoundError, ProviderError
from providers.interfaces import BusinessBackend

from .backend import ActionBackendError, BusinessActionBackend
from .executor import ActionExecutor
from .models import ActionResult, ActionStatus, ActionType, PendingAction
from .store import ActionStore, InMemoryActionStore


class ActionService:
    """Orchestrates authoritative facts, Policy, approval, and execution."""

    def __init__(
        self,
        *,
        business_backend: BusinessBackend,
        action_backend: BusinessActionBackend,
        policy_engine: PolicyEngine | None = None,
        store: ActionStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._business_backend = business_backend
        self._order_provider = OrderProvider(business_backend)
        self._refund_provider = RefundProvider(business_backend)
        self._policy = policy_engine or PolicyEngine()
        self._store = store or InMemoryActionStore()
        self._executor = ActionExecutor(action_backend)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = getattr(self._store, "lock", RLock())

    def request_refund(
        self,
        *,
        order_id: str,
        user_id: str,
        request_id: str,
        amount: Any = None,
        idempotency_key: str | None = None,
    ) -> ActionResult:
        return self._request(
            ActionType.REFUND,
            order_id=order_id,
            user_id=user_id,
            request_id=request_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )

    def request_cancel(
        self,
        *,
        order_id: str,
        user_id: str,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> ActionResult:
        return self._request(
            ActionType.CANCEL_ORDER,
            order_id=order_id,
            user_id=user_id,
            request_id=request_id,
            amount=None,
            idempotency_key=idempotency_key,
        )

    def approve(self, *, action_id: str, user_id: str, request_id: str) -> ActionResult:
        with self._lock:
            action = self._owned_action(action_id, user_id)
            if isinstance(action, ActionResult):
                return action
            if action.status is ActionStatus.AWAITING_APPROVAL:
                action.status = ActionStatus.APPROVED
                action.updated_at = self._now()
                self._store.save(action)
                return self._execute_locked(action, request_id=request_id)
            if action.status in {
                ActionStatus.COMPLETED,
                ActionStatus.REJECTED,
                ActionStatus.FAILED,
                ActionStatus.EXECUTING,
            }:
                return self._result(action, reused=True)
            return self._invalid_transition(action, "approve")

    def reject(self, *, action_id: str, user_id: str, request_id: str) -> ActionResult:
        with self._lock:
            action = self._owned_action(action_id, user_id)
            if isinstance(action, ActionResult):
                return action
            if action.status is ActionStatus.AWAITING_APPROVAL:
                action.status = ActionStatus.REJECTED
                action.error_code = "approval_rejected"
                action.error_message = "客户拒绝了该敏感动作"
                action.updated_at = self._now()
                self._store.save(action)
                return self._result(action)
            if action.status in {
                ActionStatus.COMPLETED,
                ActionStatus.REJECTED,
                ActionStatus.FAILED,
                ActionStatus.EXECUTING,
            }:
                return self._result(action, reused=True)
            return self._invalid_transition(action, "reject")

    def resume(self, *, action_id: str, user_id: str, request_id: str) -> ActionResult:
        with self._lock:
            action = self._owned_action(action_id, user_id)
            if isinstance(action, ActionResult):
                return action
            if action.status is ActionStatus.APPROVED:
                return self._execute_locked(action, request_id=request_id)
            if action.status is ActionStatus.AWAITING_APPROVAL:
                return self._result(action, reused=True)
            if action.status in {
                ActionStatus.COMPLETED,
                ActionStatus.REJECTED,
                ActionStatus.FAILED,
                ActionStatus.EXECUTING,
            }:
                return self._result(action, reused=True)
            return self._invalid_transition(action, "resume")

    def get(self, action_id: str, *, user_id: str) -> ActionResult:
        with self._lock:
            return self._result_or_error(self._owned_action(action_id, user_id))

    def _request(
        self,
        action_type: ActionType,
        *,
        order_id: str,
        user_id: str,
        request_id: str,
        amount: Any,
        idempotency_key: str | None,
    ) -> ActionResult:
        if not all(isinstance(value, str) and value.strip() for value in (order_id, user_id, request_id)):
            return self._simple_error("invalid_action_input", "action 输入缺少 order_id、user_id 或 request_id")
        parsed_amount = self._parse_amount(amount)
        if amount is not None and parsed_amount is None:
            return self._simple_error("invalid_amount", "action 金额格式无效")

        with self._lock:
            if idempotency_key:
                existing = self._store.find_by_idempotency(idempotency_key)
                if existing is not None:
                    return self._result(existing, reused=True)

            try:
                order = self._order_provider.get_order(order_id, customer_id=user_id)
                if parsed_amount is None:
                    parsed_amount = order.total_amount
                key = self._idempotency_key(
                    action_type, user_id, order_id, parsed_amount, idempotency_key
                )
                existing = self._store.find_by_idempotency(key)
                if existing is not None:
                    return self._result(existing, reused=True)
                existing_refund = self._existing_refund(order_id, user_id) if action_type is ActionType.REFUND else None
                policy = self._evaluate(action_type, order, user_id, parsed_amount, existing_refund)
            except ProviderError as exc:
                key = self._idempotency_key(action_type, user_id, order_id, parsed_amount, idempotency_key)
                return self._create_provider_failure(
                    action_type, order_id, user_id, request_id, parsed_amount, key, exc
                )

            action = self._new_action(
                action_type, order_id, user_id, request_id, parsed_amount, key, policy
            )
            if policy.decision is PolicyDecisionType.DENY:
                action.status = ActionStatus.REJECTED
                action.error_code = policy.reason_code
                action.error_message = policy.explanation
                self._store.save(action)
                return self._result(action)
            if policy.decision is PolicyDecisionType.REQUIRE_APPROVAL:
                action.status = ActionStatus.AWAITING_APPROVAL
                self._store.save(action)
                return self._result(action)

            action.status = ActionStatus.APPROVED
            self._store.save(action)
            return self._execute_locked(action, request_id=request_id)

    def _execute_locked(self, action: PendingAction, *, request_id: str) -> ActionResult:
        try:
            order = self._order_provider.get_order(action.order_id, customer_id=action.user_id)
            existing_refund = (
                self._existing_refund(action.order_id, action.user_id)
                if action.action_type is ActionType.REFUND
                else None
            )
            policy = self._evaluate(
                action.action_type, order, action.user_id, action.amount, existing_refund
            )
            action.policy_decision = policy
            action.policy_version = policy.policy_version
            action.updated_at = self._now()
            approval_already_granted = action.status is ActionStatus.APPROVED
            if policy.decision is PolicyDecisionType.DENY or (
                policy.decision is PolicyDecisionType.REQUIRE_APPROVAL
                and not approval_already_granted
            ):
                action.status = ActionStatus.REJECTED
                action.error_code = "policy_changed"
                action.error_message = policy.explanation
                self._store.save(action)
                return self._result(action)

            action.status = ActionStatus.EXECUTING
            action.updated_at = self._now()
            self._store.save(action)
            action.execution_result = self._executor.execute(
                action.action_type,
                action.order_id,
                user_id=action.user_id,
                amount=action.amount,
                action_id=action.action_id,
            )
            action.status = ActionStatus.COMPLETED
            action.updated_at = self._now()
            self._store.save(action)
            return self._result(action)
        except ProviderError as exc:
            return self._fail_action(action, exc.code, str(exc))
        except ActionBackendError as exc:
            return self._fail_action(action, exc.code, exc.message)
        except BackendDependencyError as exc:
            return self._fail_action(action, "dependency_failure", str(exc))
        except Exception as exc:
            return self._fail_action(action, "execution_failure", str(exc))

    def _evaluate(self, action_type, order, user_id, amount, existing_refund):
        if action_type is ActionType.REFUND:
            return self._policy.evaluate_refund(
                order,
                customer_id=user_id,
                evaluated_at=self._now(),
                amount=amount,
                existing_refund=existing_refund,
            )
        return self._policy.evaluate_cancel(
            order,
            customer_id=user_id,
            evaluated_at=self._now(),
            amount=amount,
        )

    def _existing_refund(self, order_id: str, user_id: str):
        try:
            return self._refund_provider.get_refund_for_order(order_id, customer_id=user_id)
        except NotFoundError:
            return None

    def _create_provider_failure(self, action_type, order_id, user_id, request_id, amount, key, exc):
        now = self._now()
        policy = PolicyDecision(
            action="refund" if action_type is ActionType.REFUND else "cancel",
            decision=PolicyDecisionType.DENY,
            reason_code=exc.code,
            policy_version=self._policy.policy_version,
            explanation=str(exc),
            order_id=order_id,
            amount=amount,
            evaluated_at=now,
            requires_approval=False,
        )
        action = self._new_action(action_type, order_id, user_id, request_id, amount, key, policy)
        action.status = ActionStatus.REJECTED if exc.code in {"not_found", "unauthorized"} else ActionStatus.FAILED
        action.error_code = exc.code
        action.error_message = str(exc)
        self._store.save(action)
        return self._result(action)

    def _new_action(self, action_type, order_id, user_id, request_id, amount, key, policy):
        now = self._now()
        return PendingAction(
            action_id=f"act_{uuid.uuid4().hex[:16]}",
            action_type=action_type,
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            policy_decision=policy,
            policy_version=policy.policy_version,
            status=ActionStatus.PENDING,
            created_at=now,
            updated_at=now,
            idempotency_key=key,
            request_id=request_id,
        )

    def _owned_action(self, action_id: str, user_id: str) -> PendingAction | ActionResult:
        action = self._store.get(action_id)
        if action is None:
            return self._simple_error("action_not_found", "PendingAction 不存在")
        if action.user_id != user_id:
            return self._simple_error("unauthorized", "当前客户无权操作该 PendingAction")
        return action

    def _fail_action(self, action: PendingAction, code: str, message: str) -> ActionResult:
        action.status = ActionStatus.FAILED
        action.error_code = code
        action.error_message = message
        action.updated_at = self._now()
        self._store.save(action)
        return self._result(action)

    def _invalid_transition(self, action: PendingAction, operation: str) -> ActionResult:
        return ActionResult(
            success=False,
            status=action.status,
            action_id=action.action_id,
            action=action,
            error_code="invalid_state_transition",
            message=f"不能在 {action.status.value} 状态执行 {operation}",
        )

    def _result_or_error(self, value):
        return value if isinstance(value, ActionResult) else self._result(value)

    @staticmethod
    def _result(action: PendingAction, *, reused: bool = False) -> ActionResult:
        return ActionResult(
            success=action.status not in {ActionStatus.REJECTED, ActionStatus.FAILED},
            status=action.status,
            action_id=action.action_id,
            action=action,
            error_code=action.error_code,
            message=action.error_message,
            reused=reused,
        )

    @staticmethod
    def _simple_error(code: str, message: str) -> ActionResult:
        return ActionResult(success=False, status=ActionStatus.FAILED, error_code=code, message=message)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _parse_amount(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        return amount if amount.is_finite() else None

    @staticmethod
    def _idempotency_key(action_type, user_id, order_id, amount, supplied):
        if supplied and supplied.strip():
            scoped = json.dumps(
                {
                    "action": action_type.value,
                    "user_id": user_id,
                    "supplied_key": supplied.strip(),
                },
                sort_keys=True,
            )
            return "idem_" + hashlib.sha256(scoped.encode("utf-8")).hexdigest()[:32]
        raw = json.dumps(
            {
                "action": action_type.value,
                "user_id": user_id,
                "order_id": order_id,
                "amount": str(amount) if amount is not None else None,
            },
            sort_keys=True,
        )
        return "auto_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


__all__ = ["ActionService"]
