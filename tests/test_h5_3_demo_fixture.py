"""H5-3 demo fixture: policy, composite approval, and ownership scenes."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from actions import ActionStatus
from demo.prepare_h5_3 import ORDER_IDS, prepare
from demo.preflight_h5_3 import auth_env_errors, fixture_errors
from demo.print_credentials import credentials, export_lines
from evaluation.topology_experiment import isolated_business
from tests.auth_helpers import customer

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def fixture():
    data, scenarios = prepare(NOW)
    return data, scenarios


def test_fixture_has_demo_orders_and_scenarios():
    data, scenarios = fixture()
    refund = data["orders"][ORDER_IDS["refund"]]
    approval = data["orders"][ORDER_IDS["approval"]]
    ownership = data["orders"][ORDER_IDS["ownership"]]
    assert refund["customer_id"] == "customer-1" and refund["total_amount"] == "129.90"
    assert approval["total_amount"] == "800.00"
    assert ownership["customer_id"] == "customer-1"
    assert all(order["status"] == "shipped" for order in (refund, approval, ownership))
    assert data["refunds"] == {}
    assert {item["id"] for item in scenarios} == {"policy", "composite", "ownership"}
    composite = next(item for item in scenarios if item["id"] == "composite")
    assert ORDER_IDS["refund"] in composite["message"]
    assert ORDER_IDS["approval"] in composite["message"]


def test_composite_demo_refund_allows_and_approval_waits():
    data, _ = fixture()
    _, service, backend = isolated_business(data, NOW)
    allowed = service.request_refund(
        order_id=ORDER_IDS["refund"], user_id="customer-1",
        request_id="h53-refund", amount="100.00", principal=customer("customer-1"))
    assert allowed.status is ActionStatus.COMPLETED
    assert len(backend.calls) == 1

    approval_data, _ = fixture()
    _, approval_service, approval_backend = isolated_business(approval_data, NOW)
    waiting = approval_service.request_refund(
        order_id=ORDER_IDS["approval"], user_id="customer-1",
        request_id="h53-approval", amount="800.00", principal=customer("customer-1"))
    assert waiting.status is ActionStatus.AWAITING_APPROVAL
    assert approval_backend.calls == []


def test_ownership_demo_cannot_execute_customer_one_order():
    data, _ = fixture()
    _, service, backend = isolated_business(data, NOW)
    result = service.request_cancel(
        order_id=ORDER_IDS["ownership"], user_id="customer-2",
        request_id="h53-ownership", principal=customer("customer-2"))
    assert result.status is not ActionStatus.COMPLETED
    assert backend.calls == []


def test_prepare_rejects_naive_time():
    with pytest.raises(ValueError):
        prepare(datetime(2026, 10, 2))


def test_demo_credentials_are_ephemeral_and_well_formed():
    tokens, identities = credentials()
    assert set(tokens) == {"customer-1", "customer-2", "reviewer", "admin"}
    assert all(len(token) >= 32 for token in tokens.values())
    assert len(set(tokens.values())) == 4
    assert identities[tokens["customer-1"]]["customer_id"] == "customer-1"
    assert identities[tokens["customer-2"]]["customer_id"] == "customer-2"
    assert identities[tokens["reviewer"]]["review_customers"] == ["customer-1"]
    assert identities[tokens["admin"]]["roles"] == ["admin"]
    bash = "\n".join(export_lines(tokens, identities, "bash"))
    powershell = "\n".join(export_lines(tokens, identities, "powershell"))
    assert bash.count("export ") == 5
    assert powershell.count("$env:") == 5
    assert tokens["reviewer"] in bash and tokens["reviewer"] in powershell


def test_preflight_fixture_check(tmp_path):
    data, _ = fixture()
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert fixture_errors(path) == []
    assert fixture_errors(path.with_name("missing.json"))
    broken = dict(data)
    broken["orders"] = {}
    path.write_text(json.dumps(broken), encoding="utf-8")
    assert any("ORD-DEMO-REFUND" in error for error in fixture_errors(path))


def test_preflight_auth_env(monkeypatch):
    monkeypatch.setenv("CARTCARE_AUTH_MODE", "demo")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("CARTCARE_DEMO_CREDENTIALS", "{}")
    assert auth_env_errors() == []
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    assert any("API_HOST" in error for error in auth_env_errors())
    monkeypatch.delenv("CARTCARE_DEMO_CREDENTIALS")
    assert any("CARTCARE_DEMO_CREDENTIALS" in error for error in auth_env_errors())
