"""H3-2 recovery probe: a deterministic model that acts only on error fields.

Not a language model and not a model-quality metric. It proves that the
structured error channel carries enough information for a decision, and that
turning ``error_feedback`` off removes it.
"""
from __future__ import annotations

import json
from types import SimpleNamespace


class RecoveryModel:
    def __init__(self, case: dict):
        self.case = case
        self.calls: list[dict] = []
        self.retries = 0
        self.seen_payloads: list[dict] = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = _last_tool_payload(kwargs.get("messages") or [])
        if payload is None:
            return self._tool_use()
        self.seen_payloads.append(payload)
        if payload.get("acknowledged") is True and "error_code" not in payload:
            return self._text(self.case["unrecovered_text"])
        if payload.get("success") is not False:
            return self._text(self.case["success_text"])
        action = payload.get("suggested_action")
        if action == "ask_user_for_missing_fields":
            return self._text(self.case["ask_text"])
        if action == "ask_user_to_confirm_identifier":
            return self._text(self.case["confirm_text"])
        if action == "explain_access_limit":
            return self._text(self.case.get("access_text", self.case["explain_text"]))
        if action == "explain_policy_and_stop":
            return self._text(self.case["explain_text"])
        if action == "retry_later" and payload.get("retryable"):
            if self.retries < int(self.case.get("max_retries", 1)):
                self.retries += 1
                return self._tool_use()
            return self._text(self.case["exhausted_text"])
        return self._text(self.case.get("report_text", "处理失败，请稍后重试。"))

    def _tool_use(self):
        return self._response([SimpleNamespace(
            type="tool_use", id=f"probe_call_{len(self.calls)}",
            name=self.case["tool"], input=dict(self.case.get("args") or {}))])

    def _text(self, text: str):
        return self._response([SimpleNamespace(type="text", text=text)])

    def _response(self, content):
        calls = len(self.calls)
        return SimpleNamespace(
            content=content,
            stop_reason="tool_use" if getattr(content[0], "type", None) == "tool_use" else "end_turn",
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
            id=f"probe-{calls}", model="recovery-probe",
        )

    async def close(self):
        return None


def _last_tool_payload(messages) -> dict | None:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in reversed(content):
            if isinstance(item, dict) and item.get("type") == "tool_result":
                raw = item.get("content")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        return None
                    return parsed if isinstance(parsed, dict) else None
    return None
