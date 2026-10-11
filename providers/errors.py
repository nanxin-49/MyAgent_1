"""Typed errors shared by business fact providers and their backends."""

from __future__ import annotations

from typing import Any, Dict, Optional


class ProviderError(Exception):
    """Base error with a stable machine-readable code."""

    code = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Public projection: never serialize diagnostic messages or record details.

        Internal typed codes remain available to deterministic business logic.
        Read-tool consumers cannot distinguish a missing resource from a foreign one.
        """
        messages = {
            "invalid_input": "查询参数无效",
            "not_found": "未找到可访问的业务记录",
            "invalid_data": "业务数据暂不可用",
            "dependency_failure": "业务查询暂不可用",
            "provider_error": "业务查询失败",
        }
        code = "not_found" if self.code == "unauthorized" else self.code
        if code not in messages:
            code = "provider_error"
        return {
            "code": code,
            "message": messages[code],
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": {},
        }


class InvalidProviderInputError(ProviderError):
    code = "invalid_input"


class NotFoundError(ProviderError):
    code = "not_found"


class UnauthorizedError(ProviderError):
    code = "unauthorized"


class ProviderDependencyError(ProviderError):
    code = "dependency_failure"


class ProviderDataError(ProviderError):
    code = "invalid_data"


class BackendDependencyError(Exception):
    """Internal backend failure that providers translate to a public error."""


__all__ = [
    "BackendDependencyError",
    "InvalidProviderInputError",
    "NotFoundError",
    "ProviderDataError",
    "ProviderDependencyError",
    "ProviderError",
    "UnauthorizedError",
]
