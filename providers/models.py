"""Validated domain models returned by business providers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"


class RefundStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class Product(_ProviderModel):
    product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    active: bool = True


class OrderItem(_ProviderModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=Decimal("0"))


class Order(_ProviderModel):
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    status: OrderStatus
    items: list[OrderItem] = Field(min_length=1)
    total_amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    created_at: datetime


class InventorySnapshot(_ProviderModel):
    product_id: str = Field(min_length=1)
    available_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    as_of: datetime


class Shipment(_ProviderModel):
    shipment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    carrier: str = Field(min_length=1)
    tracking_number: str = Field(min_length=1)
    status: ShipmentStatus
    estimated_delivery: date | None = None
    updated_at: datetime


class RefundRecord(_ProviderModel):
    refund_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    status: RefundStatus
    amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    reason: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime


__all__ = [
    "InventorySnapshot",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "RefundRecord",
    "RefundStatus",
    "Shipment",
    "ShipmentStatus",
]
