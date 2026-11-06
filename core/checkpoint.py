"""Durable approval checkpoints; never stores prompts, model text, or raw Memory."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

TERMINAL_ACTION_STATUSES = {"completed", "rejected", "failed"}
PENDING_ACTION_STATUSES = {"pending", "awaiting_approval"}
EXECUTING_ACTION_STATUSES = {"approved", "executing"}


class CheckpointStatus(str, Enum):
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIAL_COMPLETED = "partial_completed"
    REJECTED = "rejected"
    FAILED = "failed"


class CheckpointAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    error_code: str | None = None


class ActionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    conv_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    actions: list[CheckpointAction] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    status: CheckpointStatus
    remaining_actions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    resumed_at: datetime | None = None


class CheckpointStore(Protocol):
    def save(self, checkpoint: ActionCheckpoint) -> ActionCheckpoint: ...

    def get(self, request_id: str) -> ActionCheckpoint | None: ...

    def find_by_action(self, action_id: str) -> ActionCheckpoint | None: ...

    def close(self) -> None: ...


class InMemoryCheckpointStore:
    """Test/evaluation store; production uses RedisCheckpointStore."""

    backend_name = "mock-checkpoint-store"

    def __init__(self) -> None:
        self._checkpoints: dict[str, ActionCheckpoint] = {}
        self._by_action: dict[str, str] = {}

    def save(self, checkpoint: ActionCheckpoint) -> ActionCheckpoint:
        self._checkpoints[checkpoint.request_id] = checkpoint
        for action in checkpoint.actions:
            self._by_action[action.action_id] = checkpoint.request_id
        return checkpoint

    def get(self, request_id: str) -> ActionCheckpoint | None:
        return self._checkpoints.get(request_id)

    def find_by_action(self, action_id: str) -> ActionCheckpoint | None:
        request_id = self._by_action.get(action_id)
        return self._checkpoints.get(request_id) if request_id else None

    def close(self) -> None:
        return None


def reconcile_checkpoint(
    checkpoint: ActionCheckpoint,
    observed: dict[str, tuple[str, str | None]],
) -> ActionCheckpoint:
    """Project live action statuses onto a checkpoint without writing the store."""
    actions: list[CheckpointAction] = []
    changed = False
    for action in checkpoint.actions:
        value = observed.get(action.action_id)
        if value is None:
            actions.append(action)
            continue
        status, error_code = value
        if action.status != status or action.error_code != error_code:
            changed = True
            action = action.model_copy(update={"status": status, "error_code": error_code})
        actions.append(action)
    if not changed:
        return checkpoint
    return checkpoint.model_copy(update={
        "actions": actions,
        "status": checkpoint_status(actions),
        "remaining_actions": [action.action_id for action in actions
                              if action.status not in TERMINAL_ACTION_STATUSES],
    })


def checkpoint_status(actions: list[CheckpointAction]) -> CheckpointStatus:
    statuses = {action.status for action in actions}
    if not statuses:
        return CheckpointStatus.FAILED
    if statuses & PENDING_ACTION_STATUSES:
        return CheckpointStatus.AWAITING_APPROVAL
    if statuses & EXECUTING_ACTION_STATUSES:
        return CheckpointStatus.EXECUTING
    if statuses <= {"completed"}:
        return CheckpointStatus.COMPLETED
    if "completed" in statuses:
        return CheckpointStatus.PARTIAL_COMPLETED
    if statuses <= {"rejected"}:
        return CheckpointStatus.REJECTED
    return CheckpointStatus.FAILED


class CheckpointService:
    """Create/update checkpoints from already-recorded action results."""

    def __init__(self, store: CheckpointStore | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._store = store or InMemoryCheckpointStore()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def record_result(self, result: Any, *, conv_id: str, user_id: str) -> ActionCheckpoint | None:
        actions: list[CheckpointAction] = []
        seen: set[str] = set()
        for trace in getattr(result, "tool_traces", []) or []:
            action = trace.get("action_result") if isinstance(trace, dict) else None
            if not isinstance(action, dict) or not action.get("status") or not action.get("action_id"):
                continue
            action_id = str(action["action_id"])
            if action_id in seen:
                continue
            seen.add(action_id)
            actions.append(CheckpointAction(
                action_id=action_id,
                tool_name=str(trace.get("tool_name") or "unknown"),
                status=str(action["status"]),
                error_code=action.get("error_code"),
            ))
        if not any(action.status in PENDING_ACTION_STATUSES for action in actions):
            return None
        now = self._clock()
        checkpoint = ActionCheckpoint(
            request_id=str(getattr(result, "request_id")),
            conv_id=conv_id,
            user_id=user_id,
            actions=actions,
            steps=list(getattr(result, "steps", []) or []),
            status=checkpoint_status(actions),
            remaining_actions=[action.action_id for action in actions
                               if action.status not in TERMINAL_ACTION_STATUSES],
            created_at=now,
            updated_at=now,
        )
        return self._store.save(checkpoint)

    def update_for_action(self, action_id: str, status: str,
                          error_code: str | None = None) -> ActionCheckpoint | None:
        checkpoint = self._store.find_by_action(action_id)
        if checkpoint is None:
            return None
        changed = False
        actions = []
        for action in checkpoint.actions:
            if action.action_id == action_id:
                changed = action.status != status or action.error_code != error_code
                action = action.model_copy(update={"status": status, "error_code": error_code})
            actions.append(action)
        if not changed:
            return checkpoint
        now = self._clock()
        updated = checkpoint.model_copy(update={
            "actions": actions,
            "status": checkpoint_status(actions),
            "remaining_actions": [action.action_id for action in actions
                                  if action.status not in TERMINAL_ACTION_STATUSES],
            "updated_at": now,
        })
        return self._store.save(updated)

    def get(self, request_id: str) -> ActionCheckpoint | None:
        return self._store.get(request_id)

    def mark_resumed(self, request_id: str) -> ActionCheckpoint | None:
        checkpoint = self._store.get(request_id)
        if checkpoint is None:
            return None
        now = self._clock()
        return self._store.save(checkpoint.model_copy(
            update={"resumed_at": checkpoint.resumed_at or now, "updated_at": now}))

    def close(self) -> None:
        self._store.close()


__all__ = [
    "ActionCheckpoint", "CheckpointAction", "CheckpointService", "CheckpointStatus",
    "CheckpointStore", "InMemoryCheckpointStore", "checkpoint_status",
    "reconcile_checkpoint", "TERMINAL_ACTION_STATUSES",
]
