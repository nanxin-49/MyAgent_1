"""Explicit test/demo backend backed by JSON data in memory.

API startup wires this simulated backend to the read tools and ActionService.
Readers and writers explicitly share one in-process state, not a payment system.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Mapping

from .errors import BackendDependencyError
from .interfaces import RawRecord


class InMemoryBusinessState:
    """Shared demo tables and a lock for command commits and read snapshots."""

    TABLES = ("products", "orders", "inventory", "shipments", "refunds")

    def __init__(self, data: Mapping[str, Any]) -> None:
        self.data = {table: dict(data.get(table, {})) for table in self.TABLES}
        self.lock = RLock()


class InMemoryBusinessBackend:
    """Read-only in-memory backend loaded from an explicitly supplied fixture."""

    backend_name = "mock-fixture"
    _TABLES = InMemoryBusinessState.TABLES

    def __init__(
        self,
        data: Mapping[str, Any] | InMemoryBusinessState,
        *,
        fail_operations: Iterable[str] = (),
    ) -> None:
        self.state = data if isinstance(data, InMemoryBusinessState) else InMemoryBusinessState(data)
        self._data = self.state.data
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
        with self.state.lock:
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
        with self.state.lock:
            matches = [record for record in self._data["refunds"].values()
                       if isinstance(record, Mapping) and record.get("order_id") == order_id]
            if matches:
                # Preserve history by ID; the order view returns the latest update.
                _, record = max(enumerate(matches),
                    key=lambda item: (self._refund_updated_at(item[1]), item[0]))
                return dict(record)
        return None

    @staticmethod
    def _refund_updated_at(record: Mapping[str, Any]) -> datetime:
        value = record.get("updated_at")
        try:
            stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
            return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
        except (ValueError, TypeError):
            # Return malformed records for Provider validation; never hide them.
            return datetime.max.replace(tzinfo=timezone.utc)


__all__ = ["InMemoryBusinessBackend", "InMemoryBusinessState"]
