"""Environment-variable compatibility for the CartCare naming migration."""
from __future__ import annotations

import os


def compat_env(primary: str, legacy: str | None = None,
               default: str | None = None) -> str | None:
    """Read the CartCare name first, then the legacy EchoMind fallback."""
    value = os.getenv(primary)
    if value is None and legacy:
        value = os.getenv(legacy)
    return default if value is None else value


def compat_env_int(primary: str, legacy: str | None = None,
                   default: int = 0) -> int:
    raw = compat_env(primary, legacy)
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def compat_env_float(primary: str, legacy: str | None = None,
                     default: float = 0.0) -> float:
    raw = compat_env(primary, legacy)
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


__all__ = ["compat_env", "compat_env_int", "compat_env_float"]
