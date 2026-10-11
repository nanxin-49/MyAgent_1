"""N02 authentication and authorization regressions (isolated dependencies)."""
import pytest
from fastapi.testclient import TestClient

from api import main
from tests.test_action_service import make_service
from tests.auth_helpers import customer
from core.auth import Principal, get_auth_adapter, DemoAuthAdapter
from agents.support_agent import SupportRuntime
from agents.agent_orchestrator import Request as AgentRequest
from agents.tools import build_business_tools, build_action_tools
from tests.test_support_production import EmptyMemory
from tests.test_topology_comparison import FakeClient


@pytest.fixture
def verified_api(monkeypatch):
    identities = {
        "customer": customer(), "other": customer("customer-2"),
        "reviewer": Principal("review-subject", None, frozenset({"reviewer"}), frozenset({"customer-1"})),
        "outsider": Principal("review-other", None, frozenset({"reviewer"}), frozenset({"customer-2"})),
        "self-reviewer": Principal("dual-role", "customer-1", frozenset({"customer", "reviewer"}), frozenset({"customer-1"})),
        "same-subject": Principal("test-subject:customer-1", None, frozenset({"reviewer"}), frozenset({"customer-1"})),
        "admin": Principal("admin-subject", None, frozenset({"admin"})),
    }
    class FixedAdapter:
        def verify(self, request):
            return identities.get(request.headers.get("authorization", "").removeprefix("Bearer "))
    monkeypatch.setitem(main.app.dependency_overrides, get_auth_adapter, lambda: FixedAdapter())
    return TestClient(main.app)


@pytest.mark.parametrize("claim", ["customer-2", "anonymous"])
def test_n02_verified_identity_rejects_body_spoof_before_memory(verified_api, monkeypatch, claim):
    memory = EmptyMemory()
    monkeypatch.setattr(main, "_memory", memory)
    response = verified_api.post("/chat", headers={"Authorization": "Bearer customer", "X-User-Id": claim},
                                json={"message": "订单", "user_id": claim, "roles": ["admin"]})
    assert response.status_code == 403
    assert memory.writes == []


def test_n02_chat_uses_verified_customer_and_tools(verified_api, monkeypatch):
    service, _ = make_service()
    runtime = SupportRuntime("fake", "fake", client=FakeClient("get_order", {"order_id": "ORD-1001"}))
    runtime.set_shared_tools(build_business_tools(service._business_backend))
    memory = EmptyMemory()
    monkeypatch.setattr(main, "_orchestrator", runtime)
    monkeypatch.setattr(main, "_memory", memory)
    response = verified_api.post("/chat", headers={"Authorization": "Bearer customer"}, json={"message": "订单"})
    assert response.status_code == 200
    assert all(args[0] == "customer-1" for args in memory.writes)
    trace = runtime.get_tool_trace(response.json()["request_id"])
    assert trace["tool_calls"][0]["success"]


@pytest.mark.parametrize("credential", ["customer", "outsider", "self-reviewer", "same-subject", "admin"])
def test_n02_unauthorized_review_preserves_state(verified_api, monkeypatch, credential):
    service, backend = make_service(total="800")
    pending = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n02-pending", amount="600", principal=customer())
    monkeypatch.setattr(main, "_action_service", service)
    result = verified_api.post(f"/actions/{pending.action_id}/approve",
        headers={"Authorization": "Bearer " + credential, "X-Roles": "reviewer"},
        json={"user_id": "customer-1", "roles": ["reviewer"]})
    assert result.status_code == 403
    assert pending.action.status.value == "awaiting_approval"
    assert pending.action.reviewed_by is None and backend.calls == []


def test_n02_independent_reviewer_is_audited_and_idempotent(verified_api, monkeypatch):
    service, backend = make_service(total="800")
    pending = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n02-pending", amount="600", principal=customer())
    monkeypatch.setattr(main, "_action_service", service)
    for _ in range(2):
        result = verified_api.post(f"/actions/{pending.action_id}/approve",
            headers={"Authorization": "Bearer reviewer"}, json={})
        assert result.status_code == 200
        assert result.json()["action"]["user_id"] == "customer-1"
        assert result.json()["action"]["reviewed_by"] == "review-subject"
        assert result.json()["action"]["requested_by"] == "test-subject:customer-1"
        assert result.json()["status"] == "completed"
    assert len(backend.calls) == 1


def test_n02_service_and_tool_cannot_bypass_http_gate():
    service, backend = make_service(total="800")
    pending = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n02-pending", amount="600", principal=customer())
    assert service.approve(action_id=pending.action_id, user_id="customer-1", request_id="raw").error_code == "unauthenticated"
    assert service.approve(action_id=pending.action_id, user_id="customer-1", request_id="customer", principal=customer()).error_code == "forbidden"
    req = AgentRequest("退款", "customer-1", "n02-raw")
    args = {"order_id": "ORD-1001"}
    assert build_business_tools(service._business_backend)["get_order"].handler(req, args)["error"]["code"] == "unauthenticated"
    assert build_action_tools(service)["request_refund"].handler(req, args)["error_code"] == "unauthenticated"
    req.principal = customer("customer-2")
    assert build_business_tools(service._business_backend)["get_order"].handler(req, args)["error"]["code"] == "forbidden"
    assert build_action_tools(service)["request_refund"].handler(req, args)["error_code"] == "forbidden"
    assert pending.action.status.value == "awaiting_approval" and backend.calls == []


