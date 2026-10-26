"""H2-3 deterministic suite runner: 180 cases, category metrics, no model calls."""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from core.auth import Principal
from core.handoff import HandoffService
from evaluation.agent_trace_eval import score_trajectory
from evaluation.h2_3.rag_stub import make_rag_tool
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_FIXTURE = HERE / "fixture.json"
DEFAULT_OUTPUT = Path("evaluation/reports/H2-3/report.json")


def load_cases(path: str | Path) -> tuple[dict, list[dict]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "echomind.h2_3.cases" or data.get("version") != 1:
        raise ValueError("unsupported H2-3 cases schema")
    return data, data["cases"]


def turns(case: dict) -> list[dict]:
    return case.get("turns") or [case]


def principal_for(case: dict) -> Principal:
    spec = case.get("principal") or {}
    customer = spec.get("customer_id") or "customer-1"
    return Principal(spec.get("subject_id") or f"h23:{customer}", customer,
                     frozenset(spec.get("roles") or ["customer"]))


def terminal_state(service, backend, handoffs) -> dict:
    actions = list(service._store._actions.values())
    last = actions[-1] if actions else None
    return {"executor_calls": len(backend.calls), "handoff_count": len(handoffs._records),
            "action_status": last.status.value if last else None}


def rag_mapping(cases: list[dict]) -> dict[str, dict]:
    mapping = {}
    for case in cases:
        for turn in turns(case):
            spec = (turn.get("expected") or {}).get("rag")
            if spec:
                mapping[turn["message"]] = spec
    return mapping


def run_case(case: dict, service, backend, tools: dict) -> dict:
    handoffs = HandoffService()
    principal = principal_for(case)
    context = ""
    all_checks: dict[str, bool] = {}
    turn_results = []
    for index, turn in enumerate(turns(case), 1):
        model = ScriptedModel(turn["scripts"][0])
        runtime = SupportRuntime("scripted", "scripted", client=model)
        runtime.handoff_service = handoffs
        runtime.set_shared_tools(tools)
        request = Request(turn["message"], principal.customer_id, f"h23-{case['id']}",
                          context=context, principal=principal)
        result = asyncio.run(runtime.run(request))
        asyncio.run(runtime.close())
        current = terminal_state(service, backend, handoffs)
        checks = score_trajectory(result.tool_traces, turn.get("expected") or {},
                                  current, answer=result.response)
        for name, value in checks.items():
            all_checks[f"turn{index}.{name}"] = value
        turn_results.append({
            "turn": index, "message": turn["message"], "response": result.response,
            "tools_used": result.tools_used, "tool_traces": result.tool_traces,
            "terminal_state": current, "checks": checks,
        })
        context = (context + "\n" if context else "") + f"用户: {turn['message']}\n助手: {result.response}"
    final = terminal_state(service, backend, handoffs)
    return {
        "case_id": case["id"], "category": case["category"],
        "passed": bool(all_checks) and all(all_checks.values()),
        "checks": all_checks, "turns": turn_results, "terminal_state": final,
        "source": case.get("source", {}),
    }


def aggregate(results: list[dict]) -> dict:
    categories: dict[str, dict] = defaultdict(lambda: {
        "cases": 0, "passed": 0, "forbidden_checks": 0, "forbidden_failures": 0,
        "safety_violations": 0, "refusal_cases": 0, "refusal_passes": 0,
        "citation_checks": 0, "citation_passes": 0,
        "terminal_checks": 0, "terminal_passes": 0,
    })
    failures: dict[str, Counter] = defaultdict(Counter)
    for item in results:
        cat = item["category"]
        group = categories[cat]
        group["cases"] += 1
        group["passed"] += int(item["passed"])
        for name, passed in item["checks"].items():
            short = name.split(".", 1)[-1]
            if short == "forbidden_tools":
                group["forbidden_checks"] += 1
                if not passed:
                    group["forbidden_failures"] += 1
                    group["safety_violations"] += 1
            if short == "terminal_state":
                group["terminal_checks"] += 1
                group["terminal_passes"] += int(passed)
            if short in {"citation", "citation_absent"}:
                group["citation_checks"] += 1
                group["citation_passes"] += int(passed)
            if short == "answer_contains" and cat in {"out_of_scope", "injection"}:
                group["refusal_cases"] += 1
                group["refusal_passes"] += int(passed)
            if not passed:
                failures[cat][short] += 1
    report = {}
    for cat, group in sorted(categories.items()):
        cases = group["cases"]
        report[cat] = {
            "case_count": cases,
            "task_success_rate": round(group["passed"] / cases, 4) if cases else None,
            "forbidden_call_rate": round(group["forbidden_failures"] / group["forbidden_checks"], 4)
            if group["forbidden_checks"] else None,
            "safety_violation_rate": round(group["safety_violations"] / cases, 4) if cases else None,
            "refusal_rate": round(group["refusal_passes"] / group["refusal_cases"], 4)
            if group["refusal_cases"] else None,
            "citation_accuracy": round(group["citation_passes"] / group["citation_checks"], 4)
            if group["citation_checks"] else None,
            "terminal_state_accuracy": round(group["terminal_passes"] / group["terminal_checks"], 4)
            if group["terminal_checks"] else None,
            "tool_selection_accuracy": None,
            "argument_accuracy": None,
            "latency_p50_ms": None,
            "latency_p95_ms": None,
            "tokens_per_case": None,
            "cost_per_case_usd": None,
        }
    overall_cases = len(results)
    overall_passed = sum(item["passed"] for item in results)
    overall = {
        "case_count": overall_cases,
        "task_success_rate": round(overall_passed / overall_cases, 4) if overall_cases else None,
        "safety_violation_rate": round(sum(1 for item in results if any(
            name.split(".", 1)[-1] == "forbidden_tools" and not value
            for name, value in item["checks"].items())) / overall_cases, 4) if overall_cases else None,
        "model_metrics": "deferred_to_real_model",
    }
    return {"overall": overall, "categories": report,
            "failures": {cat: dict(counter) for cat, counter in failures.items()}}


def markdown(report: dict) -> str:
    lines = ["# H2-3 Deterministic Suite", "",
             f"- cases: {report['overall']['case_count']}",
             f"- task success: {report['overall']['task_success_rate']}",
             f"- safety violation: {report['overall']['safety_violation_rate']}",
             f"- real model layer: {report['real_model_layer']}", "",
             "| Category | Cases | Task success | Forbidden | Safety | Refusal | Citation | Terminal |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for cat, row in report["categories"].items():
        lines.append(f"| {cat} | {row['case_count']} | {row['task_success_rate']} | "
                     f"{row['forbidden_call_rate']} | {row['safety_violation_rate']} | "
                     f"{row['refusal_rate']} | {row['citation_accuracy']} | "
                     f"{row['terminal_state_accuracy']} |")
    if report["failures"]:
        lines += ["", "## Failures", ""]
        for cat, counts in report["failures"].items():
            lines.append(f"- {cat}: {counts}")
    return "\n".join(lines) + "\n"


def run(cases_path: str | Path = DEFAULT_CASES,
        fixture_path: str | Path = DEFAULT_FIXTURE) -> dict:
    _, cases = load_cases(cases_path)
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    mapping = rag_mapping(cases)
    results = []
    for case in cases:
        tools, service, backend = isolated_business(fixture, NOW)
        tools["search_knowledge_base"] = make_rag_tool(mapping)
        results.append(run_case(case, service, backend, tools))
    report = {
        "schema": "echomind.h2_3.report", "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "layer": "deterministic", "real_model_layer": "deferred_pending_budget",
        "case_file": str(cases_path), "cases": results,
    }
    report.update(aggregate(results))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    report = run(args.cases, args.fixture)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0 if (report["overall"]["safety_violation_rate"] or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
