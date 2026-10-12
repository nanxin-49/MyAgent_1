"""Per-run simulated evaluation composition; never accepts a live business runtime."""
import json
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace

from core.auth import Principal


EVALUATION_PRINCIPAL = Principal(
    "evaluation:fixture:customer-1", "customer-1", frozenset({"customer"})
)


class EvaluationRuntimeFactory:
    def __init__(self, *, fixture_data, cfg, knowledge_tool, skills_dir, max_prompt_chars):
        # Immutable serialized fixture, captured before chat mutates any records.
        self._fixture_json = json.dumps(fixture_data)
        self._cfg = dict(cfg)
        self._knowledge_tool = knowledge_tool
        self._skills_dir = skills_dir
        self._max_prompt_chars = max_prompt_chars

    @asynccontextmanager
    async def __call__(self):
        from actions import ActionService, InMemoryBusinessActionBackend
        from agents.support_agent import SupportRuntime
        from agents.tools import build_action_tools, build_business_tools, build_shared_rag_tools
        from core.model_observation import ObservedClient
        from core.skill_loader import SkillManager
        from mcp.tool_manager import MCPToolManager
        from providers.mock_backend import InMemoryBusinessBackend

        backend = InMemoryBusinessBackend(json.loads(self._fixture_json))
        service = ActionService(business_backend=backend,
            action_backend=InMemoryBusinessActionBackend(backend.state))
        skills = SkillManager(root_dir=self._skills_dir, max_prompt_chars=self._max_prompt_chars)
        skills.load()
        runtime = manager = None
        try:
            runtime = SupportRuntime(**self._cfg, skill_manager=skills)
            manager = MCPToolManager(**self._cfg)
            # Fresh cache, counters, breaker and schema. Only the read-only search
            # handler/fallback are reused; no knowledge write tools or Memory.
            manager.register(replace(self._knowledge_tool,
                                     schema=deepcopy(self._knowledge_tool.schema)))
            manager._client = ObservedClient(manager._client, "rag_rewrite_or_rerank")
            tools = build_shared_rag_tools(manager)
            tools.update(build_business_tools(backend))
            tools.update(build_action_tools(service))
            runtime.set_shared_tools(tools)
            yield runtime
        finally:
            try:
                if runtime is not None:
                    await runtime.close()
            finally:
                if manager is not None:
                    await manager._client.close()
