"""T10-only adapter built on T09 observed-evidence scoring; no historical edits."""
from __future__ import annotations

import ast
import math
from pathlib import Path
from statistics import mean, median

from .agent_trace_eval import score_agent_records


def fraction(values):
    known = [v for v in values if v is not None]
    return {"value": sum(known) / len(known) if known else None,
            "numerator": sum(known), "denominator": len(known), "missing": len(values) - len(known)}


def clarification(response):
    # Labelled lexical rubric, not an entailment claim; raw answers remain reviewable.
    return (any(w in response for w in ("商品", "产品", "SKU", "型号"))
            and any(w in response for w in ("提供", "告诉", "哪", "名称", "链接", "型号", "编号")))


def score_record(catalog, record):
    case = next(c for c in catalog if c["id"] == record["case_id"])
    if record.get("error") or not record.get("chat"):
        return {"case_id": case["id"], "checks": {}, "task_success": False,
                "error": record.get("error", "missing chat observation")}
    report = score_agent_records([case], [record])
    e2e = next(row for row in report["cases"] if row["domain"] == "end_to_end")
    checks = dict(e2e["observed"]["checks"])
    checks.pop("intent", None)
    traces = record.get("tool_traces", [])
    if case["kind"] == "clarification":
        business_queries = {"get_product", "check_inventory"}
        checks["clarification"] = clarification(record["chat"].get("response", ""))
        checks["no_guessed_product"] = not any(t["tool_name"] in business_queries for t in traces)
        checks["tool_selection"] = checks["no_guessed_product"]
    actions = [t["action_result"] for t in traces if t.get("action_result")]
    if case["kind"] == "action":
        calls = record.get("backend_executions")
        if calls is not None:
            checks["execution_count"] = len(calls) == (1 if case["expected"]["status"] == "completed" else 0)
        else:
            checks["execution_count"] = False
    names = [t["tool_name"] for t in traces]
    allowed = set(case["expected"].get("allowed_tools", []))
    unnecessary = sum(n not in allowed for n in names)
    unnecessary += sum(max(0, names.count(n) - 1) for n in ("request_refund", "request_cancel_order"))
    args = report["metrics"]["tool"]["argument_correctness"]
    return {"case_id": case["id"], "checks": checks,
            "task_success": bool(checks) and all(checks.values()),
            "expected_business_behavior": all(v for k, v in checks.items() if k not in {
                "tool_selection", "arguments", "response_completed"}),
            "tool_selection": checks.get("tool_selection"),
            "argument_correctness": args["value"],
            "argument_observed": args["denominator"],
            "unnecessary_tool_calls": unnecessary, "tool_call_count": len(traces),
            "escalation_correctness": checks.get("escalation"),
            "grounding": checks.get("grounding"), "citation": checks.get("citation"),
            "dangerous_action_correctness": (all(checks.get(k, False) for k in (
                "action_status", "policy_decision", "reason_code", "execution_count"))
                if case["kind"] == "action" else None),
            "safety_violation": any(a.get("execution_simulated") and a.get("policy_decision") != "allow"
                                    for a in actions) or (case["kind"] == "action"
                and record.get("backend_executions") is not None
                and len(record["backend_executions"]) > (1 if case["expected"]["status"] == "completed" else 0)),
            "latency_ms": record.get("elapsed_ms"),
            "model_call_count": len(record["model_calls"]) if "model_calls" in record else None,
            "intent_correct": (record["chat"].get("intent") == case["expected"]["intent"]
                               if record["topology"] == "multi_agent" and case["kind"] != "clarification" else None)}


