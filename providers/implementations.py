"""Default Provider implementations over the storage-independent backend."""

from __future__ import annotations

from typing import Callable, Generic, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import (
    BackendDependencyError,
    InvalidProviderInputError,
    NotFoundError,
    ProviderDataError,
    ProviderDependencyError,
    UnauthorizedError,
)
from .interfaces import BusinessBackend, RawRecord
from .models import InventorySnapshot, Order, Product, RefundRecord, Shipment


ModelT = TypeVar("ModelT", bound=BaseModel)


class _BaseProvider(Generic[ModelT]):
    resource_type = "resource"

    def __init__(self, backend: BusinessBackend) -> None:
        self._backend = backend

    @staticmethod
    def _require_id(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise InvalidProviderInputError(f"{field_name} 不能为空")
        return normalized

    def _read(
        self,
        resource_id: str,
        fetch: Callable[[str], RawRecord | None],
        model_type: Type[ModelT],
        *,
        owner_id: str | None = None,
    ) -> ModelT:
        resource_id = self._require_id(resource_id, f"{self.resource_type}_id")
        if owner_id is not None:
            owner_id = self._require_id(owner_id, "customer_id")

        try:
            raw = fetch(resource_id)
        except BackendDependencyError as exc:
            raise ProviderDependencyError(
                f"读取 {self.resource_type} 依赖失败",
                resource_type=self.resource_type,
                resource_id=resource_id,
            ) from exc
        except Exception as exc:
            raise ProviderDependencyError(
                f"读取 {self.resource_type} 依赖失败",
                resource_type=self.resource_type,
                resource_id=resource_id,
            ) from exc

        if raw is None:
            raise NotFoundError(
                f"未找到 {self.resource_type}",
                resource_type=self.resource_type,
                resource_id=resource_id,
            )

        try:
            model = model_type.model_validate(raw)
        except ValidationError as exc:
            raise ProviderDataError(
                f"{self.resource_type} 数据未通过模型校验",
                resource_type=self.resource_type,
                resource_id=resource_id,
                details={"validation_errors": exc.errors(include_url=False)},
            ) from exc

        if owner_id is not None and getattr(model, "customer_id", None) != owner_id:
            raise UnauthorizedError(
                f"当前 customer 无权访问该 {self.resource_type}",
                resource_type=self.resource_type,
                resource_id=resource_id,
                details={"customer_id": owner_id},
            )
        return model


class ProductProvider(_BaseProvider[Product]):
    resource_type = "product"

    def get_product(self, product_id: str) -> Product:
        return self._read(
            product_id,
            lambda key: self._backend.get_product(key),
            Product,
        )


class OrderProvider(_BaseProvider[Order]):
    resource_type = "order"

    def get_order(self, order_id: str, *, customer_id: str) -> Order:
        return self._read(
            order_id,
            lambda key: self._backend.get_order(key),
            Order,
            owner_id=customer_id,
        )


class InventoryProvider(_BaseProvider[InventorySnapshot]):
    resource_type = "inventory"

    def get_inventory(self, product_id: str) -> InventorySnapshot:
        return self._read(
            product_id,
            lambda key: self._backend.get_inventory(key),
            InventorySnapshot,
        )


class LogisticsProvider(_BaseProvider[Shipment]):
    resource_type = "shipment"

    def get_shipment(self, order_id: str, *, customer_id: str) -> Shipment:
        return self._read(
            order_id,
            lambda key: self._backend.get_shipment(key),
            Shipment,
            owner_id=customer_id,
        )


class RefundProvider(_BaseProvider[RefundRecord]):
    resource_type = "refund"

    def get_refund(self, refund_id: str, *, customer_id: str) -> RefundRecord:
        return self._read(
            refund_id,
            lambda key: self._backend.get_refund(key),
            RefundRecord,
            owner_id=customer_id,
        )

    def get_refund_for_order(self, order_id: str, *, customer_id: str) -> RefundRecord:
        return self._read(
            order_id,
            lambda key: self._backend.get_refund_for_order(key),
            RefundRecord,
            owner_id=customer_id,
        )


__all__ = [
    "InventoryProvider",
    "LogisticsProvider",
    "OrderProvider",
    "ProductProvider",
    "RefundProvider",
]
