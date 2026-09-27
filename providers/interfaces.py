"""Storage-independent contracts for business fact access."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .models import InventorySnapshot, Order, Product, RefundRecord, Shipment


RawRecord = Mapping[str, Any]


class BusinessBackend(Protocol):
    """Read-only backend contract implemented by DB/API/fixture adapters."""

    def get_product(self, product_id: str) -> RawRecord | None: ...

    def get_order(self, order_id: str) -> RawRecord | None: ...

    def get_inventory(self, product_id: str) -> RawRecord | None: ...

    def get_shipment(self, order_id: str) -> RawRecord | None: ...

    def get_refund(self, refund_id: str) -> RawRecord | None: ...

    def get_refund_for_order(self, order_id: str) -> RawRecord | None: ...


class ProductProviderContract(Protocol):
    def get_product(self, product_id: str) -> Product: ...


class OrderProviderContract(Protocol):
    def get_order(self, order_id: str, *, customer_id: str) -> Order: ...


class InventoryProviderContract(Protocol):
    def get_inventory(self, product_id: str) -> InventorySnapshot: ...


class LogisticsProviderContract(Protocol):
    def get_shipment(self, order_id: str, *, customer_id: str) -> Shipment: ...


class RefundProviderContract(Protocol):
    def get_refund(self, refund_id: str, *, customer_id: str) -> RefundRecord: ...

    def get_refund_for_order(self, order_id: str, *, customer_id: str) -> RefundRecord: ...


__all__ = [
    "BusinessBackend",
    "InventoryProviderContract",
    "LogisticsProviderContract",
    "OrderProviderContract",
    "ProductProviderContract",
    "RawRecord",
    "RefundProviderContract",
]