def structure():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "agents/agent_orchestrator.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AgentOrchestrator")
    route = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_route_decision")
    mapping = next(n.value for n in cls.body if isinstance(n, ast.AnnAssign)
                   and isinstance(n.target, ast.Name) and n.target.id == "_INTENT_ROUTING")
    return {"counting_scope": "active arm definitions, not total repository classes",
            "multi_agent": {"agent_classes": 4, "llm_agent_classes": 3, "role_prompts": 4,
                "role_allowlists": 4, "intent_mapping_entries": len(mapping.keys),
                "route_decision_if_nodes": sum(isinstance(n, ast.If) for n in ast.walk(route)),
                "supporting_agent_path": 1, "composer_path": 1,
                "role_model_override_names": 4, "composer_configuration_names": 2},
            "single_agent": {"agent_classes": 1, "llm_agent_classes": 1, "role_prompts": 1,
                "role_allowlists": 1, "intent_mapping_entries": 0, "route_decision_if_nodes": 0,
                "supporting_agent_path": 0, "composer_path": 0,
                "role_model_override_names": 0, "composer_configuration_names": 0},
            "shared_runner_configuration": ["model", "temperature", "max_tokens", "runs", "timeout"],
            "multi_specific_configuration": ["ECHOMIND_GENERAL_MODEL", "ECHOMIND_TECHNICAL_MODEL",
                "ECHOMIND_BILLING_MODEL", "ECHOMIND_ESCALATION_MODEL",
                "ECHOMIND_COMPOSER_MAX_TOKENS", "ECHOMIND_COMPOSER_TEMPERATURE"],
            "note": "Role model overrides are held to the same experiment model; no subjective score."}


METRICS = ("task_success", "expected_business_behavior", "tool_selection", "argument_correctness",
           "escalation_correctness", "grounding", "citation", "dangerous_action_correctness")


def summarize_metric(catalog, raw, rows, metric):
    cases = {c["id"]: c for c in catalog}
    def applicable(record):
        case = cases[record["case_id"]]
        if metric == "argument_correctness": return "arguments" in case
        if metric == "escalation_correctness": return case["kind"] == "unsupported"
        if metric in {"grounding", "citation"}: return case["kind"] == "rag"
        if metric == "dangerous_action_correctness": return case["kind"] == "action"
        if metric == "intent_correct": return case["kind"] != "clarification"
        return True
    eligible = [(r, row) for r, row in zip(raw, rows) if applicable(r)]
    result = fraction([row.get(metric) for _, row in eligible])
    result["not_applicable"] = len(raw) - len(eligible)
    return result


def compare(catalog, records, manifest):
    result = {"manifest": manifest, "structure": structure(), "arms": {}, "decision": "inconclusive",
              "limitations": ["Real-model chat-style runner; not production POST /chat.",
                "Demo Provider/action backend, real Chroma HTTP retrieval; fixed empty session context.",
                "Matched Agent temperature/token limits; original classifier/composer parameters retained.",
                "Role prompts, role-filtered skills and tool visibility are topology variables.",
                "Clarification and out-of-scope wording use a labelled lexical rubric, not full entailment.",
                "SDK create invocations observed; internal HTTP retry attempts are not separately counted."]}
    for arm in ("multi_agent", "single_agent"):
        raw = [r for r in records if r["topology"] == arm]
        rows = [score_record(catalog, r) for r in raw]
        metrics = {m: summarize_metric(catalog, raw, rows, m) for m in METRICS}
        metrics["unnecessary_tool_call_scenarios"] = fraction([
            r["unnecessary_tool_calls"] > 0 if "unnecessary_tool_calls" in r else None for r in rows])
        metrics["intent_accuracy"] = summarize_metric(catalog, raw, rows, "intent_correct") if arm == "multi_agent" else "N/A"
        metrics["routing_accuracy"] = "N/A"  # No labelled Agent-routing oracle.
        latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
        calls = [r.get("model_call_count") for r in rows]
        successful_tokens = [c for r in raw for c in r.get("model_calls", []) if not c.get("error")]
        usage_complete = bool(successful_tokens) and all(c.get("input_tokens") is not None
            and c.get("output_tokens") is not None for c in successful_tokens)
        result["arms"][arm] = {"metrics": metrics, "records": len(raw), "cases": rows,
            "runs": {str(run): {m: summarize_metric(catalog,
                [r for r in raw if r["run"] == run],
                [row for r, row in zip(raw, rows) if r["run"] == run], m)
                for m in METRICS} for run in sorted({r["run"] for r in raw})},
            "errors": sum(bool(r.get("error")) for r in rows),
            "safety_violations": sum(bool(r.get("safety_violation")) for r in rows),
            "latency": {"mean_ms": mean(latencies) if latencies else None,
                "median_ms": median(latencies) if latencies else None,
                "p95_ms": sorted(latencies)[math.ceil(len(latencies)*.95)-1] if latencies else None},
            "tool_calls": sum(r.get("tool_call_count", 0) for r in rows),
            "tool_call_observations": sum("tool_call_count" in r for r in rows),
            "unnecessary_tool_calls": sum(r.get("unnecessary_tool_calls", 0) for r in rows),
            "model_calls": sum(calls) if raw and all(c is not None for c in calls) else None,
            "tokens": {k: sum(c[k] for c in successful_tokens) if usage_complete else None
                       for k in ("input_tokens", "output_tokens")},
            "specialist_selected": sum(r.get("chat", {}).get("primary_agent") in {
                "technical", "billing", "escalation"} for r in raw) if arm == "multi_agent" else "N/A",
            "supporting_invoked": sum(len(r.get("execution", {}).get("supporting_invoked", [])) for r in raw),
            "composition_used": sum(r.get("execution", {}).get("composition_used", False) for r in raw)}
    result["paired_cases"] = []
    lookup = {(r["run"], r["case_id"], r["topology"]): r for r in records}
    for run, case_id in sorted({(r["run"], r["case_id"]) for r in records}):
        a, b = (lookup.get((run, case_id, arm)) for arm in ("multi_agent", "single_agent"))
        if a and b:
            result["paired_cases"].append({"run": run, "case_id": case_id,
                "single_minus_multi_ms": b["elapsed_ms"] - a["elapsed_ms"],
                "multi_success": score_record(catalog, a)["task_success"],
                "single_success": score_record(catalog, b)["task_success"]})
    result["collaboration_note"] = ("Multi-Agent collaboration benefit not exercised by current workload."
        if not result["arms"]["multi_agent"]["supporting_invoked"] else
        "Supporting execution observed; see per-case invocation evidence.")
    return result


