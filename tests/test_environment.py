"""Minimal import smoke tests for the declared development environment."""


def test_runtime_modules_import_from_repository_root():
    """The test runner must be able to collect the project's public modules."""
    import agents.agent_orchestrator  # noqa: F401
    import agents.tools  # noqa: F401
    import api.main  # noqa: F401
    import core.intent_recognizer  # noqa: F401
    import mcp.knowledge_base  # noqa: F401
    import memory.conversation_memory  # noqa: F401
