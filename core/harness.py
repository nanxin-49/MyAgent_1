"""Harness component switches. Defaults are all-on; off is evaluation-only."""
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessConfig:
    """Independent switches for ablation runs.

    Production code constructs ``HarnessConfig()`` (all on) or passes nothing.
    Only ``HarnessConfig.evaluation(...)`` may disable a component; constructing
    a non-default config outside evaluation raises instead of silently weakening
    the live path.
    """

    policy_guard: bool = True
    error_feedback: bool = True
    context_compression: bool = True
    loop_control: bool = True
    output_consistency: bool = True
    max_tool_rounds: int = 3
    max_tool_steps: int = 8
    max_tokens_per_turn: int = 60000
    duplicate_call_limit: int = 3
    tool_timeout_s: float = 30.0
    max_tool_result_chars: int = 8000
    max_context_tokens: int = 16000
    unguarded_max_tool_rounds: int = 1000
    mode: str = "production"

    def __post_init__(self):
        if self.mode not in {"production", "evaluation"}:
            raise ValueError("mode must be production or evaluation")
        if self.max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be >= 1")
        if self.max_tool_steps < 1:
            raise ValueError("max_tool_steps must be >= 1")
        if self.max_tokens_per_turn < 1:
            raise ValueError("max_tokens_per_turn must be >= 1")
        if self.duplicate_call_limit < 1:
            raise ValueError("duplicate_call_limit must be >= 1")
        if self.tool_timeout_s <= 0:
            raise ValueError("tool_timeout_s must be > 0")
        if self.max_tool_result_chars < 100:
            raise ValueError("max_tool_result_chars must be >= 100")
        if self.max_context_tokens < 1000:
            raise ValueError("max_context_tokens must be >= 1000")
        if self.unguarded_max_tool_rounds < self.max_tool_rounds:
            raise ValueError("unguarded_max_tool_rounds must be >= max_tool_rounds")
        disabled = [
            name for name in (
                "policy_guard", "error_feedback", "context_compression",
                "loop_control", "output_consistency",
            ) if not getattr(self, name)
        ]
        if disabled and self.mode != "evaluation":
            raise ValueError(
                "harness component switches are evaluation-only: " + ", ".join(disabled)
            )

    @classmethod
    def evaluation(cls, **overrides) -> "HarnessConfig":
        overrides.setdefault("mode", "evaluation")
        return cls(**overrides)

    @property
    def tool_round_limit(self) -> int:
        return self.max_tool_rounds if self.loop_control else self.unguarded_max_tool_rounds