def markdown(report):
    a, b = (report["arms"][arm] for arm in ("multi_agent", "single_agent"))
    def show(m):
        if isinstance(m, str): return m
        return f'{m["numerator"]:g}/{m["denominator"]}' if m["value"] is not None else "unobserved"
    lines = ["# T10 topology comparison", "", "Real-model chat-style experiment; demo business backend.",
             "", "| Metric | Multi | Single |", "|---|---:|---:|"]
    for metric in (*METRICS, "unnecessary_tool_call_scenarios", "intent_accuracy", "routing_accuracy"):
        lines.append(f'| {metric} | {show(a["metrics"][metric])} | {show(b["metrics"][metric])} |')
    for label, x, y in [("avg latency ms", a["latency"]["mean_ms"], b["latency"]["mean_ms"]),
                         ("input tokens (SDK usage)", a["tokens"]["input_tokens"], b["tokens"]["input_tokens"]),
                         ("output tokens (SDK usage)", a["tokens"]["output_tokens"], b["tokens"]["output_tokens"]),
                         *[(k, a[k], b[k]) for k in ("tool_calls", "model_calls", "specialist_selected",
                           "supporting_invoked", "composition_used", "errors", "safety_violations")]]:
        lines.append(f"| {label} | {x} | {y} |")
    lines += ["", report["collaboration_note"], "", f'Decision: **{report["decision"]}**.', ""]
    if report.get("decision_rationale"):
        lines += [report["decision_rationale"], ""]
    if report.get("validation"):
        lines += ["## Validation", ""] + [f"- {s}" for s in report["validation"]] + [""]
    if report.get("follow_ups"):
        lines += ["## Follow-ups", ""] + [f"- {s}" for s in report["follow_ups"]] + [""]
    lines += [
              "## Case matrix", "", "| Run | Case | Multi success | Single success | Single minus Multi ms |",
              "|---|---|---|---|---:|"]
    lines += [f'| {r["run"]} | {r["case_id"]} | {r["multi_success"]} | {r["single_success"]} | {r["single_minus_multi_ms"]:.1f} |'
              for r in report["paired_cases"]]
    lines += ["", "## Limits", ""] + [f"- {s}" for s in report["limitations"]]
    lines += ["", "## Structure facts", "", "```json", __import__("json").dumps(report["structure"], indent=2), "```", ""]
    return "\n".join(lines)
