from datetime import datetime, timezone
from decimal import Decimal

import pytest

from policies import PolicyDecisionType, PolicyEngine
from providers.models import OrderStatus, RefundRecord
from providers.mock_backend import InMemoryBusinessBackend


FIXTURE = "tests/fixtures/business_provider_data.json"
EVALUATED_AT = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)


def provider_order():
    from providers import OrderProvider

    backend = InMemoryBusinessBackend.from_fixture(FIXTURE)
    return OrderProvider(backend).get_order("ORD-1001", customer_id="customer-1")


def with_order(order, **changes):
    return order.__class__.model_validate({**order.model_dump(), **changes})


def test_eligible_refund_returns_allow_and_structured_audit_fields():
    result = PolicyEngine().evaluate_refund(
        provider_order(), customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.decision is PolicyDecisionType.ALLOW
    assert result.reason_code == "refund_eligible"
    assert result.policy_version == "refund-cancel-v1"
    assert result.action == "refund"
    assert result.requires_approval is False
    assert result.amount == Decimal("129.90")


def test_expired_refund_window_is_denied():
    result = PolicyEngine().evaluate_refund(
        provider_order(),
        customer_id="customer-1",
        evaluated_at=datetime(2026, 9, 28, 10, 1, tzinfo=timezone.utc),
    )

    assert result.decision is PolicyDecisionType.DENY
    assert result.reason_code == "refund_window_expired"


def test_invalid_order_status_is_denied_for_refund():
    order = with_order(provider_order(), status=OrderStatus.CANCELLED)
    result = PolicyEngine().evaluate_refund(
        order, customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.decision is PolicyDecisionType.DENY
    assert result.reason_code == "order_status_not_refundable"


def test_amount_threshold_requires_approval():
    order = with_order(provider_order(), total_amount=Decimal("800.00"))
    result = PolicyEngine().evaluate_refund(
        order,
        customer_id="customer-1",
        evaluated_at=EVALUATED_AT,
        amount=Decimal("600.00"),
    )

    assert result.decision is PolicyDecisionType.REQUIRE_APPROVAL
    assert result.reason_code == "amount_requires_approval"
    assert result.requires_approval is True


def test_cancel_allowed_for_pending_order():
    order = with_order(provider_order(), status=OrderStatus.PENDING)
    result = PolicyEngine().evaluate_cancel(
        order, customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.decision is PolicyDecisionType.ALLOW
    assert result.reason_code == "cancel_eligible"
    assert result.action == "cancel"


def test_cancel_denied_after_shipping():
    result = PolicyEngine().evaluate_cancel(
        provider_order(), customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.decision is PolicyDecisionType.DENY
    assert result.reason_code == "order_status_not_cancellable"


def test_processing_cancel_requires_approval():
    order = with_order(provider_order(), status=OrderStatus.PROCESSING)
    result = PolicyEngine().evaluate_cancel(
        order, customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.decision is PolicyDecisionType.REQUIRE_APPROVAL
    assert result.reason_code == "processing_order_requires_approval"


def test_ownership_is_a_prerequisite_for_both_actions():
    order = provider_order()
    refund = PolicyEngine().evaluate_refund(
        order, customer_id="customer-2", evaluated_at=EVALUATED_AT
    )
    cancel = PolicyEngine().evaluate_cancel(
        order, customer_id="customer-2", evaluated_at=EVALUATED_AT
    )

    assert refund.decision is PolicyDecisionType.DENY
    assert refund.reason_code == "ownership_mismatch"
    assert cancel.decision is PolicyDecisionType.DENY
    assert cancel.reason_code == "ownership_mismatch"


def test_malformed_policy_input_returns_structured_deny():
    result = PolicyEngine().evaluate_refund(
        {"order_id": "ORD-1001"},
        customer_id="customer-1",
        evaluated_at=EVALUATED_AT,
    )

    assert result.decision is PolicyDecisionType.DENY
    assert result.reason_code == "invalid_policy_input"
    assert result.policy_version == "refund-cancel-v1"


def test_invalid_amount_has_explicit_reason_code():
    result = PolicyEngine().evaluate_refund(
        provider_order(),
        customer_id="customer-1",
        evaluated_at=EVALUATED_AT,
        amount=Decimal("-1.00"),
    )

    assert result.decision is PolicyDecisionType.DENY
    assert result.reason_code == "invalid_amount"


def test_refund_record_must_belong_to_same_order():
    refund = RefundRecord.model_validate(
        {
            "refund_id": "REF-OTHER",
            "order_id": "ORD-OTHER",
            "customer_id": "customer-1",
            "status": "requested",
            "amount": "10.00",
            "reason": "test",
            "created_at": "2026-09-21T10:00:00Z",
            "updated_at": "2026-09-21T10:00:00Z",
        }
    )
    result = PolicyEngine().evaluate_refund(
        provider_order(),
        customer_id="customer-1",
        evaluated_at=EVALUATED_AT,
        existing_refund=refund,
    )

    assert result.reason_code == "refund_order_mismatch"


def test_cancel_denies_invalid_order_time():
    order = with_order(
        provider_order(),
        status=OrderStatus.PENDING,
        created_at=datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
    )
    result = PolicyEngine().evaluate_cancel(
        order, customer_id="customer-1", evaluated_at=EVALUATED_AT
    )

    assert result.reason_code == "invalid_order_time"


def test_custom_policy_version_is_propagated():
    result = PolicyEngine(policy_version="refund-cancel-v2").evaluate_cancel(
        with_order(provider_order(), status=OrderStatus.PENDING),
        customer_id="customer-1",
        evaluated_at=EVALUATED_AT,
    )

    assert result.policy_version == "refund-cancel-v2"


def test_rule_change_requires_new_policy_version():
    with pytest.raises(ValueError, match="policy_version"):
        PolicyEngine(refund_window_days=14)
