"""A02: Fake SDK through the authenticated FastAPI /chat path."""
import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from api import main
from agents.support_agent import SupportRuntime
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient

pytestmark = pytest.mark.usefixtures("authenticated_http")


def setup(monkeypatch, text="已成功转接人工客服。", tool=None, args=None):
    sdk = FakeClient(tool, args or {}, text=text)
    if not tool:
        sdk.responses = [NS(content=[NS(type="text", text=text)])]
    runtime = SupportRuntime("test", "test", client=sdk)
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_memory", EmptyMemory())
    monkeypatch.setattr(main, "_action_service", None)
    return TestClient(main.app, headers={"Authorization": "Bearer test-customer-1"}), runtime, sdk


def test_explicit_request_creates_queryable_receipt_without_model_tool(monkeypatch):
    http, runtime, _ = setup(monkeypatch)
    body = http.post("/chat", json={"message": "我想转人工客服。"}).json()
    assert body["handoff"]["status"] == "created"
    handoff = body["handoff"]
    assert handoff["handoff_required"] and handoff["handoff_requested"] and handoff["handoff_created"]
    assert handoff["handoff_id"] in body["response"]
    assert http.get('/handoffs/' + handoff["handoff_id"]).json()["status"] == "created"
    assert runtime.get_tool_trace(body["request_id"])["handoff"] == handoff


@pytest.mark.parametrize("message,text", [
    ("我不需要人工客服，请直接查询物流。", "您不需要人工客服，请提供订单号。"),
    ("帮我预订机票", "电商客服无法处理订票。"),
    ("退货政策是什么", "请提供商品信息。"),
    ("查询订单", "请提供订单号。"),
    ("常规退款咨询", "请提供订单信息。"),
])
def test_no_handoff_from_response_keywords(monkeypatch, message, text):
    http, runtime, _ = setup(monkeypatch, text)
    body = http.post("/chat", json={"message": message}).json()
    assert body["escalated"] is False
    assert body["handoff"]["status"] == "not_required"
    assert not body["handoff"]["handoff_requested"]


def test_model_words_without_tool_cannot_claim_handoff(monkeypatch):
    http, runtime, _ = setup(monkeypatch)
    body = http.post("/chat", json={"message": "请查询订单"}).json()
    assert "已成功转接" not in body["response"]
    assert body["response"] == "本次未创建人工交接记录。"
    assert not body["handoff"]["handoff_created"] and not runtime.handoff_service._records


def test_service_failure_has_no_id_or_false_success(monkeypatch):
    http, runtime, _ = setup(monkeypatch)
    def fail(*args):
        raise RuntimeError("SECRET-CREDENTIAL")
    monkeypatch.setattr(runtime.handoff_service, "_create_record", fail)
    body = http.post("/chat", json={"message": "我想转人工客服。"}).json()
    h = body["handoff"]
    assert h["status"] == "failed" and h["handoff_failed"] and h["handoff_requested"]
    assert h["handoff_id"] is None and h["error_code"] == "handoff_service_unavailable"
    assert not runtime.handoff_service._records and not body["escalated"]
    trace = runtime.get_tool_trace(body["request_id"])
    assert trace["tool_calls"][0]["error_code"] == h["error_code"]
    assert "SECRET-CREDENTIAL" not in json.dumps(body) + json.dumps(trace)
    assert "未完成转接" in body["response"]


def test_client_retry_scope_conflict_and_ownership(monkeypatch):
    http, runtime, _ = setup(monkeypatch)
    request = {"message": "我想转人工客服。", "conv_id": "session", "handoff_key": "logical-turn-1"}
    first = http.post("/chat", json=request).json()["handoff"]
    second = http.post("/chat", json=request).json()["handoff"]
    assert first["handoff_id"] == second["handoff_id"] and second["reused"]
    conflict = http.post("/chat", json={**request, "message": "请联系人工客服"}).json()["handoff"]
    assert conflict["error_code"] == "handoff_idempotency_conflict" and conflict["handoff_id"] is None
    other = http.post("/chat", json=request, headers={"Authorization": "Bearer test-customer-2"}).json()["handoff"]
    assert other["handoff_id"] != first["handoff_id"]
    assert http.get('/handoffs/' + first["handoff_id"], headers={"Authorization": "Bearer test-customer-2"}).status_code == 404
    assert http.get('/handoffs/' + first["handoff_id"], headers={"Authorization": ""}).status_code == 401
    assert http.get('/handoffs/' + first["handoff_id"], headers={"Authorization": "Bearer test-reviewer"}).status_code == 403
    third = http.post("/chat", json={**request, "handoff_key": "logical-turn-2"}).json()["handoff"]
    assert third["handoff_id"] != first["handoff_id"]
    assert len(runtime.handoff_service._records) == 3


@pytest.mark.parametrize("later", ["failure", "retry", "denied"])
def test_agent_complaint_created_receipt_survives_later_model_steps(monkeypatch, later):
    http, runtime, sdk = setup(monkeypatch, tool="request_handoff", args={"reason_code": "complex_complaint"})
    if later == "failure":
        sdk.responses = sdk.responses[:1]
    else:
        reason = "complex_complaint" if later == "retry" else "unsupported"
        sdk.responses.insert(1, NS(content=[NS(type="tool_use", id="retry", name="request_handoff", input={"reason_code": reason})]))
    body = http.post("/chat", json={"message": "我要投诉订单退款争议，多次没有解决。"}).json()
    assert body["handoff"]["handoff_created"] and body["escalated"]
    assert body["handoff"]["handoff_id"] in body["response"]
    assert len(runtime.handoff_service._records) == 1
    assert runtime.get_tool_trace(body["request_id"])["handoff"] == body["handoff"]
    assert sdk.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"
    if later == "denied":
        assert body["handoff"]["status"] == "created"
        assert runtime.get_tool_trace(body["request_id"])["tool_calls"][1]["handoff_result"]["error_code"] == "handoff_policy_rejected"


