"""Production Single Support Agent, with backend-owned A02 handoff receipts."""
from dataclasses import dataclass, replace, field
from collections import deque
import os
import re
import time

from anthropic import AsyncAnthropic
from agents.agent_orchestrator import AgentProfile, AgentType, BaseAgent, GeneralAgent
from agents.tools import general_tools, technical_tools, billing_tools, escalation_tools
from core.model_observation import ObservedClient, model_events
from core.handoff import HandoffService, HandoffResult, explicit_handoff, handoff_reply
from core.tool_contract import execute_tool
from agents.tools import build_handoff_tools
from agents.agent_orchestrator import AgentResponse


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

    async def handle(self, req):
        req.handoff = HandoffResult()
        if explicit_handoff(req.message):
            spec = self.get_tools()["request_handoff"]
            args = {"reason_code": "explicit_request"}
            execution = await execute_tool(spec, args, lambda: spec.handler(req, args))
            payload = execution.agent_payload()
            trace = {"request_id": req.request_id, "agent_type": "support", "tool_name": spec.name,
                     "risk_level": "write", "tool_use_id": "deterministic_handoff_gate",
                     "input": args, "validated_input": execution.validated_input,
                     "success": execution.success, "result_success": payload.get("success"),
                     "error_code": execution.error_code, "error_type": execution.error_type,
                     "retryable": False, "latency_ms": execution.latency_ms,
                     "handoff_result": req.handoff.model_dump()}
            response = AgentResponse(self.agent_type, "", execution.success,
                                     tools_used=[spec.name], tool_traces=[trace])
        else:
            response = await super().handle(req)
        response.escalate = req.handoff.handoff_created
        if req.handoff.handoff_requested or req.handoff.handoff_failed or any(
            t.get("tool_name") == "request_handoff" for t in response.tool_traces
        ):
            action_receipt = self._last_action_receipt()
            response.content = (action_receipt + "\n" if action_receipt else "") + handoff_reply(req.handoff)
            response.success = req.handoff.handoff_created or bool(action_receipt)
        else:
            # Wording guard only: generated handoff language cannot certify an
            # absent record. It never changes any business state or escalated.
            sentences = re.split(r"(?<=[。！？.!?\n])", response.content)
            if any(re.search(r"人工|真人|转接|handoff|escalat|human|specialist", s, re.I) for s in sentences):
                response.content = "".join(s for s in sentences if not re.search(
                    r"人工|真人|转接|handoff|escalat|human|specialist", s, re.I)) + handoff_reply(req.handoff)
        return response

    def _needs_escalation(self, content):
        return False

    def _build_system_prompt(self, req):
        return super()._build_system_prompt(req) + (
            "\n[事实充分性与回答边界]\n"
            "主题相关不等于事实充分。search_knowledge_base的usable与citation只证明检索来源和有效性，"
            "不会自动证明最终回答。Skill仅指导流程，不能替代事实证据。"
            "按用户原始问题逐项识别必要事实，核对有效片段的直接依据；不得因查询改写而遗漏原问题中的限定条件。"
            "多个必要事实必须分别有依据；允许仅回答有依据的部分，明确其余部分无法确认，不自行补数字、时效或渠道。"
            "正文明确不支持该功能时，允许引用它回答能力边界，不机械拒绝所有相关问题。"
            "订单、物流、库存、退款状态等动态事实必须以当前客户有权限的Provider结果为依据；"
            "not_found只说明未找到可访问记录，不确认记录不存在或他人记录存在。"
            "正常no_answer/low_confidence是没有可引用证据，不证明事实不存在；依赖故障/degraded不能说成正常知识不足。"
            "模拟动作completed不证明真实资金到账；模拟交接记录不证明真人接单。"
            "\n人工交接只能通过 request_handoff 创建模拟记录。理由码仅 explicit_request、complex_complaint、"
            "business_dependency_failure。不要把摘要、越界拒绝或缺参数当成交接。"
            "订票等非电商能力可合理拒绝。不允许声称真人已接单或工具未创建的交接已成功。")


@dataclass
class SupportResult:
    request_id: str
    response: str
    escalated: bool
    latency_ms: float
    tools_used: list
    tool_traces: list
    model_calls: list
    handoff: HandoffResult = field(default_factory=HandoffResult)
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
        self.handoff_service = HandoffService()
        self._traces = deque(maxlen=int(os.getenv("ECHOMIND_TOOL_TRACE_MAX", "200")))
        self._total, self._success, self._total_ms = 0, 0, 0.0

    def set_shared_tools(self, tools):
        self._tools = {**dict(tools or {}), **build_handoff_tools(self.handoff_service)}

    def set_skill_manager(self, manager):
        self._skills = manager

    def make_agent(self):
        agent = SingleSupportAgent(self._client, self._model,
            AllRoleSkills(self._skills) if self._skills else None)
        agent.set_shared_tools({**self._tools, **build_handoff_tools(self.handoff_service)})
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
                               response.tools_used, response.tool_traces, events, handoff=req.handoff)
        self._traces.append({"request_id": req.request_id, "topology": "single", "agent_type": "support",
            "intent": None, "primary_agent": None, "supporting_agents": None,
            "routing_reason": None, "routing_confidence": None,
            "deprecated_fields": ["primary_agent", "supporting_agents", "routing_reason", "routing_confidence"],
            "tools_used": list(result.tools_used), "tool_calls": list(result.tool_traces),
            "escalated": result.escalated, "latency_ms": round(elapsed, 1),
            "handoff": result.handoff.model_dump(),
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
