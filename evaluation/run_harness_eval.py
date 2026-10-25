"""H2-2 runner: replay, fault injection, trajectory scoring, pass@runs/pass^runs."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from core.auth import Principal
from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from evaluation.agent_trace_eval import score_trajectory
from evaluation.fault_injection import FaultInjector, wrap_tools
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel, from_trajectory
from evaluation.system_eval import SystemEvalCase, evaluate_system
from evaluation.topology_experiment import isolated_business

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_CASES = Path(__file__).with_name("cases") / "h2_2_cases.json"


def _load_cases(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("case file must contain a non-empty cases list")
    return cases


def _principal(case: dict) -> Principal:
    spec = case.get("principal") or {}
    customer = spec.get("customer_id") or case.get("user_id") or "customer-1"
    return Principal(spec.get("subject_id") or f"eval:{customer}", customer,
                     frozenset(spec.get("roles") or ["customer"]))


def _terminal_state(service, backend, runtime) -> dict:
    actions = list(service._store._actions.values())
    last = actions[-1] if actions else None
    data = service._business_backend.state.data
    order_id = "ORD-1001"
    return {
        "executor_calls": len(backend.calls),
        "handoff_count": len(runtime.handoff_service._records),
        "action_status": last.status.value if last else None,
        "order_status": (data.get("orders") or {}).get(order_id, {}).get("status"),
        "refund_statuses": sorted(str(r.get("status")) for r in (data.get("refunds") or {}).values()),
    }


def _model_for_run(case: dict, run: int):
    if case.get("trajectory"):
        return from_trajectory(case["trajectory"])
    scripts = case.get("scripts") or []
    if not scripts:
        raise ValueError(f"case {case.get('id')} has neither scripts nor trajectory")
    script = scripts[(run - 1) % len(scripts)]
    return ScriptedModel(script, model="scripted")


def run_case(case: dict, run: int, fixture: dict) -> dict:
    tools, service, backend = isolated_business(fixture, NOW)
    injector = FaultInjector(case.get("faults") or [])
    if case.get("faults"):
        tools = wrap_tools(tools, injector)
    model = _model_for_run(case, run)
    runtime = SupportRuntime("scripted", "scripted", client=model)
    runtime.set_shared_tools(tools)
    principal = _principal(case)
    request = Request(case.get("message") or "", principal.customer_id, f"h2-2-{case['id']}-{run}",
                      principal=principal)
    result = asyncio.run(runtime.run(request))
    terminal = _terminal_state(service, backend, runtime)
    checks = score_trajectory(result.tool_traces, case.get("expected") or {}, terminal)
    passed = bool(checks) and all(checks.values())
    return {
        "case_id": case["id"],
        "run": run,
        "response": result.response,
        "tools_used": result.tools_used,
        "tool_traces": result.tool_traces,
        "model_calls": len(result.model_calls),
        "terminal_state": terminal,
        "fault_events": injector.events,
        "checks": checks,
        "passed": passed,
    }


def summarize(runs: list[dict], baseline: dict | None = None) -> dict:
    cases = []
    for item in runs:
        observed = {
            "checks": item["checks"],
            "passed": item["passed"],
            "run": item["run"],
            "trajectory_match": item["checks"].get("trajectory"),
            "forbidden_call": not item["checks"].get("forbidden_tools", True),
            "terminal_state": item["terminal_state"],
            "fault_events": item["fault_events"],
        }
        cases.append(SystemEvalCase(
            item["case_id"], "tool", {"tools": [], "tool": None},
            observed, mode="harness_eval", run=item["run"]))
    report = evaluate_system(cases, baseline=baseline)
    return {"runs": runs, "metrics": report["metrics"],
            "pass_metrics": report["pass_metrics"], "regressions": report["regressions"]}


def _markdown(report: dict) -> str:
    lines = ["# H2-2 Harness Eval Summary", "",
             "| Case | Runs | Passes | pass@runs | pass^runs |",
             "| --- | ---: | ---: | --- | --- |"]
    for row in report["pass_metrics"]["cases"]:
        lines.append(f"| {row['case_id']} | {row['runs']} | {row['passes']} | "
                     f"{row['pass@runs']} | {row['pass^runs']} |")
    pm = report["pass_metrics"]
    lines += ["", f"- pass@runs: {pm['pass@runs']['value']} "
                    f"({pm['pass@runs']['numerator']}/{pm['pass@runs']['denominator']})",
              f"- pass^runs: {pm['pass^runs']['value']} "
              f"({pm['pass^runs']['numerator']}/{pm['pass^runs']['denominator']})"]
    tool = report.get("metrics", {}).get("tool", {})
    for name in ("trajectory_accuracy", "forbidden_call_rate"):
        item = tool.get(name) or {}
        lines.append(f"- {name}: {item.get('value')} "
                     f"({item.get('numerator')}/{item.get('denominator')})")
    if report.get("regressions"):
        lines.append(f"- regressions: {report['regressions']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--baseline", default=None)
    args = parser.parse_args(argv)
    cases = _load_cases(args.cases)
    baseline = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8")).get("metrics")
    fixture = prepare(NOW)[0]
    runs = []
    for case in cases:
        count = args.runs or len(case.get("scripts") or [1])
        for run in range(1, count + 1):
            runs.append(run_case(case, run, fixture))
    report = summarize(runs, baseline)
    markdown = _markdown(report)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        output.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0 if not report["regressions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
