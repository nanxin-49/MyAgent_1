"""H2-3 real-model layer: real DeepSeek calls, budget ledger, pass^k.

Run only with explicit budget authorization. The script is serial, writes a
JSONL progress file after every turn, and stops at the hard request/USD cap.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from anthropic import (APIConnectionError, APITimeoutError, AsyncAnthropic,
                       RateLimitError)
from dotenv import load_dotenv

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import build_shared_rag_tools
from core.handoff import HandoffService
from core.harness import HarnessConfig
from evaluation.agent_trace_eval import score_trajectory
from evaluation.h2_3.run_suite import (DEFAULT_CASES, DEFAULT_FIXTURE, load_cases,
                                       terminal_state, turns)
from evaluation.h2_4.metrics import summarize_baseline
from evaluation.h2_4.profile import harness_for_profile
from evaluation.scripted_model import ScriptedModel  # noqa: F401  (test seams)
from evaluation.topology_experiment import isolated_business
from mcp.knowledge_base import KnowledgeBase
from mcp.tool_manager import MCPToolManager, Tool
from core.tool_contract import RetryPolicy

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
DEFAULT_OUT = ROOT / "evaluation/reports/H2-3/real"


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, path: Path, *, max_requests: int, max_usd: float):
        self.path = path
        self.max_requests = max_requests
        self.max_usd = max_usd
        self.requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.halted = False
        self.events = []

    @classmethod
    def load(cls, path: Path, *, max_requests: int, max_usd: float) -> "BudgetLedger":
        data = json.loads(path.read_text(encoding="utf-8"))
        ledger = cls(path, max_requests=max_requests, max_usd=max_usd)
        ledger.requests = int(data.get("requests", 0))
        ledger.input_tokens = int(data.get("input_tokens", 0))
        ledger.output_tokens = int(data.get("output_tokens", 0))
        ledger.cost_usd = float(data.get("cost_usd", 0.0))
        ledger.halted = bool(data.get("halted", False))
        ledger.events = list(data.get("events") or [])
        return ledger

    def before(self):
        if self.halted or self.requests >= self.max_requests or self.cost_usd >= self.max_usd:
            self.halted = True
            self.save()
            raise BudgetExceeded("model budget exhausted")

    def after(self, response):
        usage = getattr(response, "usage", None)
        inp = sum(int(getattr(usage, key, 0) or 0) for key in (
            "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        out = int(getattr(usage, "output_tokens", 0) or 0)
        cost = (inp * 0.30 + out * 1.20) / 1_000_000
        self.requests += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.cost_usd += cost
        self.events.append({"number": self.requests, "input_tokens": inp, "output_tokens": out,
                            "cost_usd": cost, "at": datetime.now(timezone.utc).isoformat()})
        if self.requests >= self.max_requests or self.cost_usd >= self.max_usd:
            self.halted = True
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "requests": self.requests, "max_requests": self.max_requests,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 8), "max_usd": self.max_usd,
            "halted": self.halted, "events": self.events,
        }, ensure_ascii=False, indent=2), encoding="utf-8")


class BudgetedClient:
    def __init__(self, inner, ledger: BudgetLedger):
        self._inner = inner
        self._ledger = ledger
        self.messages = self

    async def create(self, **kwargs):
        retryable = (httpx.TransportError, httpx.TimeoutException,
                     APIConnectionError, APITimeoutError, RateLimitError)
        for attempt in (1, 2):
            try:
                # Throttle to avoid burst rate limiting on the demo endpoint.
                await asyncio.sleep(0.6)
                self._ledger.before()
                extra = dict(kwargs.get("extra_body") or {})
                extra.setdefault("thinking", {"type": "disabled"})
                kwargs["extra_body"] = extra
                response = await self._inner.messages.create(**kwargs)
                self._ledger.after(response)
                return response
            except BudgetExceeded:
                raise
            except retryable:
                if attempt == 2:
                    raise
                await asyncio.sleep(2.0)

    async def close(self):
        return await self._inner.close()


def knowledge_tool(kb: KnowledgeBase) -> Tool:
    return Tool(
        name="knowledge_search",
        description="搜索知识库（真实 Chroma HTTP）",
        handler=kb.search_handler,
        schema={"type": "object",
                "properties": {"query": {"type": "string", "minLength": 1},
                               "top_k": {"type": "integer"}},
                "required": ["query"], "additionalProperties": False},
        cache_ttl=0.0,
        supports_rerank=True,
        retry_policy=RetryPolicy(max_attempts=2),
    )


def build_manager(api_key: str, base_url: str, model: str, budgeted, kb: KnowledgeBase):
    manager = MCPToolManager(api_key=api_key, base_url=base_url, model=model)
    manager._client = budgeted
    manager.register(knowledge_tool(kb))
    return manager


def run_turn(runtime, turn, principal, context, case_id):
    request = Request(turn["message"], principal.customer_id, f"h23-real-{case_id}",
                      context=context, principal=principal)
    return asyncio.run(runtime.run(request))


def score_case(case: dict, fixture: dict, *, api_key: str, base_url: str, model: str,
               budgeted, kb: KnowledgeBase, harness: HarnessConfig | None = None):
    from evaluation.h2_3.run_suite import principal_for
    principal = principal_for(case)
    handoffs = HandoffService()
    context = ""
    all_checks: dict[str, bool] = {}
    turn_rows = []
    loop_truncated = False
    for index, turn in enumerate(turns(case), 1):
        tools, service, backend = isolated_business(fixture, NOW, harness=harness)
        manager = build_manager(api_key, base_url, model, budgeted, kb)
        tools.update(build_shared_rag_tools(manager))
        runtime = SupportRuntime(api_key, model, base_url, client=budgeted, harness=harness)
        runtime.handoff_service = handoffs
        runtime.set_shared_tools(tools)
        start = time.monotonic()
        turn_error = None
        expected = dict(turn.get("expected_agent") or turn.get("expected") or {})
        forbidden = list(expected.get("forbidden_tools") or [])
        try:
            result = run_turn(runtime, turn, principal, context, case["id"])
        except Exception as exc:  # keep evidence when the tool loop aborts
            result = None
            turn_error = f"{type(exc).__name__}: {exc}"
            loop_truncated = loop_truncated or "最大轮数" in turn_error
        latency = round((time.monotonic() - start) * 1000, 1)
        current = terminal_state(service, backend, handoffs)
        if result is None:
            checks = {"turn_error": False}
            response_text = ""
            tools_used, tool_traces, model_calls = [], [], 0
        else:
            reference = expected.pop("citation", None)
            if reference:
                expected["citation_document_id"] = str(reference).split("#", 1)[0]
            checks = score_trajectory(result.tool_traces, expected, current,
                                      answer=result.response)
            response_text = result.response
            tools_used, tool_traces = result.tools_used, result.tool_traces
            model_calls = len(result.model_calls)
        for name, value in checks.items():
            all_checks[f"turn{index}.{name}"] = value
        turn_rows.append({
            "turn": index, "message": turn["message"], "response": response_text,
            "tools_used": tools_used, "tool_traces": tool_traces,
            "terminal_state": current, "checks": checks, "latency_ms": latency,
            "model_calls": model_calls, "error": turn_error,
            "forbidden_tools": forbidden,
        })
        context = (context + "\n" if context else "") + f"用户: {turn['message']}\n助手: {response_text}"
    return {
        "case_id": case["id"], "category": case["category"],
        "passed": bool(all_checks) and all(all_checks.values()),
        "checks": all_checks, "turns": turn_rows,
        "terminal_state": terminal_state(service, backend, handoffs),
        "latency_ms": round(sum(row["latency_ms"] for row in turn_rows), 1),
        "model_calls": sum(row["model_calls"] for row in turn_rows),
        "loop_truncated": loop_truncated,
        "source": case.get("source", {}),
    }


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, int(round((p / 100) * (len(values) - 1))))
    return round(values[index], 1)


def aggregate(results, ledger: BudgetLedger, key_results: list[dict]) -> dict:
    categories: dict[str, dict] = defaultdict(lambda: {
        "cases": 0, "passed": 0, "forbidden_checks": 0, "forbidden_failures": 0,
        "safety_violations": 0, "refusal_cases": 0, "refusal_passes": 0,
        "citation_checks": 0, "citation_passes": 0,
        "trajectory_checks": 0, "trajectory_passes": 0,
        "argument_checks": 0, "argument_passes": 0,
    })
    for item in results:
        group = categories[item["category"]]
        group["cases"] += 1
        group["passed"] += int(item["passed"])
        for name, passed in item["checks"].items():
            short = name.split(".", 1)[-1]
            if short == "forbidden_tools":
                group["forbidden_checks"] += 1
                if not passed:
                    group["forbidden_failures"] += 1
                    group["safety_violations"] += 1
            if short == "trajectory":
                group["trajectory_checks"] += 1
                group["trajectory_passes"] += int(passed)
            if short.startswith("key_args:"):
                group["argument_checks"] += 1
                group["argument_passes"] += int(passed)
            if short in {"citation", "citation_absent"}:
                group["citation_checks"] += 1
                group["citation_passes"] += int(passed)
            if short == "answer_contains" and item["category"] in {"out_of_scope", "injection"}:
                group["refusal_cases"] += 1
                group["refusal_passes"] += int(passed)
    rows = {}
    for cat, group in sorted(categories.items()):
        cases = group["cases"]
        rows[cat] = {
            "case_count": cases,
            "task_success_rate": round(group["passed"] / cases, 4) if cases else None,
            "tool_selection_accuracy": round(group["trajectory_passes"] / group["trajectory_checks"], 4)
            if group["trajectory_checks"] else None,
            "argument_accuracy": round(group["argument_passes"] / group["argument_checks"], 4)
            if group["argument_checks"] else None,
            "forbidden_call_rate": round(group["forbidden_failures"] / group["forbidden_checks"], 4)
            if group["forbidden_checks"] else None,
            "safety_violation_rate": round(group["safety_violations"] / cases, 4) if cases else None,
            "refusal_rate": round(group["refusal_passes"] / group["refusal_cases"], 4)
            if group["refusal_cases"] else None,
            "citation_accuracy": round(group["citation_passes"] / group["citation_checks"], 4)
            if group["citation_checks"] else None,
        }
    latencies = [turn["latency_ms"] for result in results for turn in result["turns"]]
    overall_cases = len(results)
    overall_passed = sum(result["passed"] for result in results)
    pass_rows = []
    by_case: dict[str, dict[int, bool]] = defaultdict(dict)
    for result in key_results:
        by_case[result["case_id"]][result["run"]] = result["passed"]
    for case_id, runs in sorted(by_case.items()):
        values = list(runs.values())
        pass_rows.append({"case_id": case_id, "runs": len(values), "passes": sum(values),
                          "pass@runs": any(values), "pass^runs": all(values)})
    return {
        "overall": {
            "case_runs": overall_cases,
            "task_success_rate": round(overall_passed / overall_cases, 4) if overall_cases else None,
            "safety_violation_rate": round(sum(
                1 for result in results if any(
                    name.split(".", 1)[-1] == "forbidden_tools" and not value
                    for name, value in result["checks"].items())) / overall_cases, 4)
            if overall_cases else None,
            "latency_p50_ms": percentile(latencies, 50),
            "latency_p95_ms": percentile(latencies, 95),
            "model_requests": ledger.requests,
            "input_tokens": ledger.input_tokens,
            "output_tokens": ledger.output_tokens,
            "cost_usd": round(ledger.cost_usd, 8),
            "budget_max_requests": ledger.max_requests,
            "budget_max_usd": ledger.max_usd,
            "halted": ledger.halted,
        },
        "categories": rows,
        "pass_metrics": {
            "cases": pass_rows,
            "pass@runs": sum(row["pass@runs"] for row in pass_rows) / len(pass_rows) if pass_rows else None,
            "pass^runs": sum(row["pass^runs"] for row in pass_rows) / len(pass_rows) if pass_rows else None,
        },
    }


def aggregate_combined(prior_rows: list[dict], new_results: list[dict],
                       ledger: BudgetLedger) -> dict:
    summary = []
    for row in prior_rows:
        summary.append({"case_id": row["case_id"], "category": row["category"],
                        "run": row["run"], "passed": bool(row.get("passed")),
                        "latency_ms": row.get("latency_ms") or 0})
    for result in new_results:
        summary.append({"case_id": result["case_id"], "category": result["category"],
                        "run": result["run"], "passed": result["passed"],
                        "latency_ms": result.get("latency_ms") or 0})
    by_category = defaultdict(lambda: [0, 0])
    for row in summary:
        group = by_category[row["category"]]
        group[0] += 1
        group[1] += int(row["passed"])
    by_case = defaultdict(dict)
    for row in summary:
        by_case[row["case_id"]][row["run"]] = row["passed"]
    key_categories = {"refund_allow", "refund_approval", "refund_deny", "ownership"}
    pass_rows = []
    for case_id, runs in sorted(by_case.items()):
        category = next(row["category"] for row in summary if row["case_id"] == case_id)
        if category not in key_categories:
            continue
        values = list(runs.values())
        pass_rows.append({"case_id": case_id, "runs": len(values), "passes": sum(values),
                          "pass@runs": any(values), "pass^runs": all(values)})
    latencies = [row["latency_ms"] for row in summary if row.get("latency_ms")]
    detailed = new_results
    detailed_checks = [check for result in detailed for check in result["checks"].items()]
    forbidden_failures = sum(1 for name, passed in detailed_checks
                             if name.split(".", 1)[-1] == "forbidden_tools" and not passed)
    trajectory = [(name, passed) for name, passed in detailed_checks
                  if name.split(".", 1)[-1] == "trajectory"]
    arguments = [(name, passed) for name, passed in detailed_checks
                 if name.split(".", 1)[-1].startswith("key_args:")]
    return {
        "overall": {
            "case_runs": len(summary),
            "task_success_rate": round(sum(row["passed"] for row in summary) / len(summary), 4)
            if summary else None,
            "safety_violation_rate": round(forbidden_failures / len(detailed), 4)
            if detailed else None,
            "safety_scope": "new_detailed_runs_only; prior 180 rows lack per-check detail",
            "latency_p50_ms": percentile(latencies, 50),
            "latency_p95_ms": percentile(latencies, 95),
            "model_requests": ledger.requests,
            "input_tokens": ledger.input_tokens,
            "output_tokens": ledger.output_tokens,
            "cost_usd": round(ledger.cost_usd, 8),
            "budget_max_requests": ledger.max_requests,
            "budget_max_usd": ledger.max_usd,
            "halted": ledger.halted,
            "detailed_case_runs": len(detailed),
        },
        "categories": {
            cat: {"case_count": values[0],
                  "task_success_rate": round(values[1] / values[0], 4) if values[0] else None}
            for cat, values in sorted(by_category.items())
        },
        "detailed_model_metrics": {
            "tool_selection_accuracy": round(sum(p for _, p in trajectory) / len(trajectory), 4)
            if trajectory else None,
            "argument_accuracy": round(sum(p for _, p in arguments) / len(arguments), 4)
            if arguments else None,
            "scope": "new_detailed_runs_only",
        },
        "pass_metrics": {
            "cases": pass_rows,
            "pass@runs": round(sum(row["pass@runs"] for row in pass_rows) / len(pass_rows), 4)
            if pass_rows else None,
            "pass^runs": round(sum(row["pass^runs"] for row in pass_rows) / len(pass_rows), 4)
            if pass_rows else None,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--max-requests", type=int, default=1200)
    parser.add_argument("--max-usd", type=float, default=2.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", default=None, help="comma-separated case ids")
    parser.add_argument("--only-categories", default=None, help="comma-separated categories")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--profile", choices=("full", "bare"), default="full",
                        help="full = production harness; bare = model + tools only")
    parser.add_argument("--no-key-runs", action="store_true",
                        help="run every case once; skip key-category runs 2/3")
    parser.add_argument("--max-tool-rounds", type=int, default=10,
                        help="bare profile experiment bound (not a deliverable guardrail)")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("ANTHROPIC_MODEL", "deepseek-flash").strip()
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or "https://api.deepseek.com/anthropic"
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    out = Path(args.output_dir)
    ledger_path = out / "ledger.json"
    progress_path = out / "progress.jsonl"
    prior_rows: list[dict] = []
    out.mkdir(parents=True, exist_ok=True)
    if args.resume:
        if not ledger_path.exists():
            raise SystemExit(f"{ledger_path} missing; cannot resume")
        ledger = BudgetLedger.load(ledger_path, max_requests=args.max_requests,
                                   max_usd=args.max_usd)
        if progress_path.exists():
            prior_rows = [json.loads(line) for line in
                          progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        if ledger_path.exists() and not args.fresh:
            raise SystemExit(f"{ledger_path} exists; pass --fresh to start a new run")
        progress_path.write_text("", encoding="utf-8")
        ledger = BudgetLedger(ledger_path, max_requests=args.max_requests,
                              max_usd=args.max_usd)
    details_path = out / "details.jsonl"
    prior_details: list[dict] = []
    if args.resume:
        if details_path.exists():
            prior_details = [json.loads(line) for line in
                             details_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        details_path.write_text("", encoding="utf-8")
    raw = AsyncAnthropic(
        api_key=api_key, base_url=base_url, max_retries=0,
        timeout=httpx.Timeout(60, connect=5),
        http_client=httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=0),
                                      timeout=httpx.Timeout(60, connect=5), trust_env=False),
    )
    budgeted = BudgetedClient(raw, ledger)
    harness = harness_for_profile(args.profile, max_tool_rounds=args.max_tool_rounds)
    kb = KnowledgeBase(chroma_host="127.0.0.1", chroma_port=8001)
    _, cases = load_cases(args.cases)
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[:args.limit]
    if args.only:
        wanted = {item.strip() for item in args.only.split(",") if item.strip()}
        cases = [case for case in cases if case["id"] in wanted]
    if args.only_categories:
        wanted_categories = {item.strip() for item in args.only_categories.split(",")
                             if item.strip()}
        cases = [case for case in cases if case["category"] in wanted_categories]
    key_categories = {"refund_allow", "refund_approval", "refund_deny", "ownership"}
    completed = {(row["case_id"], int(row["run"])) for row in prior_rows}
    plan = [(case, 1) for case in cases]
    if not args.no_key_runs:
        plan += [(case, run) for case in cases if case["category"] in key_categories
                 for run in (2, 3)]
    plan = [(case, run) for case, run in plan if (case["id"], run) not in completed]
    results: list[dict] = []
    key_results: list[dict] = []
    halted = False
    for case, run in plan:
        if ledger.halted:
            halted = True
            break
        try:
            result = score_case(case, fixture, api_key=api_key, base_url=base_url,
                                model=model, budgeted=budgeted, kb=kb, harness=harness)
        except BudgetExceeded:
            halted = True
            break
        except Exception as exc:
            result = {"case_id": case["id"], "category": case["category"],
                      "passed": False, "checks": {"error": False},
                      "turns": [], "terminal_state": {}, "latency_ms": 0,
                      "model_calls": 0, "error": f"{type(exc).__name__}: {exc}"}
        result["run"] = run
        results.append(result)
        if case["category"] in key_categories:
            key_results.append(result)
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({key: result.get(key) for key in (
                "case_id", "category", "run", "passed", "latency_ms", "model_calls", "error")},
                ensure_ascii=False) + "\n")
        with details_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        print(json.dumps({"case": result["case_id"], "run": run, "passed": result["passed"],
                          "requests": ledger.requests, "usd": round(ledger.cost_usd, 5)},
                         ensure_ascii=False), flush=True)
    report = {
        "schema": "echomind.h2_3.real_report", "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "base_url": base_url, "layer": "real_model",
        "profile": args.profile,
        "harness": asdict(harness or HarnessConfig()),
        "max_tool_rounds": args.max_tool_rounds if harness else None,
        "halted": halted or ledger.halted, "results": results,
    }
    merged_details = [*prior_details, *results]
    loop_truncated = sum(1 for result in merged_details if result.get("loop_truncated"))
    report["baseline_metrics"] = summarize_baseline(
        merged_details, loop_truncated=loop_truncated)
    report["baseline_metrics_scope"] = (
        "all_detailed_runs" if prior_details else
        "new_results_only" if args.resume else "all_results")
    if args.resume:
        report["resume"] = True
        report["prior_rows"] = len(prior_rows)
        report["new_results"] = len(results)
        report.update(aggregate_combined(prior_rows, results, ledger))
        if prior_details:
            report["overall"]["safety_scope"] = "all_detailed_runs"
        target = out / "final.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
        lines = ["# H2-3 real2 Final", "",
                 f"- case_runs: {report['overall']['case_runs']}",
                 f"- task_success_rate: {report['overall']['task_success_rate']}",
                 f"- safety_violation_rate: {report['overall']['safety_violation_rate']} "
                 f"({report['overall']['safety_scope']})",
                 f"- requests/cost: {report['overall']['model_requests']} / "
                 f"USD {report['overall']['cost_usd']}",
                 f"- p50/p95: {report['overall']['latency_p50_ms']} / "
                 f"{report['overall']['latency_p95_ms']} ms",
                 f"- pass@runs/pass^runs: {report['pass_metrics']['pass@runs']} / "
                 f"{report['pass_metrics']['pass^runs']}", "",
                 "| Case | Runs | Passes | pass@runs | pass^runs |",
                 "| --- | ---: | ---: | --- | --- |"]
        for row in report["pass_metrics"]["cases"]:
            lines.append(f"| {row['case_id']} | {row['runs']} | {row['passes']} | "
                         f"{row['pass@runs']} | {row['pass^runs']} |")
        (out / "FINAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        report.update(aggregate(results, ledger, key_results))
        target = out / "report.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "pass_metrics": report["pass_metrics"],
                      "baseline_metrics": report["baseline_metrics"]},
                     ensure_ascii=False, indent=2))
    return 0 if not report["overall"]["halted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
