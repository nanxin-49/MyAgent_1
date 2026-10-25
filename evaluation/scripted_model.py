"""JSON-scripted fake Anthropic model for deterministic harness tests.

Script format:
{
  "name": "example",
  "turns": [
    {"tool_calls": [{"name": "get_order", "input": {"order_id": "ORD-1"}, "id": "call_1"}]},
    {"text": "final answer"}
  ]
}
"""
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable


class ScriptExhausted(RuntimeError):
    """Raised instead of silently returning a canned answer."""


def load_script(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ScriptedModel:
    """Drop-in for ``AsyncAnthropic`` at the ``messages.create`` seam."""

    def __init__(self, turns: Iterable[dict], *, model: str = "scripted"):
        self._turns = list(turns)
        self._model = model
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._turns:
            raise ScriptExhausted("scripted model has no remaining turns")
        turn = self._turns.pop(0)
        content = []
        text = turn.get("text")
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        tool_calls = turn.get("tool_calls") or []
        for index, call in enumerate(tool_calls):
            content.append(SimpleNamespace(
                type="tool_use",
                id=call.get("id") or f"call_{len(self.calls)}_{index}",
                name=call["name"],
                input=call.get("input") or {},
            ))
        usage = SimpleNamespace(
            input_tokens=int(turn.get("input_tokens", 0) or 0),
            output_tokens=int(turn.get("output_tokens", 0) or 0),
        )
        return SimpleNamespace(
            content=content,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage=usage,
            id=f"scripted-{len(self.calls)}",
        )

    async def close(self) -> None:
        return None


def script_from_file(path: str | Path) -> ScriptedModel:
    script = load_script(path)
    return ScriptedModel(script.get("turns") or [], model=script.get("model", "scripted"))
