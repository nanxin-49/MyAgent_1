"""Experimental topology only. Production /chat and business modules are unchanged."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from actions import ActionService, InMemoryBusinessActionBackend
from agents.agent_orchestrator import AgentProfile, AgentType, BaseAgent, GeneralAgent
from agents.tools import (billing_tools, build_action_tools, build_business_tools,
                          build_shared_rag_tools, escalation_tools, general_tools, technical_tools)
from providers.mock_backend import InMemoryBusinessBackend


def helper_tools():
    return {**general_tools(), **technical_tools(), **billing_tools(), **escalation_tools()}


class SingleSupportAgent(BaseAgent):
    # GENERAL is only the legacy response/trace envelope, not a dispatch target.
    agent_type = AgentType.GENERAL
    system_prompt = GeneralAgent.system_prompt
    profile = AgentProfile(
        role="电商客服", mission="处理商品、订单、物流和售后问题，明确证据与人工处理边界。",
        workflow=("确认诉求", "回答或收集必要信息", "按工具结果说明下一步"),
        input_contract=("用户消息", "相同的冻结会话上下文"),
        output_contract=GeneralAgent.profile.output_contract,
        handoff_conditions=GeneralAgent.profile.handoff_conditions,
        tool_scope=tuple(helper_tools()), temperature=0.2, max_tokens=1200,
    )

    def get_tools(self):
        return {**super().get_tools(), **helper_tools()}

    def _build_role_packet(self, req):
        # No case labels, guessed entities, or classifier output are injected.
        return ""


class AllRoleSkills:
    """Reuse existing skill text and keyword matching; remove only role filtering."""
    def __init__(self, manager):
        self.manager = manager

    def prompt_for(self, message, agent_type=None):
        return self.manager.prompt_for(message, None)


def isolated_business(fixture: dict[str, Any], now):
    # Backends shallow-copy records internally, so give each independent deep data.
    read = InMemoryBusinessBackend(deepcopy(fixture))
    write = InMemoryBusinessActionBackend(deepcopy(fixture))
    service = ActionService(business_backend=read, action_backend=write, clock=lambda: now)
    tools = {**build_business_tools(read), **build_action_tools(service)}
    return tools, service, write


def bind_tools(agent, business_tools, rag_manager):
    tools = {**build_shared_rag_tools(rag_manager), **business_tools}
    agent.set_shared_tools(tools)
    return tools


def matched_generation(orchestrator, model, temperature, max_tokens):
    """Runner-only control. Leave routing, role text, helper allowlists intact."""
    for pool in orchestrator._pool.values():
        for agent in pool:
            agent._model = model
            agent.profile = replace(agent.profile, model=model, temperature=temperature,
                                    max_tokens=max_tokens)

