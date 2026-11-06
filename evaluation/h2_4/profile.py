"""Harness ablation profiles. Evaluation-only; production /chat never imports these."""
from __future__ import annotations

from core.harness import HarnessConfig

PROFILES = (
    "full",
    "bare",
    "no_guardrails",
    "no_error_feedback",
    "no_context_compression",
    "no_loop_control",
)


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
    """Return the config for an ablation profile.

    ``full`` keeps production defaults (``None``). All other profiles are
    evaluation-only and may only be constructed through ``HarnessConfig.evaluation``.
    The ``no_loop_control`` profile keeps a 10-round runner bound so one runaway
    case cannot consume the whole ablation budget; it is not a deliverable guardrail.
    """
    if name == "full":
        return None
    if name == "bare":
        return bare_harness(max_tool_rounds=max_tool_rounds)
    if name == "no_guardrails":
        return HarnessConfig.evaluation(policy_guard=False, output_consistency=False)
    if name == "no_error_feedback":
        return HarnessConfig.evaluation(error_feedback=False)
    if name == "no_context_compression":
        return HarnessConfig.evaluation(context_compression=False)
    if name == "no_loop_control":
        return HarnessConfig.evaluation(
            loop_control=False, unguarded_max_tool_rounds=max_tool_rounds)
    raise ValueError(f"unknown profile: {name}")
