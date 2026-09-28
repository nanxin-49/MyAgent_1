"""Small deterministic action store for the demo backend."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from .models import PendingAction


class ActionStore(Protocol):
    def get(self, action_id: str) -> PendingAction | None: ...

    def find_by_idempotency(self, key: str) -> PendingAction | None: ...

    def save(self, action: PendingAction) -> PendingAction: ...


class InMemoryActionStore:
    """Test/demo persistence; replaceable by a transactional repository later."""

    backend_name = "mock-action-store"

    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}
        self._idempotency: dict[str, str] = {}
        self.lock = RLock()

    def get(self, action_id: str) -> PendingAction | None:
        return self._actions.get(action_id)

    def find_by_idempotency(self, key: str) -> PendingAction | None:
        action_id = self._idempotency.get(key)
        return self._actions.get(action_id) if action_id else None

    def save(self, action: PendingAction) -> PendingAction:
        self._actions[action.action_id] = action
        self._idempotency[action.idempotency_key] = action.action_id
        return action


__all__ = ["ActionStore", "InMemoryActionStore"]
