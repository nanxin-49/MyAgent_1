import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from providers import (
    InventoryProvider,
    LogisticsProvider,
    NotFoundError,
    OrderProvider,
    ProductProvider,
    ProviderDataError,
    ProviderDependencyError,
    RefundProvider,
    UnauthorizedError,
)
from providers.mock_backend import InMemoryBusinessBackend
from providers.models import InventorySnapshot, OrderStatus, ShipmentStatus


FIXTURE = Path(__file__).parent / "fixtures" / "business_provider_data.json"


@pytest.fixture()
def backend() -> InMemoryBusinessBackend:
    return InMemoryBusinessBackend.from_fixture(FIXTURE)


def test_all_providers_return_validated_business_facts(backend):
    product = ProductProvider(backend).get_product(" SKU-1001 ")
    order = OrderProvider(backend).get_order("ORD-1001", customer_id="customer-1")
    inventory = InventoryProvider(backend).get_inventory("SKU-1001")
    shipment = LogisticsProvider(backend).get_shipment("ORD-1001", customer_id="customer-1")
    refund = RefundProvider(backend).get_refund("REF-1001", customer_id="customer-1")

    assert product.name == "CartCare Demo Backpack"
    assert product.price == Decimal("129.90")
    assert order.status is OrderStatus.SHIPPED
    assert order.items[0].quantity == 1
    assert inventory.available_quantity == 12
    assert shipment.status is ShipmentStatus.IN_TRANSIT
    assert refund.order_id == order.order_id


def test_refund_provider_can_lookup_by_order(backend):
    refund = RefundProvider(backend).get_refund_for_order(
        "ORD-1001",
        customer_id="customer-1",
    )

    assert refund.refund_id == "REF-1001"


def test_not_found_is_typed_and_serializable(backend):
    with pytest.raises(NotFoundError) as caught:
        ProductProvider(backend).get_product("SKU-MISSING")

    assert caught.value.code == "not_found"
    assert caught.value.to_dict()["resource_type"] == "product"


def test_customer_ownership_is_enforced_by_read_providers(backend):
    with pytest.raises(UnauthorizedError) as caught:
        OrderProvider(backend).get_order("ORD-1001", customer_id="customer-2")

    assert caught.value.code == "unauthorized"
    assert caught.value.resource_id == "ORD-1001"


def test_backend_failure_is_wrapped_as_dependency_failure():
    failing_backend = InMemoryBusinessBackend(
        json.loads(FIXTURE.read_text(encoding="utf-8")),
        fail_operations={"get_order"},
    )

    with pytest.raises(ProviderDependencyError) as caught:
        OrderProvider(failing_backend).get_order("ORD-1001", customer_id="customer-1")

    assert caught.value.code == "dependency_failure"
    assert caught.value.resource_type == "order"
    assert failing_backend.backend_name == "mock-fixture"


def test_invalid_backend_record_is_rejected_before_returning_facts():
    backend = InMemoryBusinessBackend(
        {
            "products": {
                "SKU-BAD": {
                    "product_id": "SKU-BAD",
                    "name": "",
                    "price": "not-a-number",
                }
            }
        }
    )

    with pytest.raises(ProviderDataError) as caught:
        ProductProvider(backend).get_product("SKU-BAD")

    assert caught.value.code == "invalid_data"


def test_invalid_inventory_record_is_rejected_before_returning_facts():
    backend = InMemoryBusinessBackend(
        {
            "inventory": {
                "SKU-BAD": {
                    "product_id": "SKU-BAD",
                    "available_quantity": -1,
                    "reserved_quantity": 0,
                    "as_of": "2026-09-27T10:00:00Z",
                }
            }
        }
    )

    with pytest.raises(ProviderDataError):
        InventoryProvider(backend).get_inventory("SKU-BAD")


def test_model_validation_rejects_negative_inventory():
    with pytest.raises(ValidationError):
        InventorySnapshot(
            product_id="SKU-BAD",
            available_quantity=-1,
            reserved_quantity=0,
            as_of="2026-09-27T10:00:00Z",
        )
