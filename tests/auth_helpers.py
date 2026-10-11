"""Explicit trusted test identities. Never installed by production code."""
from core.auth import Principal, get_principal
from fastapi import HTTPException, Request


def customer(user_id="customer-1"):
    return Principal("test-subject:" + user_id, user_id, frozenset({"customer"}))


def reviewer(user_id="customer-1"):
    return Principal("test-reviewer", None, frozenset({"reviewer"}), frozenset({user_id}))


def install_http_auth(monkeypatch, app):
    identities = {
        "test-customer-1": Principal("test-customer", "customer-1", frozenset({"customer", "admin"})),
        "test-customer-2": Principal("test-other", "customer-2", frozenset({"customer", "admin"})),
        "test-u": customer("u"),
        "test-reviewer": reviewer(),
    }
    def verified(request: Request):
        principal = identities.get(request.headers.get("authorization", "").removeprefix("Bearer "))
        if principal is None:
            raise HTTPException(401, "test authentication required")
        return principal
    monkeypatch.setitem(app.dependency_overrides, get_principal, verified)


customer.__test__ = reviewer.__test__ = False
