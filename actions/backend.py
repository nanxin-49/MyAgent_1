"""Write command contract and explicitly simulated e-commerce backend."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol

from providers.errors import BackendDependencyError
from providers.models import OrderStatus, RefundRecord, RefundStatus
from providers.mock_backend import InMemoryBusinessState
from pydantic import ValidationError


class ActionBackendError(Exception):
    """Expected failure from a business action backend."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BusinessActionBackend(Protocol):
    """Command interface; action service is storage independent."""

    def execute_refund(
        self, order_id: str, *, customer_id: str, amount: Decimal, action_id: str
    ) -> dict[str, Any]: ...

    def execute_cancel(
        self, order_id: str, *, customer_id: str, action_id: str
    ) -> dict[str, Any]: ...


class InMemoryBusinessActionBackend:
    """Clearly marked test/demo command backend, never a real payment gateway."""

    backend_name = "mock-action-fixture"

    def __init__(
        self,
        data: Mapping[str, Any] | InMemoryBusinessState,
        *,
        fail_operations: Iterable[str] = (),
    ) -> None:
        self.state = data if isinstance(data, InMemoryBusinessState) else InMemoryBusinessState(data)
        self._data = self.state.data
        self._fail_operations = set(fail_operations)
        self.calls: list[dict[str, Any]] = []

    def _order(self, order_id: str, customer_id: str) -> dict[str, Any]:
        record = self._data["orders"].get(order_id)
        if not isinstance(record, dict):
            raise ActionBackendError("not_found", "订单不存在")
        if record.get("customer_id") != customer_id:
            raise ActionBackendError("unauthorized", "订单不属于当前客户")
        return record

    def execute_refund(
        self, order_id: str, *, customer_id: str, amount: Decimal, action_id: str
    ) -> dict[str, Any]:
        if "execute_refund" in self._fail_operations:
            raise BackendDependencyError("mock refund backend failure")
        with self.state.lock:
            order = self._order(order_id, customer_id)
            refund_id = "REF-" + action_id
            refunds = self._data["refunds"]
            existing = refunds.get(refund_id)
            if existing is not None:
                # A command replay can return only its own immutable record.
                try:
                    existing_record = RefundRecord.model_validate(existing)
                except ValidationError:
                    raise ActionBackendError("invalid_refund_record", "退款申请记录无效") from None
                if (existing_record.order_id, existing_record.customer_id, existing_record.amount) != (
                    order_id, customer_id, amount
                ):
                    raise ActionBackendError("refund_record_conflict", "退款编号已绑定其他参数")
                return self._refund_receipt(existing)
            if order["status"] in {OrderStatus.REFUND_PENDING.value, OrderStatus.REFUNDED.value}:
                raise ActionBackendError("refund_already_started", "订单退款已开始，不能重复执行")
            now = datetime.now(timezone.utc)
            try:
                record = RefundRecord(refund_id=refund_id, order_id=order_id,
                    customer_id=customer_id, status=RefundStatus.PENDING, amount=amount,
                    currency=order.get("currency", "CNY"), reason="simulated_refund_request",
                    created_at=now, updated_at=now).model_dump(mode="json")
            except ValidationError:
                raise ActionBackendError("invalid_refund_record", "退款申请记录无效") from None
            receipt = self._refund_receipt(record)
            previous_status = order["status"]
            previous_calls = len(self.calls)
            try:
                refunds[refund_id] = record
                order["status"] = OrderStatus.REFUND_PENDING.value
                self.calls.append({"operation": "refund", "order_id": order_id, "action_id": action_id})
            except Exception:
                refunds.pop(refund_id, None)
                order["status"] = previous_status
                del self.calls[previous_calls:]
                raise ActionBackendError("refund_commit_failed", "模拟退款状态写入失败") from None
            return receipt

    @staticmethod
    def _refund_receipt(record: Mapping[str, Any]) -> dict[str, Any]:
        return {"simulated": True, "operation": "refund", "order_id": record["order_id"],
                "amount": record["amount"], "status": "completed",
                "refund_id": record["refund_id"], "refund_status": record["status"]}

    def execute_cancel(
        self, order_id: str, *, customer_id: str, action_id: str
    ) -> dict[str, Any]:
        if "execute_cancel" in self._fail_operations:
            raise BackendDependencyError("mock cancel backend failure")
        with self.state.lock:
            order = self._order(order_id, customer_id)
            self.calls.append({"operation": "cancel", "order_id": order_id, "action_id": action_id})
            order["status"] = OrderStatus.CANCELLED.value
        return {
            "simulated": True,
            "operation": "cancel",
            "order_id": order_id,
            "status": "completed",
        }


__all__ = ["ActionBackendError", "BusinessActionBackend", "InMemoryBusinessActionBackend"]
