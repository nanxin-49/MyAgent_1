"""H2-4 baseline profiles. Evaluation-only; production /chat never imports these."""
from __future__ import annotations

from core.harness import HarnessConfig

PROFILES = ("full", "bare")


def bare_harness(max_tool_rounds: int = 10) -> HarnessConfig:
    """Model + tools only: keep PolicyEngine, disable the other harness layers.

    ``max_tool_rounds`` is a runner-side experiment bound, not a deliverable
    guardrail. It stops one runaway case from consuming the whole budget; the
    number of turns that hit it is reported as ``loop_truncated``.
    """
    if max_tool_rounds < 1:
        raise ValueError("max_tool_rounds must be >= 1")
    return HarnessConfig.evaluation(
        policy_guard=True,
        error_feedback=False,
        context_compression=False,
        loop_control=False,
        output_consistency=False,
        unguarded_max_tool_rounds=max_tool_rounds,
    )


def harness_for_profile(name: str, *, max_tool_rounds: int = 10) -> HarnessConfig | None:
    """``full`` keeps production defaults (None); ``bare`` builds the ablation."""
    if name == "full":
        return None
    if name == "bare":
        return bare_harness(max_tool_rounds=max_tool_rounds)
    raise ValueError(f"unknown profile: {name}")
