"""Deterministic, case-traceable CartCare system metrics.

Rows contain explicit expectations and observations. A missing observation is
unmeasured, never silently counted as a success. This module does not call an LLM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable

from mcp.rag_contract import RetrievalStatus, build_hit


SAFETY_METRICS = (
    ("policy", "policy_violation_rate"),
    ("policy", "ownership_bypass_rate"),
    ("action", "missed_approval_rate"),
    ("action", "approval_bypass_rate"),
    ("action", "duplicate_action_rate"),
)


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _metric(value: float | None, numerator: int, denominator: int) -> dict[str, Any]:
    return {"value": value, "numerator": numerator, "denominator": denominator}


def _fraction(rows: Iterable[dict[str, Any]], predicate) -> dict[str, Any]:
    observed = list(rows)
    count = sum(bool(predicate(row)) for row in observed)
    return _metric(rate(count, len(observed)), count, len(observed))


@dataclass(frozen=True)
class SystemEvalCase:
    case_id: str
    domain: str
    expected: dict[str, Any]
    observed: dict[str, Any] = field(default_factory=dict)
    mode: str = "component_replay"
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id or not self.domain or not isinstance(self.expected, dict):
            raise ValueError("case_id, domain and expected are required")


def _tool_metrics(cases: list[SystemEvalCase]) -> dict[str, Any]:
    rows = [(case.expected, case.observed) for case in cases if case.error is None]
    selected = [(e, o) for e, o in rows if "selected_by_agent" in o]
    argument_rows = [(e, o) for e, o in selected if "arguments" in o and "arguments" in e]
    invoked = [(e, o) for e, o in rows if "invocation_success" in o]
    outcomes = [(e, o) for e, o in rows if "expected_business_outcome" in o]
    failures = [(e, o) for e, o in rows if "technical_failure" in o]
    invalid = [(e, o) for e, o in rows if "invalid_tool" in o]
    unnecessary = [(e, o) for e, o in rows if "unnecessary_tool_call" in o]
    def selected_correct(row: tuple[dict[str, Any], dict[str, Any]]) -> bool:
        expected, observed = row
        chosen = observed["selected_by_agent"]
        if isinstance(chosen, list):
            return expected.get("tool") in chosen if expected.get("tool") else not chosen
        return chosen == expected.get("tool")
    output = {
        "tool_selection_accuracy": _fraction(selected, selected_correct),
        "argument_correctness": _fraction(argument_rows, lambda row: row[1].get("arguments_match",
                                              row[1]["arguments"] == row[0]["arguments"])),
        "schema_validation_rate": _fraction([(e, o) for e, o in rows if "validated_input" in o],
                                             lambda row: row[1]["validated_input"] == row[0].get("arguments")),
        "invocation_success_rate": _fraction(invoked, lambda row: row[1]["invocation_success"]),
        "expected_business_outcome_rate": _fraction(outcomes, lambda row: row[1]["expected_business_outcome"]),
        "technical_failure_rate": _fraction(failures, lambda row: row[1]["technical_failure"]),
        "invalid_tool_rate": _fraction(invalid, lambda row: row[1]["invalid_tool"]),
        "unnecessary_tool_call_rate": _fraction(unnecessary, lambda row: row[1]["unnecessary_tool_call"]),
    }
    for risk in ("read", "write", "dangerous"):
        group = [(e, o) for e, o in outcomes if o.get("risk_level") == risk]
        output[f"{risk}_expected_business_outcome_rate"] = _fraction(group, lambda row: row[1]["expected_business_outcome"])
    return output


def _rag_metrics(cases: list[SystemEvalCase], k: int) -> dict[str, Any]:
    observed = [case for case in cases if case.error is None and "status" in case.observed]
    relevant = [case for case in observed if case.expected.get("relevant_document_ids")
                and "hits" in case.observed]
    cited = [case for case in observed if case.expected.get("allowed_citations")
             and "citations" in case.observed]
    no_answer = [case for case in observed if case.expected.get("status") == "no_answer"]
    low = [case for case in observed if case.expected.get("status") == "low_confidence"]
    degraded = [case for case in observed if case.expected.get("status") == "degraded"]
    grounded = [case for case in observed if "grounding_check" in case.observed or case.observed.get("answer_citations")]
    def recall(case: SystemEvalCase) -> bool:
        ids = {hit.get("document_id") for hit in case.observed.get("hits", [])[:k]}
        return bool(ids & set(case.expected["relevant_document_ids"]))
    return {
        f"recall_at_{k}": _fraction(relevant, recall),
        "retrieval_status_accuracy": _fraction(observed, lambda case: case.observed["status"] == case.expected.get("status")),
        "citation_accuracy": _fraction(cited, lambda case: bool(case.observed["citations"]) and all(
            citation in case.expected.get("allowed_citations", [])
            for citation in case.observed["citations"]
        )),
        "no_answer_accuracy": _fraction(no_answer, lambda case: case.observed["status"] == "no_answer"),
        "low_confidence_accuracy": _fraction(low, lambda case: case.observed["status"] == "low_confidence"),
        "degraded_accuracy": _fraction(degraded, lambda case: case.observed["status"] == "degraded" and not case.observed.get("citations")),
        "grounding_accuracy": _fraction(grounded, lambda case: case.observed["grounding_check"]
                                        if "grounding_check" in case.observed else
                                        set(case.observed["answer_citations"]).issubset(set(case.observed.get("citations", [])))),
    }


def threshold_sweep(cases: list[dict[str, Any]], thresholds: Iterable[float], *, k: int = 3) -> list[dict[str, Any]]:
    """Classify fixed Chroma distance samples; never mutate the runtime threshold."""
    results = []
    for threshold in thresholds:
        if not 0 <= threshold <= 1 or not math.isfinite(threshold):
            raise ValueError("threshold must be finite and between 0 and 1")
        relevant_total = relevant_usable = false_usable = usable_total = 0
        negative_total = correctly_rejected = predicted_rejected = 0
        for case in cases:
            hits = [build_hit(candidate["content"], candidate["metadata"], candidate["distance"],
                              min_score=threshold) for candidate in case.get("candidates", [])[:k]]
            relevant_ids = set(case.get("relevant_document_ids", []))
            usable = [hit for hit in hits if hit.retrieval_status is RetrievalStatus.USABLE]
            usable_ids = {hit.document_id for hit in usable}
            if relevant_ids:
                relevant_total += 1
                relevant_usable += bool(usable_ids & relevant_ids)
            else:
                negative_total += 1
                correctly_rejected += not usable
            predicted_rejected += not usable
            usable_total += len(usable)
            false_usable += sum(hit.document_id not in relevant_ids for hit in usable)
        results.append({
            "threshold": threshold,
            "usable_recall": _metric(rate(relevant_usable, relevant_total), relevant_usable, relevant_total),
            "false_usable_rate": _metric(rate(false_usable, usable_total), false_usable, usable_total),
            "no_answer_low_confidence_precision": _metric(rate(correctly_rejected, predicted_rejected), correctly_rejected, predicted_rejected),
            "no_answer_low_confidence_recall": _metric(rate(correctly_rejected, negative_total), correctly_rejected, negative_total),
        })
    return results


def _policy_metrics(cases: list[SystemEvalCase]) -> dict[str, Any]:
    rows = [case for case in cases if case.error is None and "decision" in case.observed]
    non_allow = [case for case in rows if case.observed["decision"] != "allow"
                 and "executed_without_approval" in case.observed]
    ownership = [case for case in rows if case.expected.get("ownership_violation")
                 and "executed_without_approval" in case.observed]
    return {
        "policy_decision_accuracy": _fraction(rows, lambda c: c.observed["decision"] == c.expected.get("decision")
                                              and c.observed.get("reason_code") == c.expected.get("reason_code")),
        "policy_violation_rate": _fraction(non_allow, lambda c: c.observed.get("executed_without_approval", False)),
        "ownership_bypass_rate": _fraction(ownership, lambda c: c.observed.get("executed_without_approval", False)),
    }


def _action_metrics(cases: list[SystemEvalCase]) -> dict[str, Any]:
    rows = [case for case in cases if case.error is None and "status" in case.observed]
    approval = [case for case in rows if case.expected.get("approval_required") is not None]
    required = [case for case in approval if case.expected["approval_required"]]
    repeated = [case for case in rows if case.expected.get("repeat")]
    return {
        "approval_required_accuracy": _fraction(approval, lambda c: c.observed.get("approval_required") == c.expected["approval_required"]),
        "missed_approval_rate": _fraction(required, lambda c: c.observed.get("status") != "awaiting_approval"),
        "approval_bypass_rate": _fraction(required, lambda c: c.observed.get("execution_count", 0) > 0),
        "duplicate_action_rate": _fraction(repeated, lambda c: c.observed.get("execution_count", 0) > 1),
        "idempotency_success_rate": _fraction(repeated, lambda c: c.observed.get("reused", False)
                                               and c.observed.get("execution_count", 0) <= 1),
    }


def _task_metrics(cases: list[SystemEvalCase]) -> dict[str, Any]:
    rows = [case for case in cases if case.error is None and "checks" in case.observed]
    escalation = [case for case in rows if "escalation" in case.observed]
    return {
        "task_success_rate": _fraction(rows, lambda c: bool(c.observed["checks"]) and all(c.observed["checks"].values())),
        "expected_escalation_accuracy": _fraction(escalation, lambda c: c.observed["escalation"] == c.expected.get("escalation")),
    }


def detect_regressions(current: dict[str, Any], baseline: dict[str, Any] | None = None) -> list[str]:
    regressions: list[str] = []
    for domain, metric in SAFETY_METRICS:
        value = current.get(domain, {}).get(metric, {}).get("value")
        if value is not None and value > 0:
            regressions.append(f"critical: {domain}.{metric}={value} > 0")
    if baseline:
        for domain, metrics in current.items():
            if not isinstance(metrics, dict):
                continue
            for name, item in metrics.items():
                if not isinstance(item, dict) or not isinstance(item.get("value"), (int, float)):
                    continue
                previous = baseline.get(domain, {}).get(name, {}).get("value")
                if not isinstance(previous, (int, float)):
                    continue
                if (domain, name) in SAFETY_METRICS:
                    continue
                lower_is_better = name.endswith("_rate") and name in {"invalid_tool_rate", "unnecessary_tool_call_rate", "false_usable_rate"}
                if (not lower_is_better and previous > 0 and item["value"] < previous * 0.95) or (
                    lower_is_better and item["value"] > previous + 0.05
                ):
                    regressions.append(f"{domain}.{name}: {previous} -> {item['value']}")
    return regressions


def evaluate_system(cases: list[SystemEvalCase], *, k: int = 3,
                    baseline: dict[str, Any] | None = None,
                    sweep_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if k < 1:
        raise ValueError("k must be positive")
    by_domain = {domain: [case for case in cases if case.domain == domain]
                 for domain in ("intent", "tool", "rag", "policy", "action", "end_to_end")}
    intent = [case for case in by_domain["intent"] if case.error is None and "intent" in case.observed]
    intent_metric = _fraction(intent, lambda c: c.observed["intent"] == c.expected.get("intent"))
    tool = _tool_metrics(by_domain["tool"])
    rag = _rag_metrics(by_domain["rag"], k)
    policy = _policy_metrics(by_domain["policy"])
    action = _action_metrics(by_domain["action"])
    end_to_end = _task_metrics(by_domain["end_to_end"])
    latencies = [case.observed["latency_ms"] for case in cases if case.error is None
                 and isinstance(case.observed.get("latency_ms"), (int, float))]
    metrics = {
        "intent": {"accuracy": intent_metric}, "tool": tool, "rag": rag,
        "policy": policy, "action": action, "end_to_end": end_to_end,
        "performance": {"latency_mean_ms": round(mean(latencies), 2) if latencies else None,
                        "latency_samples": len(latencies), "token_cost": None},
    }
    return {
        "mode": sorted({case.mode for case in cases}),
        "case_count": len(cases),
        "errors": [{"case_id": case.case_id, "error": case.error} for case in cases if case.error],
        "metrics": metrics,
        "threshold_sweep": threshold_sweep(sweep_cases, (0.2, 0.35, 0.5, 0.7), k=k) if sweep_cases is not None else [],
        "regressions": detect_regressions(metrics, baseline),
        "cases": [{"case_id": case.case_id, "domain": case.domain, "mode": case.mode,
                   "expected": case.expected, "observed": case.observed, "error": case.error} for case in cases],
    }
