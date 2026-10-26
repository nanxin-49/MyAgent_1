"""Rebuild an H2-4 summary from details.jsonl. Offline; makes no model calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.h2_4.metrics import summarize_baseline
from evaluation.h2_4.run_baseline import summary_markdown

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "evaluation/reports/H2-4/bare"


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1))))
    return round(ordered[index], 1)


def usage_from_log(log_path: Path, ledger_path: Path, *, run: int = 1) -> dict:
    """Attribute requests/tokens/cost to one run index using log + ledger order."""
    events = json.loads(ledger_path.read_text(encoding="utf-8"))["events"]
    indices: set[int] = set()
    previous = 0
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith('{"case"'):
            continue
        row = json.loads(line)
        end = int(row["requests"])
        if end < previous:  # defensive: a fresh ledger restarts the counter
            previous = end
        if int(row.get("run", 1)) == run:
            indices.update(range(previous, end))
        previous = end
    selected = [events[index] for index in sorted(indices) if index < len(events)]
    return {
        "requests": len(selected),
        "input_tokens": sum(int(event.get("input_tokens") or 0) for event in selected),
        "output_tokens": sum(int(event.get("output_tokens") or 0) for event in selected),
        "cost_usd": round(sum(float(event.get("cost_usd") or 0) for event in selected), 8),
    }


def build_report(final: dict | None, details: list[dict], *, run: int | None = 1,
                 usage: dict | None = None) -> dict:
    rows = details if run is None else [row for row in details
                                        if int(row.get("run", 1)) == run]
    metrics = summarize_baseline(
        rows, loop_truncated=sum(1 for row in rows if row.get("loop_truncated")))
    latencies = [turn.get("latency_ms") or 0 for row in rows
                 for turn in row.get("turns") or []]
    overall = dict((final or {}).get("overall") or {})
    overall.update({
        "case_runs": len(rows),
        "task_success_rate": metrics["task_success_rate"],
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "safety_scope": (f"all_detailed_runs_run_{run}" if run is not None
                         else "all_detailed_runs"),
    })
    if usage:
        overall.update({"model_requests": usage["requests"],
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                        "cost_usd": usage["cost_usd"]})
    if run is not None:
        overall["halted"] = False
        overall["note"] = ("filtered run view; ledger-wide halt status applies to all runs")
    return {
        "profile": (final or {}).get("profile"),
        "model": (final or {}).get("model"),
        "harness": (final or {}).get("harness"),
        "overall": overall,
        "baseline_metrics": metrics,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--details", default=str(DEFAULT_DIR / "details.jsonl"))
    parser.add_argument("--report", default=str(DEFAULT_DIR / "final.json"))
    parser.add_argument("--log", default=str(DEFAULT_DIR / "run.log"))
    parser.add_argument("--ledger", default=str(DEFAULT_DIR / "ledger.json"))
    parser.add_argument("--out", default=str(DEFAULT_DIR / "FIRST_PASS.md"))
    parser.add_argument("--run", type=int, default=1,
                        help="0 keeps every run; default 1 = headline first pass")
    args = parser.parse_args(argv)
    details = [json.loads(line) for line in
               Path(args.details).read_text(encoding="utf-8").splitlines() if line.strip()]
    report_path = Path(args.report)
    final = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    usage = None
    if args.run and Path(args.log).exists() and Path(args.ledger).exists():
        usage = usage_from_log(Path(args.log), Path(args.ledger), run=args.run)
    report = build_report(final, details, run=args.run or None, usage=usage)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(summary_markdown(report), encoding="utf-8")
    print(f"summary written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
