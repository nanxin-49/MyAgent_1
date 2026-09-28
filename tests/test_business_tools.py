import asyncio
import json
from pathlib import Path

import pytest

from agents.agent_orchestrator import GeneralAgent, Request
from agents.tools import build_business_tools
from core.intent_recognizer import IntentCategory, UrgencyLevel
from providers.mock_backend import InMemoryBusinessBackend


FIXTURE = Path(__file__).parent / "fixtures" / "business_provider_data.json"


def make_request(user_id: str = "customer-1") -> Request:
    return Request(
        message="查询我的订单",
        user_id=user_id,
        conv_id="conv-tools",
        intent=IntentCategory.ORDER_STATUS,
        intent_group="order",
        urgency=UrgencyLevel.LOW,
    )


@pytest.fixture()
def tools():
    backend = InMemoryBusinessBackend.from_fixture(FIXTURE)
    return build_business_tools(backend)


def test_business_read_tools_return_provider_facts(tools):
    req = make_request()

    product = tools["get_product"].handler(req, {"product_id": "SKU-1001"})
    order = tools["get_order"].handler(req, {"order_id": "ORD-1001"})
    shipment = tools["get_shipment"].handler(req, {"order_id": "ORD-1001"})
    inventory = tools["check_inventory"].handler(req, {"product_id": "SKU-1001"})
    refund = tools["get_refund_status"].handler(req, {"order_id": "ORD-1001"})

    assert product["success"] is True
    assert product["data"]["product_id"] == "SKU-1001"
    assert order["data"]["status"] == "shipped"
    assert shipment["data"]["tracking_number"] == "TRACK-1001"
    assert inventory["data"]["available_quantity"] == 12
    assert refund["data"]["status"] == "requested"
    assert all(result["source"] == "business_provider" for result in (product, order, shipment, inventory, refund))


def test_order_ownership_is_checked_by_provider(tools):
    result = tools["get_order"].handler(make_request("customer-2"), {"order_id": "ORD-1001"})

    assert result["success"] is False
    assert result["error"]["code"] == "unauthorized"
    assert result["error"]["resource_id"] == "ORD-1001"


def test_not_found_is_a_stable_tool_error(tools):
    result = tools["get_product"].handler(make_request(), {"product_id": "SKU-MISSING"})

    assert result["success"] is False
    assert result["error"]["code"] == "not_found"
    assert result["data"] is None


def test_dependency_failure_is_a_stable_tool_error():
    backend = InMemoryBusinessBackend.from_fixture(FIXTURE)
    failing = InMemoryBusinessBackend(
        json.loads(FIXTURE.read_text(encoding="utf-8")),
        fail_operations={"get_order"},
    )
    tool = build_business_tools(failing)["get_order"]

    result = tool.handler(make_request(), {"order_id": "ORD-1001"})

    assert backend.backend_name == "mock-fixture"
    assert result["success"] is False
    assert result["error"]["code"] == "dependency_failure"


def test_invalid_provider_data_is_a_stable_tool_error():
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
    tool = build_business_tools(backend)["get_product"]

    result = tool.handler(make_request(), {"product_id": "SKU-BAD"})

    assert result["success"] is False
    assert result["error"]["code"] == "invalid_data"


def test_malformed_arguments_are_rejected_by_agent_schema(tools):
    spec = tools["get_order"]

    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(spec, {})
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(spec, {"order_id": 1001})
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(spec, {"order_id": ""})
    with pytest.raises(ValueError):
        GeneralAgent._validate_tool_input(spec, {"order_id": "ORD-1001", "customer_id": "customer-1"})


class _ToolUseBlock:
    type = "tool_use"
    id = "toolu_order_1"
    name = "get_order"
    input = {"order_id": "ORD-1001"}


class _TextBlock:
    type = "text"
    text = "订单 ORD-1001 当前已发货。"


class _RoundTripClient:
    def __init__(self):
        self.calls = []
        self.responses = [
            type("Response", (), {"content": [_ToolUseBlock()]})(),
            type("Response", (), {"content": [_TextBlock()]})(),
        ]

    class Messages:
        def __init__(self, owner):
            self.owner = owner

        async def create(self, **kwargs):
            self.owner.calls.append(kwargs)
            return self.owner.responses.pop(0)

    @property
    def messages(self):
        return self.Messages(self)


def test_agent_round_trip_contains_provider_result_in_final_llm_input(tools):
    client = _RoundTripClient()
    agent = GeneralAgent(client, "test-model")
    agent.set_shared_tools(tools)

    response = asyncio.run(agent.handle(make_request()))

    assert response.success is True
    assert response.tools_used == ["get_order"]
    assert response.tool_traces[0]["success"] is True
    second_messages = client.calls[1]["messages"]
    tool_content = second_messages[-1]["content"][0]["content"]
    provider_result = json.loads(tool_content)
    assert provider_result["data"]["order_id"] == "ORD-1001"
    assert provider_result["data"]["status"] == "shipped"
    assert response.content == "订单 ORD-1001 当前已发货。"