def test_n02_cross_customer_action_query_is_not_found(verified_api, monkeypatch):
    service, _ = make_service(total="800")
    action = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n02-pending", amount="600", principal=customer())
    monkeypatch.setattr(main, "_action_service", service)
    headers = {"Authorization": "Bearer other"}
    assert verified_api.get(f"/actions/{action.action_id}", headers=headers).status_code == 404
    assert verified_api.get(f"/actions/{action.action_id}?user_id=customer-1", headers=headers).status_code == 403
    assert verified_api.post(f"/actions/{action.action_id}/resume", headers=headers, json={}).status_code == 404


@pytest.mark.parametrize("path", ["/trace/tools", "/trace/tool/x", "/skills/reload", "/knowledge/add", "/knowledge/upload", "/eval/run"])
def test_n02_customer_cannot_use_admin_routes(verified_api, path):
    method = "GET" if path.startswith("/trace") else "POST"
    response = verified_api.request(method, path, json={}, headers={"Authorization": "Bearer customer"})
    assert response.status_code == 403


def test_n02_admin_can_read_trace_and_reload_only_with_role(verified_api, monkeypatch):
    class Skills:
        calls = 0
        def reload(self): self.calls += 1
        def summary(self): return {"loaded": self.calls}
    skills = Skills()
    runtime = SupportRuntime("fake", "fake", client=FakeClient("unused", {}))
    monkeypatch.setattr(main, "_skill_manager", skills)
    monkeypatch.setattr(main, "_orchestrator", runtime)
    headers = {"Authorization": "Bearer admin"}
    assert verified_api.get("/trace/tools", headers=headers).status_code == 200
    assert verified_api.post("/skills/reload", headers=headers).json() == {"loaded": 1}


@pytest.mark.parametrize("mode,env,bind,remote,expected", [
    ("demo", "development", "127.0.0.1", "127.0.0.1", 200),
    ("demo", "production", "127.0.0.1", "127.0.0.1", 401),
    ("demo", "development", "0.0.0.0", "127.0.0.1", 401),
    ("demo", "development", "127.0.0.1", "203.0.113.2", 401),
    ("disabled", "development", "127.0.0.1", "127.0.0.1", 401),
])
def test_n02_demo_auth_is_explicit_and_loopback_only(monkeypatch, mode, env, bind, remote, expected):
    import json
    token = "local-test-credential-32-chars-minimum"
    monkeypatch.setenv("CARTCARE_AUTH_MODE", mode)
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.setenv("API_HOST", bind)
    monkeypatch.setenv("CARTCARE_DEMO_CREDENTIALS", json.dumps({token: {
        "subject_id": "local-admin", "roles": ["admin"]}}))
    runtime = SupportRuntime("fake", "fake", client=FakeClient("unused", {}))
    monkeypatch.setattr(main, "_orchestrator", runtime)
    import asyncio
    import httpx
    async def check():
        transport = httpx.ASGITransport(app=main.app, client=(remote, 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as http:
            assert (await http.get("/trace/tools", headers={"Authorization": "Bearer " + token})).status_code == expected
            assert (await http.get("/trace/tools", headers={"Authorization": "Bearer invalid"})).status_code == 401
    asyncio.run(check())


@pytest.mark.parametrize("method,path,payload", [
    ("POST", "/chat", {"message": "订单", "user_id": "customer-1"}),
    ("GET", "/actions/unknown?user_id=customer-1", None),
    ("GET", "/trace/tools", None),
    ("GET", "/trace/tool/unknown", None),
    ("POST", "/knowledge/add", {"documents": []}),
    ("POST", "/knowledge/upload", None),
    ("POST", "/skills/reload", None),
    ("GET", "/skills", None),
    ("POST", "/eval/run", {}),
    ("GET", "/knowledge/stats", None),
    ("GET", "/monitor", None),
    ("GET", "/metrics", None),
    ("POST", "/search?query=demo", None),
])
def test_n02_anonymous_protected_routes_return_401(method, path, payload):
    http = TestClient(main.app)
    try:
        response = http.request(method, path, json=payload,
            headers={"X-User-Id": "customer-1", "X-Roles": "admin,reviewer"})
        assert response.status_code == 401
    finally:
        http.close()


def test_n02_untrusted_approval_cannot_change_pending_action(monkeypatch):
    service, backend = make_service(total="800")
    pending = service.request_refund(order_id="ORD-1001", user_id="customer-1",
        request_id="n02-pending", amount="600", principal=customer())
    monkeypatch.setattr(main, "_action_service", service)
    http = TestClient(main.app)
    try:
        response = http.post(f"/actions/{pending.action_id}/approve",
            json={"user_id": "customer-1", "roles": ["reviewer"]})
        assert response.status_code == 401
        assert pending.action.status.value == "awaiting_approval"
        assert backend.calls == []
    finally:
        http.close()
