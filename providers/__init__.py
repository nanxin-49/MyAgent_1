"""Business fact providers for dynamic e-commerce data.

Providers are intentionally independent from Agent tools and from any concrete
storage or external API.  The mock backend is only a test/demo implementation.
"""

from .errors import (
    BackendDependencyError,
    InvalidProviderInputError,
    NotFoundError,
    ProviderDataError,
    ProviderDependencyError,
    ProviderError,
    UnauthorizedError,
)
from .implementations import (
    InventoryProvider,
    LogisticsProvider,
    OrderProvider,
    ProductProvider,
    RefundProvider,
)
from .models import (
    InventorySnapshot,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    RefundRecord,
    RefundStatus,
    Shipment,
    ShipmentStatus,
)

__all__ = [
    "BackendDependencyError",
    "InvalidProviderInputError",
    "NotFoundError",
    "ProviderDataError",
    "ProviderDependencyError",
    "ProviderError",
    "UnauthorizedError",
    "InventoryProvider",
    "LogisticsProvider",
    "OrderProvider",
    "ProductProvider",
    "RefundProvider",
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
