"""Run fixed, deterministic component-replay evaluations on demo fixtures.

This runner never claims an Agent selected a tool. Use the existing HTTP
baseline runner for actual /chat routing and tool selection observations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actions import ActionService, InMemoryBusinessActionBackend
from agents.agent_orchestrator import Request
from agents.tools import build_action_tools, build_business_tools
from core.tool_contract import execute_tool
from mcp.rag_contract import RetrievalStatus, build_hit
from mcp.tool_manager import MCPToolManager, Tool
from policies import PolicyEngine
from providers import OrderProvider, RefundProvider
from providers.mock_backend import InMemoryBusinessBackend

from .system_eval import SystemEvalCase, evaluate_system


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name("system_cases.json")
FIXTURE_PATH = ROOT / "providers" / "fixtures" / "business_provider_data.json"
NOW = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
POLICY_METADATA = {
    "document_id": "policy-refund-v1", "title": "Demo refund policy", "source": "demo://refund-policy",
    "doc_type": "policy", "policy_version": "refund-v1", "effective_at": "2026-09-01T00:00:00Z",
    "chunk_index": 0, "total_chunks": 1,
}
FAQ_METADATA = {
    "document_id": "faq-shipping-v1", "title": "Demo shipping FAQ", "source": "demo://shipping-faq",
    "doc_type": "faq", "chunk_index": 0, "total_chunks": 1,
}


def _demo_data(setup: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    setup = setup or {}
    if setup.get("refunds") is False:
        data["refunds"] = {}
    if "order_status" in setup:
        data["orders"]["ORD-1001"]["status"] = setup["order_status"]
    if "total_amount" in setup:
        data["orders"]["ORD-1001"]["total_amount"] = setup["total_amount"]
    return data


async def _scenario(case: dict[str, Any]) -> list[SystemEvalCase]:
    case_id = case["id"]
    expected = case["expected"]
    kind = case["kind"]
    started = time.perf_counter()
    rows: list[SystemEvalCase] = []
    if kind == "unsupported":
        # An unsupported request has no executable component path. Its intent,
        # escalation and task success remain unmeasured in this offline replay.
        return []
    if kind == "rag":
        result = await _rag_result("usable")
        hit = result.data[0]
        citation = result.citations[0]["reference"] if result.citations else None
        checks = {"status": result.retrieval_status == expected["status"],
                  "citation": citation == expected["citation"],
                  "document": hit["document_id"] == expected["document_id"]}
        rows.append(SystemEvalCase(case_id, "rag", {
            "relevant_document_ids": [expected["document_id"]],
            "allowed_citations": [expected["citation"]], "status": expected["status"],
        }, {"status": result.retrieval_status,
            "hits": [{"document_id": hit["document_id"]}],
            "citations": [citation] if citation else []}))
        rows.append(SystemEvalCase(case_id, "end_to_end", expected,
                                   {"checks": checks, "latency_ms": (time.perf_counter()-started)*1000}))
        return rows

    data = _demo_data(case.get("setup"))
    read_backend = InMemoryBusinessBackend(data)
    action_backend = InMemoryBusinessActionBackend(data)
    service = ActionService(business_backend=read_backend, action_backend=action_backend, clock=lambda: NOW)
    tools = build_business_tools(read_backend) | build_action_tools(service)
    spec = tools[case["tool"]]
    arguments = case["arguments"]
    user_id = case.get("user_id", "customer-1")
    request = Request(message=case["message"], user_id=user_id, conv_id=f"eval-{case_id}", request_id=f"eval-{case_id}")
    result = await execute_tool(spec, arguments, lambda: spec.handler(request, arguments))
    payload = result.data if isinstance(result.data, dict) else {}
    checks: dict[str, bool] = {"tool_executed": result.attempts == 1}
    if kind == "read":
        expected_value = expected["data_value"]
        actual_value = (payload.get("data") or {}).get(expected["data_field"])
        checks["provider_fact"] = actual_value == expected_value
    else:
        action = payload.get("action") or {}
        policy = action.get("policy_decision") or {}
        status = payload.get("status")
        decision = policy.get("decision")
        checks["status"] = status == expected["status"]
        if "policy_decision" in expected:
            checks["policy"] = decision == expected["policy_decision"]
        if "error_code" in expected:
            checks["error"] = payload.get("error_code") == expected["error_code"]
        rows.append(SystemEvalCase(case_id, "action", {
            "approval_required": expected["approval_required"],
        }, {"status": status, "approval_required": status == "awaiting_approval",
            "execution_count": len(action_backend.calls)}))
        if decision is not None:
            rows.append(SystemEvalCase(case_id, "policy", {
                "decision": expected.get("policy_decision"), "reason_code": expected.get("reason_code"),
                "ownership_violation": case_id == "ownership_violation",
            }, {"decision": decision, "reason_code": policy.get("reason_code"),
                "executed_without_approval": len(action_backend.calls) > 0 and decision != "allow"}))
    rows.append(SystemEvalCase(case_id, "tool", {"tool": spec.name, "arguments": arguments}, {
        "validated_input": result.validated_input,
        "invocation_success": result.attempts > 0,
        "expected_business_outcome": all(checks.values()),
        "technical_failure": result.error_code in {
            "dependency_failure", "timeout", "execution_failure", "service_unavailable"
        },
        "risk_level": spec.risk_level.value,
        "latency_ms": result.latency_ms,
    }))
    rows.append(SystemEvalCase(case_id, "end_to_end", expected,
                               {"checks": checks, "latency_ms": (time.perf_counter()-started)*1000}))
    return rows


def _policy_cases() -> list[SystemEvalCase]:
    from providers.models import OrderStatus
    from decimal import Decimal
    data = _demo_data({"refunds": False})
    order = OrderProvider(InMemoryBusinessBackend(data)).get_order("ORD-1001", customer_id="customer-1")
    engine = PolicyEngine()
    previous = RefundProvider(InMemoryBusinessBackend(_demo_data())).get_refund_for_order(
        "ORD-1001", customer_id="customer-1")
    specs = [
        ("refund_allow", "refund", {}, "allow", "refund_eligible"),
        ("refund_expired", "refund", {"evaluated_at": datetime(2026,9,28,10,1,tzinfo=timezone.utc)}, "deny", "refund_window_expired"),
        ("refund_invalid_status", "refund", {"status": OrderStatus.CANCELLED}, "deny", "order_status_not_refundable"),
        ("refund_threshold", "refund", {"total_amount": Decimal("800"), "amount": Decimal("600")}, "require_approval", "amount_requires_approval"),
        ("refund_ownership", "refund", {"customer_id": "customer-2"}, "deny", "ownership_mismatch"),
        ("refund_duplicate", "refund", {"existing_refund": previous}, "deny", "refund_already_in_progress"),
        ("cancel_allow", "cancel", {"status": OrderStatus.PENDING}, "allow", "cancel_eligible"),
        ("cancel_deny", "cancel", {}, "deny", "order_status_not_cancellable"),
        ("cancel_approval", "cancel", {"status": OrderStatus.PROCESSING}, "require_approval", "processing_order_requires_approval"),
    ]
    rows = []
    for case_id, action, options, expected_decision, reason in specs:
        updated = order.model_copy(update={key: options[key] for key in ("status", "total_amount") if key in options})
        kwargs = {"customer_id": options.get("customer_id", "customer-1"),
                  "evaluated_at": options.get("evaluated_at", NOW)}
        if action == "refund":
            kwargs.update({key: options[key] for key in ("amount", "existing_refund") if key in options})
            decision = engine.evaluate_refund(updated, **kwargs)
        else:
            decision = engine.evaluate_cancel(updated, **kwargs)
        rows.append(SystemEvalCase(case_id, "policy", {
            "decision": expected_decision, "reason_code": reason,
            "ownership_violation": case_id == "refund_ownership",
        }, {"decision": decision.decision.value, "reason_code": decision.reason_code,
            "policy_version": decision.policy_version}))
    return rows


def _action_repeats() -> list[SystemEvalCase]:
    data = _demo_data({"refunds": False})
    backend = InMemoryBusinessActionBackend(data)
    service = ActionService(business_backend=InMemoryBusinessBackend(data), action_backend=backend, clock=lambda: NOW)
    first = service.request_refund(order_id="ORD-1001", user_id="customer-1", request_id="repeat-1")
    repeated = service.request_refund(order_id="ORD-1001", user_id="customer-1", request_id="repeat-2")
    service.resume(action_id=first.action_id, user_id="customer-1", request_id="repeat-3")
    rows = [SystemEvalCase("refund_repeat", "action", {"repeat": True}, {
        "status": repeated.status.value, "reused": repeated.reused, "execution_count": len(backend.calls),
    })]
    approval_data = _demo_data({"refunds": False, "total_amount": "800.00"})
    approval_backend = InMemoryBusinessActionBackend(approval_data)
    approval_service = ActionService(business_backend=InMemoryBusinessBackend(approval_data),
                                     action_backend=approval_backend, clock=lambda: NOW)
    pending = approval_service.request_refund(order_id="ORD-1001", user_id="customer-1",
                                              request_id="approval-1", amount="600")
    approved = approval_service.approve(action_id=pending.action_id, user_id="customer-1", request_id="approval-2")
    duplicate = approval_service.approve(action_id=pending.action_id, user_id="customer-1", request_id="approval-3")
    resumed = approval_service.resume(action_id=pending.action_id, user_id="customer-1", request_id="approval-4")
    rows.append(SystemEvalCase("duplicate_approval_resume", "action", {"repeat": True}, {
        "status": resumed.status.value, "reused": duplicate.reused and resumed.reused,
        "execution_count": len(approval_backend.calls), "approved_status": approved.status.value,
    }))
    reject_data = _demo_data({"refunds": False, "total_amount": "800.00"})
    reject_backend = InMemoryBusinessActionBackend(reject_data)
    reject_service = ActionService(business_backend=InMemoryBusinessBackend(reject_data),
                                   action_backend=reject_backend, clock=lambda: NOW)
    pending_reject = reject_service.request_refund(order_id="ORD-1001", user_id="customer-1",
                                                   request_id="reject-1", amount="600")
    rejected = reject_service.reject(action_id=pending_reject.action_id, user_id="customer-1", request_id="reject-2")
    after_reject = reject_service.resume(action_id=pending_reject.action_id, user_id="customer-1", request_id="reject-3")
    rows.append(SystemEvalCase("reject_resume", "action", {"repeat": True}, {
        "status": rejected.status.value, "reused": after_reject.reused,
        "execution_count": len(reject_backend.calls),
    }))
    return rows


async def _rag_result(scenario: str):
    manager = MCPToolManager(api_key="demo-eval-only")
    async def rewrite(query, n=3):
        return [query]
    async def rerank(query, items, top_k):
        return items[:top_k]
    async def handler(params, context):
        if scenario == "degraded":
            raise RuntimeError("demo Chroma dependency failure")
        if scenario == "no_answer":
            return []
        distance = 0.2 if scenario == "usable" else 0.8
        return [build_hit("Demo source text", POLICY_METADATA if scenario == "usable" else FAQ_METADATA,
                          distance, min_score=0.35, now=NOW).model_dump(mode="json")]
    manager.rewrite_query = rewrite
    manager._rerank = rerank
    manager.register(Tool("knowledge_search", "demo search", handler, {
        "type": "object", "properties": {"query": {"type": "string", "minLength": 1},
                                          "top_k": {"type": "integer"}},
        "required": ["query"], "additionalProperties": False,
    }, fallback=(lambda params, context, error: [{"fallback": True, "content": "demo degraded"}])
    if scenario == "degraded" else None))
    return await manager.search_with_rewrite("knowledge_search", "demo question")


async def _rag_cases() -> list[SystemEvalCase]:
    examples = [
        ("rag_policy", "policy-refund-v1", POLICY_METADATA, 0.2, "usable"),
        ("rag_low", "faq-shipping-v1", FAQ_METADATA, 0.8, "low_confidence"),
        ("rag_no_answer", None, None, None, "no_answer"),
        ("rag_degraded", None, None, None, "degraded"),
    ]
    rows = []
    for case_id, document_id, metadata, distance, expected_status in examples:
        result = await _rag_result(expected_status)
        hit = result.data[0] if result.data else None
        status = result.retrieval_status
        citation = result.citations[0]["reference"] if result.citations else None
        rows.append(SystemEvalCase(case_id, "rag", {
            "relevant_document_ids": [document_id] if document_id and expected_status == "usable" else [],
            "allowed_citations": [citation] if citation else [], "status": expected_status,
        }, {"status": status, "hits": [{"document_id": hit["document_id"]}] if hit else [],
            "citations": [citation] if citation else []}))
    return rows


def _sweep_cases() -> list[dict[str, Any]]:
    return [
        {"relevant_document_ids": ["policy-refund-v1"], "candidates": [
            {"content": "Demo policy", "metadata": POLICY_METADATA, "distance": 0.6},
            {"content": "Irrelevant FAQ", "metadata": FAQ_METADATA, "distance": 0.7}]},
        {"relevant_document_ids": ["faq-shipping-v1"], "candidates": [
            {"content": "Demo FAQ", "metadata": FAQ_METADATA, "distance": 0.15}]},
        {"relevant_document_ids": [], "candidates": [
            {"content": "Irrelevant FAQ", "metadata": FAQ_METADATA, "distance": 0.58}]},
        {"relevant_document_ids": [], "candidates": []},
    ]


async def run_suite(*, baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows: list[SystemEvalCase] = []
    for case in cases:
        try:
            rows.extend(await _scenario(case))
        except Exception as exc:
            rows.append(SystemEvalCase(case["id"], "end_to_end", case["expected"], error=str(exc)))
    rows.extend(_policy_cases())
    rows.extend(_action_repeats())
    rows.extend(await _rag_cases())
    report = evaluate_system(rows, sweep_cases=_sweep_cases(), baseline=baseline)
    report["scenario_count"] = len(cases)
    report["unmeasured_scenarios"] = [case["id"] for case in cases if case["kind"] == "unsupported"]
    report["limitations"] = [
        "component replay uses demo fixtures and scripted tool invocation; Agent tool selection and intent are unmeasured",
        "unsupported/escalation requires a live /chat run; this scenario is catalogued but unmeasured offline",
        "RAG sweep uses fixed illustrative distances, not a production retrieval corpus",
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic CartCare system eval on demo data")
    parser.add_argument("--output", type=Path, default=None, help="optional JSON report path")
    parser.add_argument("--baseline", type=Path, default=None, help="previous JSON report for regression comparison")
    args = parser.parse_args()
    baseline = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["metrics"]
    report = asyncio.run(run_suite(baseline=baseline))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "mode", "scenario_count", "case_count", "unmeasured_scenarios", "metrics", "threshold_sweep", "regressions", "errors", "limitations"
    )}, ensure_ascii=False, indent=2))
    return 1 if report["regressions"] or report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
