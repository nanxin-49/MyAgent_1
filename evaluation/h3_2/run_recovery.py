"""H3-2 runner: compare fault recovery with error_feedback on vs off.

Deterministic probe model only. This measures the information channel, not
real-model recovery quality; that comparison belongs to H3-6.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from core.auth import Principal
from core.harness import HarnessConfig
from evaluation.agent_trace_eval import score_trajectory
from evaluation.fault_injection import FaultInjector, wrap_tools
from evaluation.h3_2.recovery_model import RecoveryModel
from evaluation.prepare_online_eval import prepare
from evaluation.topology_experiment import isolated_business

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUT = ROOT / "evaluation/reports/H3-2/recovery.json"
PROFILE = Principal("h32:customer-1", "customer-1", frozenset({"customer"}))


def load_cases(path: str | Path = DEFAULT_CASES) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "cartcare.h3_2.recovery_cases" or data.get("version") != 1:
        raise ValueError("unsupported H3-2 recovery case schema")
    return data["cases"]


def _terminal_state(service, backend, runtime) -> dict:
    actions = list(service._store._actions.values())
    last = actions[-1] if actions else None
    return {
        "executor_calls": len(backend.calls),
        "handoff_count": len(runtime.handoff_service._records),
        "action_status": last.status.value if last else None,
    }


def run_case(case: dict, fixture: dict, harness: HarnessConfig) -> dict:
    tools, service, backend = isolated_business(fixture, NOW)
    injector = FaultInjector(case.get("faults") or [])
    if case.get("faults"):
        tools = wrap_tools(tools, injector)
    model = RecoveryModel(case)
    runtime = SupportRuntime("probe", "probe", client=model, harness=harness)
    runtime.set_shared_tools(tools)
    request = Request(case["message"], PROFILE.customer_id, f"h32-{case['id']}",
                      principal=PROFILE)
    result = asyncio.run(runtime.run(request))
    terminal = _terminal_state(service, backend, runtime)
    checks = score_trajectory(result.tool_traces, case["expected"], terminal,
                              answer=result.response)
    payload = model.seen_payloads[0] if model.seen_payloads else None
    return {
        "case_id": case["id"],
        "category": case["category"],
        "recovered": bool(checks) and all(checks.values()),
        "checks": checks,
        "response": result.response,
        "tools_used": result.tools_used,
        "terminal_state": terminal,
        "model_visible_payload": json.dumps(payload, ensure_ascii=False)[:600]
        if payload is not None else None,
        "fault_events": injector.events,
    }


def evaluate(cases_path: str | Path = DEFAULT_CASES) -> dict:
    cases = load_cases(cases_path)
    fixture = prepare(NOW)[0]
    arms = {}
    for name, harness in (
        ("on", HarnessConfig()),
        ("off", HarnessConfig.evaluation(error_feedback=False)),
    ):
        rows = [run_case(case, fixture, harness) for case in cases]
        arms[name] = {
            "cases": rows,
            "recovery_rate": round(sum(row["recovered"] for row in rows) / len(rows), 4)
            if rows else None,
            "executed_violations": sum(row["terminal_state"]["executor_calls"] for row in rows),
        }
    return {
        "schema": "cartcare.h3_2.recovery_report",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "layer": "deterministic_probe",
        "model": "recovery-probe (acts only on structured error fields)",
        "note": ("Deterministic information-channel comparison, not real-model "
                 "quality. Real-model recovery is deferred to H3-6."),
        "arms": arms,
    }


def markdown(report: dict) -> str:
    lines = ["# H3-2 Structured Error Recovery (deterministic probe)", "",
             f"- model: {report['model']}",
             f"- note: {report['note']}", "",
             "| Case | on: recovered | off: recovered | on tools | off tools |",
             "| --- | --- | --- | ---: | ---: |"]
    on = {row["case_id"]: row for row in report["arms"]["on"]["cases"]}
    off = {row["case_id"]: row for row in report["arms"]["off"]["cases"]}
    for case_id, row in on.items():
        other = off[case_id]
        lines.append(f"| {case_id} | {row['recovered']} | {other['recovered']} | "
                     f"{len(row['tools_used'])} | {len(other['tools_used'])} |")
    for name in ("on", "off"):
        arm = report["arms"][name]
        lines.append(f"- {name}: recovery_rate={arm['recovery_rate']}, "
                     f"executor_calls={arm['executed_violations']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    report = evaluate(args.cases)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                      encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0 if report["arms"]["off"]["executed_violations"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
