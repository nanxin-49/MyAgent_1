"""Explicit test/demo backend backed by JSON data in memory.

This module is not wired into the API.  It provides deterministic records for
Provider tests and can later be replaced by a SQLite or external API adapter
implementing the same ``BusinessBackend`` protocol.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .errors import BackendDependencyError
from .interfaces import RawRecord


class InMemoryBusinessBackend:
    """Read-only in-memory backend loaded from an explicitly supplied fixture."""

    backend_name = "mock-fixture"
    _TABLES = ("products", "orders", "inventory", "shipments", "refunds")

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        fail_operations: Iterable[str] = (),
    ) -> None:
        self._data = {
            table: dict(data.get(table, {}))
            for table in self._TABLES
        }
        self._fail_operations = set(fail_operations)

    @classmethod
    def from_fixture(cls, path: str | Path) -> "InMemoryBusinessBackend":
        fixture_path = Path(path)
        with fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("business fixture must contain a JSON object")
        return cls(payload)

    def _get(self, table: str, key: str) -> RawRecord | None:
        operation = f"get_{table.rstrip('s')}"
        if operation in self._fail_operations:
            raise BackendDependencyError(f"mock backend failure: {operation}")
        record = self._data[table].get(key)
        return dict(record) if isinstance(record, Mapping) else None

    def get_product(self, product_id: str) -> RawRecord | None:
        return self._get("products", product_id)

    def get_order(self, order_id: str) -> RawRecord | None:
        return self._get("orders", order_id)

    def get_inventory(self, product_id: str) -> RawRecord | None:
        return self._get("inventory", product_id)

    def get_shipment(self, order_id: str) -> RawRecord | None:
        return self._get("shipments", order_id)

    def get_refund(self, refund_id: str) -> RawRecord | None:
        return self._get("refunds", refund_id)

    def get_refund_for_order(self, order_id: str) -> RawRecord | None:
        operation = "get_refund_for_order"
        if operation in self._fail_operations:
            raise BackendDependencyError(f"mock backend failure: {operation}")
        for record in self._data["refunds"].values():
            if isinstance(record, Mapping) and record.get("order_id") == order_id:
                return dict(record)
        return None


__all__ = ["InMemoryBusinessBackend"]
