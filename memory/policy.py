"""Deterministic, deliberately narrow rules for persisted support memory.

Memory contains references and explicit communication preferences, never live
business facts. Provider and ActionService remain the authority for state.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable


ORDER_ID = re.compile(r"\bORD-[A-Za-z0-9-]{3,64}\b")
PREFERENCE_RULES = {
    "reply_language": (("中文", ("请用中文", "用中文回复", "希望用中文")),
                       ("English", ("请用英文", "用英文回复", "希望用英文"))),
    "reply_detail": (("简短", ("请简短", "简短回复", "回答简短", "希望简短")),
                     ("详细", ("请详细", "详细回复", "回答详细", "希望详细"))),
}
TOPICS = {"refund_policy": ("退款政策", "退货政策"),
          "shipping_policy": ("配送政策", "运费政策"),
          "after_sales": ("售后流程", "售后政策"),
          "membership": ("会员规则", "会员政策")}
CLARIFICATIONS = {"order_id": ("请提供订单号", "提供订单号"),
                  "product_model": ("请提供商品型号", "提供商品型号")}


def explicit_preferences(message: str) -> dict[str, str]:
    """Only direct user instructions from an allowlist can enter a profile."""
    result: dict[str, str] = {}
    for name, alternatives in PREFERENCE_RULES.items():
        for value, phrases in alternatives:
            if any(phrase in message for phrase in phrases):
                result[name] = value
    return result


def validated_preferences(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items()
            if any(key == field and value == allowed
                   for field, alternatives in PREFERENCE_RULES.items()
                   for allowed, _ in alternatives)}


def user_order_refs(messages: Iterable[Any], previous: str = "") -> list[str]:
    refs = ORDER_ID.findall(previous)
    for message in messages:
        if getattr(getattr(message, "role", None), "value", None) == "user":
            refs.extend(ORDER_ID.findall(message.content))
    return list(dict.fromkeys(refs))[-5:]


def compressed_summary(messages: list[Any], previous: str = "") -> str:
    """Keep references and unresolved clarifications, without model inference."""
    if previous and not previous.startswith("历史参考；"):
        previous = ""  # An old model-written summary is not a trusted source.
    refs = user_order_refs(messages, previous)
    prefs = validated_preferences(dict(re.findall(r"(reply_language|reply_detail)=([^;\n]+)", previous)))
    for message in messages:
        if getattr(getattr(message, "role", None), "value", None) == "user":
            prefs.update(explicit_preferences(message.content))
    pending = set(re.findall(r"pending=(order_id|product_model)", previous))
    for index, message in enumerate(messages):
        if getattr(getattr(message, "role", None), "value", None) != "assistant":
            continue
        for field, phrases in CLARIFICATIONS.items():
            if any(phrase in message.content for phrase in phrases):
                later_users = [m.content for m in messages[index + 1:]
                               if getattr(getattr(m, "role", None), "value", None) == "user"]
                resolved = bool(ORDER_ID.search(" ".join(later_users))) if field == "order_id" else False
                if not resolved:
                    pending.add(field)
    if refs:
        pending.discard("order_id")
    parts = [f"订单号引用: {', '.join(refs)}" ] if refs else []
    parts.extend(f"{key}={value}" for key, value in sorted(prefs.items()))
    parts.extend(f"pending={field}" for field in sorted(pending))
    if not parts:
        return ""
    return "历史参考；仅用于引用和澄清，实时业务状态必须重新查询。\n" + "; ".join(parts)


def episodic_topics(messages: Iterable[Any]) -> list[str]:
    labels: list[str] = []
    for message in messages:
        if getattr(getattr(message, "role", None), "value", None) != "user":
            continue
        for label, phrases in TOPICS.items():
            if any(phrase in message.content for phrase in phrases):
                labels.append(label)
    return list(dict.fromkeys(labels))[:3]


def fresh_metadata(metadata: Any, *, user_id: str, memory_type: str, source: str) -> bool:
    if not isinstance(metadata, dict) or metadata.get("user_id") != user_id:
        return False
    if metadata.get("memory_type") != memory_type or metadata.get("source") != source:
        return False
    try:
        created = datetime.fromisoformat(metadata["created_at"])
        expiry = datetime.fromisoformat(metadata["expires_at"])
        now = datetime.now(timezone.utc)
        return (created.tzinfo is not None and expiry.tzinfo is not None
                and created <= now < expiry and created < expiry)
    except (KeyError, TypeError, ValueError):
        return False
