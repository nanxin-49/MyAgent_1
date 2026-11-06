"""Stable trajectory recording and H1-1 ledger conversion for H2-2.

The recorder wraps the model client and records response content/stop_reason/usage
plus request-side hashes. It deliberately does not store full prompts or hidden
reasoning, matching core/model_observation.py's privacy contract.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "echomind.trajectory"
VERSION = 1


class TrajectoryError(ValueError):
    pass


def _sha(value: Any) -> str | None:
    if value is None:
        return None
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _block(block: Any) -> dict:
    if isinstance(block, dict):
        return dict(block)
    kind = getattr(block, "type", None)
    if kind == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if kind == "tool_use":
        return {"type": "tool_use", "id": getattr(block, "id", None),
                "name": getattr(block, "name", None), "input": getattr(block, "input", {})}
    return {"type": str(kind), "raw": str(block)}


def _usage(usage: Any) -> dict:
    if usage is None:
        return {}
    return {key: getattr(usage, key, None) for key in (
        "input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens",
    )}


def response_payload(response: Any) -> dict:
    return {
        "id": getattr(response, "id", None),
        "model": getattr(response, "model", None),
        "stop_reason": getattr(response, "stop_reason", None),
        "usage": _usage(getattr(response, "usage", None)),
        "content": [_block(block) for block in (getattr(response, "content", None) or [])],
    }


def request_payload(kwargs: dict) -> dict:
    messages = kwargs.get("messages") or []
    tool_results = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_results.append(dict(block))
    return {
        "messages_sha256": _sha(messages),
        "system_sha256": _sha(kwargs.get("system")),
        "tool_schema_sha256": _sha(kwargs.get("tools")),
        "message_count": len(messages),
        "tool_results_sent": tool_results,
    }


class TrajectoryRecorder:
    """Client wrapper: records every messages.create turn and passes it through."""

    def __init__(self, client: Any, stage: str = "support", *, case_id: str | None = None):
        self._client = client
        self.stage = stage
        self.case_id = case_id
        self.turns: list[dict] = []
        self.calls: list[dict] = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = await self._client.messages.create(**kwargs)
        self.turns.append({
            "index": len(self.turns),
            "source_event_number": len(self.turns) + 1,
            "stage": self.stage,
            "request": request_payload(kwargs),
            "response": response_payload(response),
            "latency_ms": None,
            "http_status": 200,
            "error": None,
            "at_utc": datetime.now(timezone.utc).isoformat(),
        })
        return response

    async def close(self):
        return await self._client.close()

    def build(self, *, provenance: dict | None = None, case: dict | None = None,
              outcome: dict | None = None, evidence_level: str = "real_model") -> dict:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "evidence_level": evidence_level,
            "provenance": provenance or {},
            "case": case or {"id": self.case_id, "message": "", "turn_range": []},
            "turns": self.turns,
            "outcome": outcome or {},
        }

    def dump(self, path: str | Path, **kwargs) -> None:
        Path(path).write_text(json.dumps(self.build(**kwargs), ensure_ascii=False, indent=2),
                              encoding="utf-8")


def load(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise TrajectoryError(f"unsupported trajectory schema: {data.get('schema')!r}")
    if data.get("version") != VERSION:
        raise TrajectoryError(f"unsupported trajectory version: {data.get('version')!r}")
    return data


def turns_for_replay(trajectory: dict) -> list[dict]:
    turns = []
    for turn in trajectory.get("turns") or []:
        response = turn.get("response") or {}
        turns.append({
            "content": response.get("content") or [],
            "stop_reason": response.get("stop_reason"),
            "usage": response.get("usage") or {},
            "model": response.get("model"),
            "id": response.get("id"),
            "error": turn.get("error"),
            "request": turn.get("request") or {},
        })
    return turns


def from_model_ledger(ledger: dict, *, case_id: str, turn_range: list[int] | None = None,
                      provenance: dict | None = None, stages: set[str] | None = None) -> dict:
    """Convert H1-1's response-side model ledger into a trajectory.

    The ledger has no request messages/system/tools, so those fields are null;
    this is recorded in provenance and must not be presented as a full request
    transcript. ``stages`` filters interleaved RAG rewrite/rerank calls.
    """
    start, end = (turn_range or [1, 10 ** 9])
    events = [event for event in (ledger.get("events") or [])
              if start <= int(event.get("number", 0)) <= end
              and (stages is None or event.get("stage") in stages)]
    turns = []
    for index, event in enumerate(events):
        turns.append({
            "index": index,
            "source_event_number": event.get("number"),
            "stage": event.get("stage"),
            "request": {
                "messages_sha256": None,
                "system_sha256": None,
                "tool_schema_sha256": None,
                "message_count": None,
                "tool_results_sent": event.get("tool_results_sent") or [],
            },
            "response": {
                "id": None,
                "model": event.get("model"),
                "stop_reason": event.get("stop_reason"),
                "usage": event.get("usage") or {},
                "content": event.get("content") or [],
            },
            "latency_ms": event.get("latency_ms"),
            "http_status": event.get("http_status"),
            "error": event.get("error_type"),
            "at_utc": event.get("at_utc"),
        })
    provenance = dict(provenance or {})
    provenance.setdefault("model", events[0].get("model") if events else None)
    provenance.setdefault("note", "converted from H1-1 model_ledger; request messages/system/tools unavailable")
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "converted_h1_1_ledger",
        "provenance": provenance,
        "case": {"id": case_id, "message": "", "turn_range": turn_range or []},
        "turns": turns,
        "outcome": {},
    }