@pytest.mark.parametrize("message,reason", [
    ("我不需要人工客服，请直接查询物流。", "complex_complaint"),
    ("帮我预订机票", "unsupported"), ("请查询订单", "complex_complaint"),
    ("退款政策", "business_dependency_failure"),
])
def test_agent_cannot_create_outside_policy(monkeypatch, message, reason):
    http, runtime, _ = setup(monkeypatch, tool="request_handoff", args={"reason_code": reason})
    body = http.post("/chat", json={"message": message}).json()
    assert not body["handoff"]["handoff_created"] and not runtime.handoff_service._records
    assert "已成功转接" not in body["response"]


def test_created_receipt_survives_memory_write_failure(monkeypatch):
    from tests.test_action_memory_consistency import FaultMemory
    http, runtime, _ = setup(monkeypatch)
    monkeypatch.setattr(main, "_memory", FaultMemory("user"))
    response = http.post("/chat", json={"message": "我想转人工客服。"})
    assert response.status_code == 200
    assert response.json()["handoff"]["handoff_created"]
    assert response.json()["memory_write_status"] == "failed"


def test_concurrent_same_scope_and_minimal_safe_summary():
    from concurrent.futures import ThreadPoolExecutor
    from agents.agent_orchestrator import Request
    from core.handoff import HandoffService
    from tests.auth_helpers import customer
    service = HandoffService()
    req = Request("我想转人工客服。SECRET-CREDENTIAL", "customer-1", "session", principal=customer(), handoff_key="same")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: service.request(req, "explicit_request"), range(8)))
    assert len({r.handoff_id for r in results}) == len(service._records) == 1
    record = service.get(results[0].handoff_id, customer())
    assert record["owner"] == "customer-1" and "SECRET-CREDENTIAL" not in json.dumps(record)


@pytest.mark.parametrize("message", ["不想转人工", "不用转人工客服", "请不要联系人工客服", "人工客服是做什么的？"])
def test_conservative_gate_does_not_trigger_negation_or_question(monkeypatch, message):
    http, runtime, _ = setup(monkeypatch, "请提供订单号。")
    assert not http.post("/chat", json={"message": message}).json()["handoff"]["handoff_requested"]
    assert not runtime.handoff_service._records


def test_observed_business_failure_allows_agent_handoff(monkeypatch):
    from agents.tools import AgentToolSpec
    http, runtime, sdk = setup(monkeypatch, tool="get_shipment", args={"order_id": "demo-order"})
    runtime.set_shared_tools({"get_shipment": AgentToolSpec("get_shipment", "fake dependency", {
        "type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
        lambda req, args: {"success": False, "source": "business_provider", "error_code": "dependency_failure"})})
    sdk.responses.insert(1, NS(content=[NS(type="tool_use", id="h", name="request_handoff",
                                        input={"reason_code": "business_dependency_failure"})]))
    body = http.post("/chat", json={"message": "请查询我的订单物流"}).json()
    assert body["handoff"]["status"] == "created"
    assert body["handoff"]["reason_code"] == "business_dependency_failure"
    assert runtime.get_tool_trace(body["request_id"])["tool_calls"][0]["error_code"] == "dependency_failure"


def test_service_auth_scope_before_idempotency():
    from fastapi import HTTPException
    from agents.agent_orchestrator import Request
    from core.handoff import HandoffService
    from tests.auth_helpers import customer
    service = HandoffService()
    req = Request("我想转人工客服", "customer-1", "c", principal=customer(), handoff_key="k")
    service.request(req, "explicit_request")
    req.principal = customer("customer-2")
    with pytest.raises(HTTPException) as error:
        service.request(req, "explicit_request")
    assert error.value.status_code == 403 and len(service._records) == 1


def test_failure_replay_then_new_request_recovers(monkeypatch):
    http, runtime, _ = setup(monkeypatch)
    original = runtime.handoff_service._create_record
    def fail(*args):
        raise RuntimeError("outage")
    monkeypatch.setattr(runtime.handoff_service, "_create_record", fail)
    request = {"message": "我想转人工客服", "conv_id": "c", "handoff_key": "failed-turn"}
    first = http.post("/chat", json=request).json()["handoff"]
    monkeypatch.setattr(runtime.handoff_service, "_create_record", original)
    replay = http.post("/chat", json=request).json()["handoff"]
    assert first["status"] == replay["status"] == "failed" and replay["reused"]
    fresh = http.post("/chat", json={**request, "handoff_key": "fresh-turn"}).json()["handoff"]
    assert fresh["status"] == "created" and len(runtime.handoff_service._records) == 1


def test_structured_evaluator_rejects_fabricated_created_state(monkeypatch):
    from evaluation.run_handoff_eval import run
    from evaluation.handoff_eval import score
    report = run()
    assert report["passed"] == report["total"] == 7
    row = report["observations"][0]
    case = {"required": True, "status": "created"}
    assert not score(case, row["body"], row["trace"], None, 0)["passed"]
