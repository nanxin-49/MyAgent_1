"""Write command contract and explicitly simulated e-commerce backend."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping, Protocol

from providers.errors import BackendDependencyError
from providers.models import OrderStatus


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
        data: Mapping[str, Any],
        *,
        fail_operations: Iterable[str] = (),
    ) -> None:
        self._data = {"orders": dict(data.get("orders", {}))}
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
        order = self._order(order_id, customer_id)
        self.calls.append({"operation": "refund", "order_id": order_id, "action_id": action_id})
        order["status"] = OrderStatus.REFUND_PENDING.value
        return {
            "simulated": True,
            "operation": "refund",
            "order_id": order_id,
            "amount": str(amount),
            "status": "completed",
        }

    def execute_cancel(
        self, order_id: str, *, customer_id: str, action_id: str
    ) -> dict[str, Any]:
        if "execute_cancel" in self._fail_operations:
            raise BackendDependencyError("mock cancel backend failure")
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
