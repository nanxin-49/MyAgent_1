"""H2-4 entry point: run the H2-3 180-case suite with the bare harness profile.

Defaults: bare profile, 180 cases x 1 run, hard cap 700 requests / USD 1.0.
Real model calls require explicit budget authorization before running.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluation.h2_3 import real_model

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "evaluation/reports/H2-4/bare"
DEFAULT_MAX_REQUESTS = "700"
DEFAULT_MAX_USD = "1.0"


def _has_flag(argv: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(name + "=") for arg in argv)


def _flag_value(argv: list[str], name: str, default: str) -> str:
    for index, arg in enumerate(argv):
        if arg == name and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return default


def build_argv(argv: list[str]) -> list[str]:
    argv = list(argv)
    defaults = []
    if not _has_flag(argv, "--profile"):
        defaults += ["--profile", "bare"]
    if not _has_flag(argv, "--output-dir"):
        defaults += ["--output-dir", str(DEFAULT_OUT)]
    if not _has_flag(argv, "--max-requests"):
        defaults += ["--max-requests", DEFAULT_MAX_REQUESTS]
    if not _has_flag(argv, "--max-usd"):
        defaults += ["--max-usd", DEFAULT_MAX_USD]
    if not _has_flag(argv, "--no-key-runs"):
        defaults += ["--no-key-runs"]
    return argv + defaults


def summary_markdown(report: dict) -> str:
    metrics = report.get("baseline_metrics") or {}
    overall = report.get("overall") or {}
    lines = ["# H2-4 Bare Baseline (model + tools)", "",
             f"- profile: {report.get('profile')}",
             f"- model: {report.get('model')}",
             f"- harness: {json.dumps(report.get('harness') or {}, ensure_ascii=False)}",
             f"- case_runs: {overall.get('case_runs')}",
             f"- task_success_rate: {overall.get('task_success_rate')}",
             f"- policy_blocked_attempts: {metrics.get('policy_blocked_attempts')} "
             f"(cases: {metrics.get('cases_with_policy_blocked')})",
             f"- executed_violations: {metrics.get('executed_violations')} "
             f"(cases: {metrics.get('cases_with_executed_violation')})",
             f"- approval_required_attempts: {metrics.get('approval_required_attempts')}",
             f"- overclaim_cases: {metrics.get('overclaim_cases')} "
             f"({metrics.get('overclaim_rate')}; {metrics.get('overclaim_scope')})",
             f"- loop_truncated: {metrics.get('loop_truncated')}",
             f"- model_calls p50/p95: {metrics.get('model_calls_p50')} / "
             f"{metrics.get('model_calls_p95')}",
             f"- turns over 3 rounds: {metrics.get('turns_over_three_rounds')} / "
             f"{metrics.get('turns')}",
             f"- requests/cost: {overall.get('model_requests')} / USD "
             f"{overall.get('cost_usd')} (cap {overall.get('budget_max_requests')} / "
             f"USD {overall.get('budget_max_usd')})",
             f"- latency p50/p95: {overall.get('latency_p50_ms')} / "
             f"{overall.get('latency_p95_ms')} ms",
             f"- halted: {overall.get('halted')}"]
    if overall.get("note"):
        lines.append(f"- note: {overall['note']}")
    lines += ["",
              "| Category | Cases | Task success | Policy blocked | Executed violations | Overclaims |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for category, row in (metrics.get("categories") or {}).items():
        lines.append(f"| {category} | {row['case_count']} | {row['task_success_rate']} | "
                     f"{row['policy_blocked_attempts']} | {row['executed_violation_cases']} | "
                     f"{row['overclaim_cases']} |")
    failures = metrics.get("failure_distribution") or {}
    if failures:
        lines += ["", "## Failure distribution", ""]
        for category, counts in failures.items():
            lines.append(f"- {category}: {counts}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = build_argv(list(sys.argv[1:] if argv is None else argv))
    output_dir = Path(_flag_value(argv, "--output-dir", str(DEFAULT_OUT)))
    rc = real_model.main(argv)
    report_path = output_dir / "report.json"
    if not report_path.exists():
        report_path = output_dir / "final.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary_path = output_dir / "SUMMARY.md"
        summary_path.write_text(summary_markdown(report), encoding="utf-8")
        print(f"summary written to {summary_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
