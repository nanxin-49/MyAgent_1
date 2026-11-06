"""H3-3 runner: compare context compression on/off on deterministic cases.

Deterministic scripts do not react to context, so success equality only proves
the compressed path does not break the chain; quality impact on a real model is
left to H3-6.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import make_tool
from core.auth import Principal
from core.harness import HarnessConfig
from evaluation.agent_trace_eval import score_trajectory
from evaluation.prepare_online_eval import prepare
from evaluation.scripted_model import ScriptedModel
from evaluation.topology_experiment import isolated_business

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUT = ROOT / "evaluation/reports/H3-3/context_budget.json"


def load_cases(path: str | Path = DEFAULT_CASES) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "cartcare.h3_3.context_cases" or data.get("version") != 1:
        raise ValueError("unsupported H3-3 context case schema")
    return data["cases"]


def _context_text(chars: int) -> str:
    if chars <= 0:
        return ""
    return ("历史对话内容，仅供引用。" * ((chars // 12) + 1))[:chars]


def _tools(fixture: dict):
    tools, service, backend = isolated_business(fixture, NOW)
    tools["big"] = make_tool("big", "返回大结果的测试工具", {}, lambda req, args: {
        "success": True, "data": {"blob": "x" * 3000}})
    tools["rag_like"] = make_tool("rag_like", "返回长检索片段的测试工具", {}, lambda req, args: {
        "success": True, "retrieval_status": "usable",
        "results": [{"document_id": "refund", "content": "退款政策说明。" * 500}],
        "citations": [{"document_id": "refund", "reference": "refund#1"}]})
    return tools, service, backend


def _terminal_state(service, backend) -> dict:
    actions = list(service._store._actions.values())
    last = actions[-1] if actions else None
    return {"executor_calls": len(backend.calls),
            "action_status": last.status.value if last else None}


def run_case(case: dict, fixture: dict, harness: HarnessConfig) -> dict:
    tools, service, backend = _tools(fixture)
    model = ScriptedModel(case["scripts"][0])
    runtime = SupportRuntime("scripted", "scripted", client=model, harness=harness)
    runtime.set_shared_tools(tools)
    principal = Principal("h33:customer-1", "customer-1", frozenset({"customer"}))
    request = Request(case["message"], principal.customer_id, f"h33-{case['id']}",
                      context=_context_text(int(case.get("context_chars") or 0)),
                      principal=principal)
    result = asyncio.run(runtime.run(request))
    terminal = _terminal_state(service, backend)
    checks = score_trajectory(result.tool_traces, case["expected"], terminal)
    rounds = result.context_rounds
    return {
        "case_id": case["id"],
        "passed": bool(checks) and all(checks.values()),
        "checks": checks,
        "tools_used": result.tools_used,
        "terminal_state": terminal,
        "estimated_tokens": sum(row["estimated_tokens"]["total"] for row in rounds),
        "compressed_rounds": sum(1 for row in rounds if row["compressed"]),
        "over_budget_rounds": sum(1 for row in rounds if row["over_budget"]),
        "context_rounds": rounds,
    }


def evaluate(cases_path: str | Path = DEFAULT_CASES) -> dict:
    cases = load_cases(cases_path)
    fixture = prepare(NOW)[0]
    arms = {}
    for name, harness in (
        ("on", HarnessConfig(max_context_tokens=4000)),
        ("off", HarnessConfig.evaluation(context_compression=False,
                                         max_context_tokens=4000)),
    ):
        rows = [run_case(case, fixture, harness) for case in cases]
        arms[name] = {
            "cases": rows,
            "task_success_rate": round(sum(row["passed"] for row in rows) / len(rows), 4)
            if rows else None,
            "estimated_tokens": sum(row["estimated_tokens"] for row in rows),
            "compressed_rounds": sum(row["compressed_rounds"] for row in rows),
            "over_budget_rounds": sum(row["over_budget_rounds"] for row in rows),
            "executor_calls": sum(row["terminal_state"]["executor_calls"] for row in rows),
        }
    return {
        "schema": "cartcare.h3_3.context_report",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "layer": "deterministic",
        "budget_tokens": 4000,
        "note": ("Estimated tokens (ASCII/4 + non-ASCII chars), not tokenizer output. "
                 "Deterministic scripts do not react to context; success equality only "
                 "shows the compressed path is intact. Real-model quality is H3-6."),
        "arms": arms,
    }


def markdown(report: dict) -> str:
    lines = ["# H3-3 Context Budget Comparison", "",
             f"- budget: {report['budget_tokens']} estimated tokens",
             f"- note: {report['note']}", "",
             "| Case | on success | off success | on tokens | off tokens | on compressed rounds |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    on = {row["case_id"]: row for row in report["arms"]["on"]["cases"]}
    off = {row["case_id"]: row for row in report["arms"]["off"]["cases"]}
    for case_id, row in on.items():
        other = off[case_id]
        lines.append(f"| {case_id} | {row['passed']} | {other['passed']} | "
                     f"{row['estimated_tokens']} | {other['estimated_tokens']} | "
                     f"{row['compressed_rounds']} |")
    for name in ("on", "off"):
        arm = report["arms"][name]
        lines.append(f"- {name}: success={arm['task_success_rate']}, "
                     f"tokens={arm['estimated_tokens']}, "
                     f"compressed_rounds={arm['compressed_rounds']}, "
                     f"over_budget_rounds={arm['over_budget_rounds']}, "
                     f"executor_calls={arm['executor_calls']}")
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
    on, off = report["arms"]["on"], report["arms"]["off"]
    return 0 if on["task_success_rate"] == 1.0 and on["executor_calls"] == off["executor_calls"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
