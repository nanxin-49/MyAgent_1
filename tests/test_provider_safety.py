"""N03: synthetic malformed data must stay out of tools, models and HTTP."""
import json
import traceback
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import main
from agents.support_agent import SupportRuntime
from agents.tools import build_business_tools
from providers import LogisticsProvider, OrderProvider, ProviderError, RefundProvider
from providers.mock_backend import InMemoryBusinessBackend
from tests.test_business_tools import FIXTURE, make_request
from tests.test_support_production import EmptyMemory


MARKER = "N03-SYNTHETIC-PRIVATE-DATA"


def malformed_backend():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["orders"]["ORD-1001"].pop("status")
    data["orders"]["ORD-1001"]["private_note"] = MARKER
    return InMemoryBusinessBackend(data)


@pytest.mark.parametrize("customer", ["customer-1", "customer-2"])
def test_n03_provider_error_has_no_raw_input(customer, caplog):
    with pytest.raises(ProviderError) as caught:
        OrderProvider(malformed_backend()).get_order("ORD-1001", customer_id=customer)
    error = caught.value
    assert MARKER not in json.dumps(error.details)
    assert MARKER not in json.dumps(error.to_dict())
    assert MARKER not in str(error) and MARKER not in caplog.text
    assert MARKER not in "".join(traceback.format_exception(error))
    if customer == "customer-1":
        assert error.code == "invalid_data"
        assert error.details["validation_error_count"] > 0
    else:
        assert error.to_dict()["code"] == "not_found"


def test_n03_unknown_or_foreign_order_has_same_public_error():
    tool = build_business_tools(malformed_backend())["get_order"]
    errors = [tool.handler(make_request("customer-2"), {"order_id": order})["error"]
              for order in ("ORD-1001", "ORD-MISSING")]
    assert errors[0]["code"] == errors[1]["code"] == "not_found"
    assert errors[0]["message"] == errors[1]["message"]
    assert errors[0]["details"] == errors[1]["details"] == {}


def test_n03_public_error_serialization_does_not_trust_message_or_details():
    error = ProviderError(MARKER, details={"raw": MARKER})
    assert MARKER not in json.dumps(error.to_dict())


@pytest.mark.parametrize("kind", ["order", "shipment", "refund"])
@pytest.mark.parametrize("owner", [None, "customer-2"])
def test_n03_owned_providers_fail_closed_before_validation(kind, owner):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    table, record_id, provider_type, method = {
        "order": ("orders", "ORD-1001", OrderProvider, "get_order"),
        "shipment": ("shipments", "ORD-1001", LogisticsProvider, "get_shipment"),
        "refund": ("refunds", "REF-1001", RefundProvider, "get_refund"),
    }[kind]
    record = data[table][record_id]
    record["private_note"] = MARKER
    if owner is None:
        record.pop("customer_id")
    else:
        record["customer_id"] = owner
    provider = provider_type(InMemoryBusinessBackend(data))
    with pytest.raises(ProviderError) as caught:
        getattr(provider, method)(record_id, customer_id="customer-1")
    assert caught.value.code == "unauthorized"
    assert caught.value.to_dict()["code"] == "not_found"
    assert caught.value.details == {}
    assert MARKER not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("customer", ["customer-1", "customer-2"])
def test_n03_http_trace_and_model_tool_result_are_safe(monkeypatch, customer):
    class Client:
        calls = []
        @property
        def messages(self):
            return self
        async def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                block = SimpleNamespace(type="tool_use", id="n03-read", name="get_order",
                                        input={"order_id": "ORD-1001"})
            else:
                # Echo the actual tool result to test HTTP without model behavior assumptions.
                block = SimpleNamespace(type="text", text=kwargs["messages"][-1]["content"][0]["content"])
            return SimpleNamespace(content=[block])
    client = Client()
    runtime = SupportRuntime("fake", "fake", client=client)
    tools = build_business_tools(malformed_backend())
    runtime.set_shared_tools(tools)
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_memory", EmptyMemory())
    http = TestClient(main.app)  # No lifespan: only injected Fake SDK/Memory/backend.
    try:
        response = http.post("/chat", json={"message": "查询订单", "user_id": customer})
        assert response.status_code == 200
        body = response.json()
        trace_response = http.get(f"/trace/tool/{body['request_id']}")
        assert trace_response.status_code == 200
        assert len(client.calls) == 2
        tool_payload = json.loads(client.calls[1]["messages"][-1]["content"][0]["content"])
        expected = "invalid_data" if customer == "customer-1" else "not_found"
        assert tool_payload["error"]["code"] == expected
        direct = tools["get_order"].handler(make_request(customer), {"order_id": "ORD-1001"})
        for visible in (direct, tool_payload, body, trace_response.json()):
            assert MARKER not in json.dumps(visible)
            assert "private_note" not in json.dumps(visible)
        assert tool_payload["error"]["details"] == {}
    finally:
        http.close()
