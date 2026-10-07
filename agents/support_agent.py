"""Production Single Support Agent. Role text matches accepted T10 Single."""
from dataclasses import dataclass, replace
from collections import deque
import os
import time

from anthropic import AsyncAnthropic
from agents.agent_orchestrator import AgentProfile, AgentType, BaseAgent, GeneralAgent
from agents.tools import general_tools, technical_tools, billing_tools, escalation_tools
from core.model_observation import ObservedClient, model_events


def support_helpers():
    return {**general_tools(), **technical_tools(), **billing_tools(), **escalation_tools()}


class AllRoleSkills:
    def __init__(self, manager):
        self.manager = manager

    def prompt_for(self, message, agent_type=None):
        return self.manager.prompt_for(message, None)


class SingleSupportAgent(BaseAgent):
    agent_type = AgentType.SUPPORT
    system_prompt = GeneralAgent.system_prompt
    profile = AgentProfile(
        role="电商客服", mission="处理商品、订单、物流和售后问题，明确证据与人工处理边界。",
        workflow=("确认诉求", "回答或收集必要信息", "按工具结果说明下一步"),
        input_contract=("用户消息", "相同的冻结会话上下文"),
        output_contract=GeneralAgent.profile.output_contract,
        handoff_conditions=GeneralAgent.profile.handoff_conditions,
        tool_scope=tuple(support_helpers()), temperature=.2, max_tokens=1200,
    )

    def get_tools(self):
        return {**super().get_tools(), **support_helpers()}

    def _build_role_packet(self, req):
        return ""


@dataclass
class SupportResult:
    request_id: str
    response: str
    escalated: bool
    latency_ms: float
    tools_used: list
    tool_traces: list
    model_calls: list
    agent_type: AgentType = AgentType.SUPPORT
    intent: None = None


class SupportRuntime:
    """One topology, independent Agent state per request, shared guarded handlers."""
    supports_routing = False

    def __init__(self, api_key, model, base_url=None, skill_manager=None, client=None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._raw_client = client or AsyncAnthropic(**kwargs)
        self._client = ObservedClient(self._raw_client, "support")
        self._model, self._skills = model, skill_manager
        self._tools = {}
        self._traces = deque(maxlen=int(os.getenv("ECHOMIND_TOOL_TRACE_MAX", "200")))
        self._total, self._success, self._total_ms = 0, 0, 0.0

    def set_shared_tools(self, tools):
        self._tools = dict(tools or {})

    def set_skill_manager(self, manager):
        self._skills = manager

    def make_agent(self):
        agent = SingleSupportAgent(self._client, self._model,
            AllRoleSkills(self._skills) if self._skills else None)
        agent.set_shared_tools(self._tools)
        agent.profile = replace(agent.profile, tool_scope=tuple(agent.get_tools()))
        return agent

    async def run(self, req):
        # Classification fields are neither created nor used for dispatch.
        agent = self.make_agent()
        events = []
        token = model_events.set(events)
        start = time.monotonic()
        try:
            response = await agent.handle(req)
        finally:
            model_events.reset(token)
        elapsed = (time.monotonic() - start) * 1000
        self._total += 1
        self._success += int(response.success)
        self._total_ms += elapsed
        result = SupportResult(req.request_id, response.content, response.escalate, elapsed,
                               response.tools_used, response.tool_traces, events)
        self._traces.append({"request_id": req.request_id, "topology": "single", "agent_type": "support",
            "intent": None, "primary_agent": None, "supporting_agents": None,
            "routing_reason": None, "routing_confidence": None,
            "deprecated_fields": ["primary_agent", "supporting_agents", "routing_reason", "routing_confidence"],
            "tools_used": list(result.tools_used), "tool_calls": list(result.tool_traces),
            "escalated": result.escalated, "latency_ms": round(elapsed, 1),
            "model_call_count": len(events), "model_calls": list(events),
            "model_observation_scope": "support + RAG SDK calls; excludes Memory/profile and internal HTTP retries"})
        return result

    def get_tool_trace(self, request_id):
        return next((t for t in reversed(self._traces) if t["request_id"] == request_id), None)

    def get_recent_tool_traces(self, limit=20):
        return list(reversed(list(self._traces)[-max(1, int(limit)):]))

    def get_stats(self):
        return {"support_0": {"total": self._total,
            "success_rate": self._success / self._total if self._total else 1.0,
            "avg_ms": self._total_ms / self._total if self._total else 0.0,
            "model": self._model, "role": "support", "topology": "single",
            "available_tools": list(self.make_agent().get_tools())}}

    async def close(self):
        await self._raw_client.close()
