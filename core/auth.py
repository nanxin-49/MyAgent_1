"""Server-owned identity; deny by default, explicitly enabled loopback demo only."""
from dataclasses import dataclass
import hmac
import json
import os
from typing import Protocol

from fastapi import Depends, HTTPException, Request


@dataclass(frozen=True)
class Principal:
    subject_id: str
    customer_id: str | None = None
    roles: frozenset[str] = frozenset()
    review_customers: frozenset[str] = frozenset()


class AuthAdapter(Protocol):
    def verify(self, request: Request) -> Principal | None: ...


class DenyAuthAdapter:
    def verify(self, request):
        return None


class DemoAuthAdapter:
    """Not production authentication. Tokens are configured on the server, never seeded."""
    def verify(self, request):
        if (os.getenv("CARTCARE_AUTH_MODE") != "demo"
            or os.getenv("APP_ENV") != "development"
            or os.getenv("API_HOST") not in {"127.0.0.1", "::1"}
            or request.client is None
            or request.client.host not in {"127.0.0.1", "::1"}
            or request.url.hostname not in {"127.0.0.1", "localhost", "::1"}):
            return None
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not supplied:
            return None
        try:
            identities = json.loads(os.getenv("CARTCARE_DEMO_CREDENTIALS", "{}"))
            if not isinstance(identities, dict):
                return None
            for credential, identity in identities.items():
                if len(credential) < 32 or not hmac.compare_digest(credential, supplied):
                    continue
                subject = identity["subject_id"]
                customer = identity.get("customer_id")
                roles = frozenset(identity["roles"])
                scope = frozenset(identity.get("review_customers", []))
                if (not isinstance(subject, str) or not subject
                    or not roles <= {"customer", "reviewer", "admin"}
                    or (customer is not None and (not isinstance(customer, str) or not customer))
                    or ("customer" in roles and customer is None)
                    or not all(isinstance(value, str) and value for value in scope)):
                    return None
                return Principal(subject, customer, roles, scope)
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
        return None


def get_auth_adapter(request: Request) -> AuthAdapter:
    # A real verifier must be installed explicitly; no anonymous/demo fallback.
    configured = getattr(request.app.state, "auth_adapter", None)
    if configured is not None:
        return configured
    return DemoAuthAdapter() if os.getenv("CARTCARE_AUTH_MODE") == "demo" else DenyAuthAdapter()


def get_principal(request: Request, adapter: AuthAdapter = Depends(get_auth_adapter)) -> Principal:
    try:
        principal = adapter.verify(request)
    except Exception:
        raise HTTPException(401, "认证验证失败", headers={"WWW-Authenticate": "Bearer"}) from None
    if not isinstance(principal, Principal) or not principal.subject_id:
        raise HTTPException(401, "需要有效认证", headers={"WWW-Authenticate": "Bearer"})
    return principal


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if "admin" not in principal.roles:
        raise HTTPException(403, "需要管理权限")
    return principal


def require_reviewer(principal: Principal = Depends(get_principal)) -> Principal:
    if "reviewer" not in principal.roles:
        raise HTTPException(403, "需要审核权限")
    return principal


def customer_identity(principal: Principal, claimed: str | None = None) -> str:
    if not isinstance(principal, Principal):
        raise HTTPException(401, "需要有效认证")
    if "customer" not in principal.roles or not principal.customer_id:
        raise HTTPException(403, "需要客户权限")
    if claimed is not None and claimed != principal.customer_id:
        raise HTTPException(403, "身份声明与认证主体不一致")
    return principal.customer_id
