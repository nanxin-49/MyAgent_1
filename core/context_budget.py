"""Estimated prompt composition and deterministic context compression.

Token counts are estimates (ASCII/4 + non-ASCII chars), not model tokenizer
output; they are used for budgeting and reporting only.
"""
from __future__ import annotations

import copy
import json
import math
from typing import Any

BACKGROUND_PREFIXES = ("[背景信息]", "[结构化实体]", "[角色输入契约]")
TOOL_RESULT_KEEP = ("success", "error_code", "error_type", "retryable",
                    "suggested_action", "retrieval_status", "answer_guidance",
                    "status", "action_id", "refund_id")
TOOL_PREVIEW_CHARS = 200
BACKGROUND_KEEP_CHARS = 400
DIALOGUE_KEEP_CHARS = 300


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    return math.ceil(ascii_chars / 4) + (len(text) - ascii_chars)


def _is_retrieval(raw: str) -> bool:
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(parsed, dict) and (
        "retrieval_status" in parsed or "citations" in parsed)


def _block_tokens(block: Any) -> int:
    return estimate_tokens(json.dumps(block, ensure_ascii=False, default=str))


def _last_user_index(messages: list[dict]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index].get("content"), str):
            return index
    return None


def _message_tokens(message: dict) -> int:
    content = message.get("content")
    if isinstance(content, str):
        return estimate_tokens(content)
    if isinstance(content, list):
        return sum(_block_tokens(block) for block in content)
    return 0


def compose_context(messages: list[dict], *, system: str = "",
                    tool_schemas: Any = None) -> dict[str, int]:
    """Report the estimated prompt composition for one model call."""
    system_tokens = estimate_tokens(system)
    tools_tokens = estimate_tokens(
        json.dumps(tool_schemas, ensure_ascii=False, default=str) if tool_schemas else "")
    memory = user = dialogue = tool_results = retrieval = 0
    current = _last_user_index(messages)
    for index, message in enumerate(messages):
        content = message.get("content")
        if isinstance(content, str):
            if content.startswith(BACKGROUND_PREFIXES):
                memory += estimate_tokens(content)
            elif index == current:
                user += estimate_tokens(content)
            else:
                dialogue += estimate_tokens(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    raw = block.get("content") or ""
                    tokens = estimate_tokens(raw if isinstance(raw, str) else str(raw))
                    tool_results += tokens
                    if isinstance(raw, str) and _is_retrieval(raw):
                        retrieval += tokens
                else:
                    dialogue += _block_tokens(block)
    return {
        "system_prompt": system_tokens,
        "tool_schemas": tools_tokens,
        "memory_context": memory,
        "user_message": user,
        "dialogue": dialogue,
        "tool_results": tool_results,
        "retrieval": retrieval,
        "total": system_tokens + tools_tokens + memory + user + dialogue + tool_results,
    }


def _compress_tool_result(raw: Any) -> str:
    text = raw if isinstance(raw, str) else str(raw)
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, dict):
        return json.dumps({"compressed": True, "preview": text[:TOOL_PREVIEW_CHARS]},
                          ensure_ascii=False)
    kept = {key: parsed[key] for key in TOOL_RESULT_KEEP if key in parsed}
    kept["compressed"] = True
    kept["preview"] = json.dumps(parsed, ensure_ascii=False, default=str)[:TOOL_PREVIEW_CHARS]
    return json.dumps(kept, ensure_ascii=False, default=str)


def _total_tokens(messages: list[dict], fixed_tokens: int) -> int:
    return fixed_tokens + sum(_message_tokens(message) for message in messages)


def _compression_targets(messages: list[dict], current: int | None):
    """Yield (index, kind) in compression priority order."""
    for index, message in enumerate(messages):
        content = message.get("content")
        if isinstance(content, list) and any(
                isinstance(block, dict) and block.get("type") == "tool_result"
                for block in content):
            yield index, "tool_result"
    for index, message in enumerate(messages):
        content = message.get("content")
        if index == current or not isinstance(content, str):
            continue
        if content.startswith(BACKGROUND_PREFIXES):
            yield index, "background"
    for index, message in enumerate(messages):
        content = message.get("content")
        if index == current or not isinstance(content, str):
            continue
        if not content.startswith(BACKGROUND_PREFIXES):
            yield index, "dialogue"


def _apply(messages: list[dict], index: int, kind: str) -> bool:
    message = messages[index]
    content = message.get("content")
    if kind == "tool_result":
        changed = False
        new_blocks = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                raw = block.get("content")
                if isinstance(raw, str) and '"compressed": true' in raw:
                    new_blocks.append(block)
                    continue
                new_blocks.append({**block, "content": _compress_tool_result(raw)})
                changed = True
            else:
                new_blocks.append(block)
        message["content"] = new_blocks
        return changed
    if kind == "background":
        if content.endswith("[背景已压缩]"):
            return False
        message["content"] = content[:BACKGROUND_KEEP_CHARS] + "\n[背景已压缩]"
        return True
    if kind == "dialogue":
        if content.endswith("[已压缩]"):
            return False
        message["content"] = content[:DIALOGUE_KEEP_CHARS] + "\n[已压缩]"
        return True
    return False


def compress_messages(messages: list[dict], *, budget: int, fixed_tokens: int) -> dict:
    """Compress message content until the estimated prompt fits the budget.

    System prompt, tool schemas and the current user message are never touched;
    when they alone exceed the budget, ``over_budget`` is reported truthfully.
    """
    working = copy.deepcopy(messages)
    total = _total_tokens(working, fixed_tokens)
    compressed = False
    if total <= budget:
        return {"messages": working, "compressed": False, "over_budget": False,
                "estimated_tokens": total}
    current = _last_user_index(working)
    for index, kind in _compression_targets(working, current):
        if total <= budget:
            break
        if _apply(working, index, kind):
            compressed = True
            total = _total_tokens(working, fixed_tokens)
    return {"messages": working, "compressed": compressed,
            "over_budget": total > budget, "estimated_tokens": total}
