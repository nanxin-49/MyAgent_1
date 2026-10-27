"""Redis-backed action and checkpoint stores for single-instance persistence."""
from __future__ import annotations

from threading import RLock

from redis import Redis

from core.checkpoint import ActionCheckpoint, CheckpointStore
from .models import PendingAction
from .store import ActionStore

DEFAULT_ACTION_PREFIX = "cartcare:actions"
DEFAULT_CHECKPOINT_PREFIX = "cartcare:checkpoints"

# Atomic idempotency binding: never let two action IDs share one key.
_SAVE_ACTION_LUA = """
local existing = redis.call('GET', KEYS[2])
if existing and existing ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2])
redis.call('SET', KEYS[2], ARGV[1])
return 1
"""


class IdempotencyConflict(RuntimeError):
    """A Redis idempotency key is already bound to another action."""


class RedisActionStore(ActionStore):
    backend_name = "redis-action-store"

    def __init__(self, redis_url: str, *, prefix: str = DEFAULT_ACTION_PREFIX,
                 client: Redis | None = None) -> None:
        self._client = client or Redis.from_url(
            redis_url, decode_responses=True, socket_timeout=5)
        self._client.ping()
        self._prefix = prefix.rstrip(":")
        self.lock = RLock()
        self._save_script = self._client.register_script(_SAVE_ACTION_LUA)

    def _action_key(self, action_id: str) -> str:
        return f"{self._prefix}:action:{action_id}"

    def _idem_key(self, key: str) -> str:
        return f"{self._prefix}:idem:{key}"

    def get(self, action_id: str) -> PendingAction | None:
        raw = self._client.get(self._action_key(action_id))
        if raw is None:
            return None
        return PendingAction.model_validate_json(raw)

    def find_by_idempotency(self, key: str) -> PendingAction | None:
        action_id = self._client.get(self._idem_key(key))
        return self.get(action_id) if action_id else None

    def save(self, action: PendingAction) -> PendingAction:
        result = self._save_script(
            keys=[self._action_key(action.action_id),
                  self._idem_key(action.idempotency_key)],
            args=[action.action_id, action.model_dump_json()],
        )
        if int(result) != 1:
            raise IdempotencyConflict(
                f"idempotency key {action.idempotency_key!r} is bound to another action")
        return action

    def close(self) -> None:
        self._client.close()


class RedisCheckpointStore(CheckpointStore):
    backend_name = "redis-checkpoint-store"

    def __init__(self, redis_url: str, *, prefix: str = DEFAULT_CHECKPOINT_PREFIX,
                 client: Redis | None = None) -> None:
        self._client = client or Redis.from_url(
            redis_url, decode_responses=True, socket_timeout=5)
        self._client.ping()
        self._prefix = prefix.rstrip(":")

    def _checkpoint_key(self, request_id: str) -> str:
        return f"{self._prefix}:checkpoint:{request_id}"

    def _action_key(self, action_id: str) -> str:
        return f"{self._prefix}:action:{action_id}"

    def save(self, checkpoint: ActionCheckpoint) -> ActionCheckpoint:
        with self._client.pipeline(transaction=True) as pipe:
            pipe.set(self._checkpoint_key(checkpoint.request_id),
                     checkpoint.model_dump_json())
            for action in checkpoint.actions:
                pipe.set(self._action_key(action.action_id), checkpoint.request_id)
            pipe.execute()
        return checkpoint

    def get(self, request_id: str) -> ActionCheckpoint | None:
        raw = self._client.get(self._checkpoint_key(request_id))
        if raw is None:
            return None
        return ActionCheckpoint.model_validate_json(raw)

    def find_by_action(self, action_id: str) -> ActionCheckpoint | None:
        request_id = self._client.get(self._action_key(action_id))
        return self.get(request_id) if request_id else None

    def close(self) -> None:
        self._client.close()


__all__ = [
    "DEFAULT_ACTION_PREFIX", "DEFAULT_CHECKPOINT_PREFIX", "IdempotencyConflict",
    "RedisActionStore", "RedisCheckpointStore",
]
