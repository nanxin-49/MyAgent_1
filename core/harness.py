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
    unguarded_max_tool_rounds: int = 1000
    mode: str = "production"

    def __post_init__(self):
        if self.mode not in {"production", "evaluation"}:
            raise ValueError("mode must be production or evaluation")
        if self.max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be >= 1")
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
