"""Evaluation-only tool fault injection. Production tools are never wrapped."""
from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

FAULT_KINDS = ("timeout", "invalid_arguments", "not_found", "dependency_failure", "execution_failure")


@dataclass(frozen=True)
class ToolFault:
    tool: str
    kind: str
    on_call: int = 1
    mode: str = "once"          # once | sticky
    message: str = ""

    def __post_init__(self):
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"unsupported fault kind: {self.kind}")
        if self.on_call < 1:
            raise ValueError("on_call must be >= 1")
        if self.mode not in {"once", "sticky"}:
            raise ValueError("mode must be once or sticky")


class InjectedToolFailure(Exception):
    code = "execution_failure"


class FaultInjector:
    def __init__(self, faults):
        self._faults = [f if isinstance(f, ToolFault) else ToolFault(**f) for f in (faults or [])]
        self._counts: dict[str, int] = defaultdict(int)
        self.events: list[dict] = []

    def _trigger(self, name: str) -> ToolFault | None:
        count = self._counts[name]
        for fault in self._faults:
            if fault.tool != name:
                continue
            if fault.mode == "once" and count == fault.on_call:
                return fault
            if fault.mode == "sticky" and count >= fault.on_call:
                return fault
        return None

    def _payload(self, name: str, fault: ToolFault) -> dict:
        message = fault.message or f"injected {fault.kind}"
        if name == "search_knowledge_base":
            return {"success": False, "query": "", "error": message,
                    "error_code": fault.kind, "retrieval_status": "degraded",
                    "results": [], "citations": [],
                    "answer_guidance": "检索依赖故障，不能判定知识是否存在。"}
        if fault.kind in {"not_found", "dependency_failure"}:
            return {"success": False, "data": None, "source": "business_provider",
                    "error": {"code": fault.kind, "message": message}}
        return {"success": False, "error": message, "error_code": fault.kind,
                "error_type": "tool", "retryable": False}

    def bind(self, name: str, handler):
        async def wrapped(*args, **kwargs):
            self._counts[name] += 1
            fault = self._trigger(name)
            if fault is not None:
                self.events.append({"tool": name, "call_index": self._counts[name],
                                    "kind": fault.kind, "error_code": fault.kind})
                if fault.kind == "timeout":
                    raise asyncio.TimeoutError(f"injected timeout: {name}")
                if fault.kind == "execution_failure":
                    raise InjectedToolFailure(f"injected execution failure: {name}")
                return self._payload(name, fault)
            result = handler(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        return wrapped


def wrap_tools(tools: dict[str, Any], injector: FaultInjector) -> dict[str, Any]:
    return {name: replace(spec, handler=injector.bind(name, spec.handler))
            for name, spec in tools.items()}


def events_by_tool(injector: FaultInjector) -> list[dict]:
    return list(injector.events)
