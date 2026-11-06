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

from evaluation.trajectory import _sha, load as load_trajectory, turns_for_replay


class ScriptExhausted(RuntimeError):
    """Raised instead of silently returning a canned answer."""


class ScriptedProviderError(RuntimeError):
    """Replays a recorded provider error turn."""


def load_script(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ScriptedModel:
    """Drop-in for ``AsyncAnthropic`` at the ``messages.create`` seam."""

    def __init__(self, turns: Iterable[dict], *, model: str = "scripted",
                 expect_request_sha256: bool = False):
        self._turns = list(turns)
        self._model = model
        self._expect_request_sha256 = expect_request_sha256
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._turns:
            raise ScriptExhausted("scripted model has no remaining turns")
        turn = self._turns.pop(0)
        if self._expect_request_sha256:
            expected = (turn.get("request") or {}).get("messages_sha256")
            if expected and _sha(kwargs.get("messages")) != expected:
                raise RuntimeError("replay request messages do not match the recorded trajectory")
        if turn.get("error"):
            raise ScriptedProviderError(str(turn["error"]))
        content = self._content(turn)
        tool_calls = [block for block in content if getattr(block, "type", None) == "tool_use"]
        usage_data = turn.get("usage") or {
            "input_tokens": turn.get("input_tokens", 0),
            "output_tokens": turn.get("output_tokens", 0),
        }
        usage = SimpleNamespace(
            input_tokens=int(usage_data.get("input_tokens", 0) or 0),
            output_tokens=int(usage_data.get("output_tokens", 0) or 0),
            cache_creation_input_tokens=usage_data.get("cache_creation_input_tokens"),
            cache_read_input_tokens=usage_data.get("cache_read_input_tokens"),
        )
        stop_reason = turn.get("stop_reason") or ("tool_use" if tool_calls else "end_turn")
        return SimpleNamespace(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            id=turn.get("id") or f"scripted-{len(self.calls)}",
            model=turn.get("model") or self._model,
        )

    def _content(self, turn: dict) -> list:
        if "content" in turn:
            blocks = []
            for block in turn.get("content") or []:
                if isinstance(block, dict):
                    blocks.append(SimpleNamespace(**block))
                else:
                    blocks.append(block)
            return blocks
        content = []
        text = turn.get("text")
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        for index, call in enumerate(turn.get("tool_calls") or []):
            content.append(SimpleNamespace(
                type="tool_use",
                id=call.get("id") or f"call_{len(self.calls)}_{index}",
                name=call["name"],
                input=call.get("input") or {},
            ))
        return content

    def assert_consumed(self) -> None:
        if self._turns:
            raise AssertionError(f"{len(self._turns)} scripted turns were not consumed")

    async def close(self) -> None:
        return None


def script_from_file(path: str | Path) -> ScriptedModel:
    script = load_script(path)
    return ScriptedModel(script.get("turns") or [], model=script.get("model", "scripted"))


def from_trajectory(path: str | Path, *, expect_request_sha256: bool = False) -> ScriptedModel:
    trajectory = load_trajectory(path)
    model = (trajectory.get("provenance") or {}).get("model") or "scripted"
    return ScriptedModel(turns_for_replay(trajectory), model=model,
                         expect_request_sha256=expect_request_sha256)
