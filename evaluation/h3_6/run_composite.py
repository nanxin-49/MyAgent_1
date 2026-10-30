"""H3-6 deterministic composite runner: per-demand terminal states, no model calls."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from evaluation.fault_injection import FaultInjector, wrap_tools
from evaluation.h2_3.rag_stub import make_rag_tool
from evaluation.h2_3.run_suite import load_cases, principal_for, terminal_state
from evaluation.h3_6.composite import evaluate_demands, summarize_arm
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_FIXTURE = ROOT / "evaluation/h2_3/fixture.json"
DEFAULT_OUT = ROOT / "evaluation/reports/H3-6/composite.json"


def rag_mapping(case: dict) -> dict:
    mapping = {}
    for demand in case.get("demands") or []:
        if (demand.get("kind") == "rag" and demand.get("query")
                and demand.get("rag")):
            mapping[demand["query"]] = demand["rag"]
    return mapping


def action_rows(service) -> list[dict]:
    return [{
        "action_id": action.action_id,
        "action_type": action.action_type.value,
        "order_id": action.order_id,
        "status": action.status.value,
        "error_code": action.error_code,
        "policy_decision": action.policy_decision.decision.value,
        "requested_by": action.requested_by,
    } for action in service._store._actions.values()]


def run_case(case: dict, fixture: dict) -> dict:
    tools, service, backend = isolated_business(fixture, NOW)
    mapping = rag_mapping(case)
    if mapping:
        tools["search_knowledge_base"] = make_rag_tool(mapping)
    injector = FaultInjector(case.get("faults") or [])
    if case.get("faults"):
        tools = wrap_tools(tools, injector)
    model = ScriptedModel(case["scripts"][0])
    runtime = SupportRuntime("scripted", "scripted", client=model)
    runtime.set_shared_tools(tools)
    principal = principal_for(case)
    request = Request(case["message"], principal.customer_id, f"h36-{case['id']}",
                      principal=principal)
    result = asyncio.run(runtime.run(request))
    asyncio.run(runtime.close())
    checks, demands = evaluate_demands(
        case, result.tool_traces, result.response, injector.events)
    terminal = terminal_state(service, backend, runtime.handoff_service)
    terminal["actions"] = action_rows(service)
    return {
        "case_id": case["id"],
        "category": case["category"],
        "source": case.get("source", {}),
        "passed": bool(checks) and all(checks.values()),
        "checks": checks,
        "demand_results": demands,
        "response": result.response,
        "tools_used": result.tools_used,
        "tool_traces": result.tool_traces,
        "steps": result.steps,
        "stop_reason": result.stop_reason,
        "model_calls": len(result.model_calls),
        "fault_events": injector.events,
        "terminal_state": terminal,
        "turns": [{
            "turn": 1,
            "message": case["message"],
            "response": result.response,
            "tool_traces": result.tool_traces,
            "steps": result.steps,
            "stop_reason": result.stop_reason,
            "model_calls": len(result.model_calls),
            "latency_ms": result.latency_ms,
            "fault_events": injector.events,
        }],
    }


def markdown(report: dict) -> str:
    summary = report["summary"]
    lines = ["# H3-6 Composite Deterministic Suite", "",
             f"- cases: {summary['cases']}",
             f"- strict task success: {summary['task_success_rate']}",
             f"- demand completion: {summary['demands_passed']} / {summary['demands']} "
             f"({summary['demand_completion_rate']})",
             f"- demand status: {json.dumps(summary['demand_status_counts'], ensure_ascii=False)}",
             f"- cases with executed violation: {summary['cases_with_executed_violation']}",
             f"- cases with forbidden attempt: {summary['cases_with_forbidden_attempt']}",
             f"- answer overclaim cases: {summary['cases_with_answer_overclaim']}",
             f"- fault recovery: {summary['fault_recovered']} / {summary['fault_cases']}",
             f"- average tool steps: {summary['average_tool_steps']}", "",
             "| Case | Passed | Demands | Completion |", "| --- | --- | --- | --- |"]
    for row in report["cases"]:
        demands = ", ".join(f"{item['id']}={item['status']}"
                            for item in row["demand_results"])
        checks = row["checks"]
        lines.append(f"| {row['case_id']} | {row['passed']} | {demands} | "
                     f"{checks.get('completion')} |")
    failures = [row for row in report["cases"] if not row["passed"]]
    if failures:
        lines += ["", "## Failures", ""]
        for row in failures:
            failed = [name for name, passed in row["checks"].items() if not passed]
            lines.append(f"- {row['case_id']}: {failed}")
    return "\n".join(lines) + "\n"


def run(cases_path: str | Path = DEFAULT_CASES,
        fixture_path: str | Path = DEFAULT_FIXTURE) -> dict:
    _, cases = load_cases(cases_path)
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    results = [run_case(case, fixture) for case in cases]
    report = {
        "schema": "echomind.h3_6.composite_report",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "layer": "deterministic",
        "case_file": str(cases_path),
        "cases": results,
        "summary": summarize_arm(results),
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    report = run(args.cases, args.fixture)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                      encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0 if report["summary"]["cases_with_violation"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
