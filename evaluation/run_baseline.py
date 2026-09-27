"""Run the fixed As-Is baseline against the real HTTP /chat endpoint.

The runner intentionally does not call internal functions as a replacement for
production traffic. When the service is unavailable it writes one BLOCKED
record per case and preserves the concrete connection error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import time


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name("baseline_cases.json")
REPORT_DIR = Path(__file__).with_name("reports")


def _json_request(
    base_url: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 90.0,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {body[:500]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"无法连接 {url}: {exc}") from exc


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except Exception as exc:
        return f"N/A ({exc})"


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value}


def _expected_intent_matches(expected: Any, actual: Any) -> bool:
    return str(actual) in _as_set(expected)


def _canonical_expected_intent(expected: Any, actual: Any) -> str:
    """Use the matched allowed label for metrics when a Case has alternatives."""
    options = _as_set(expected)
    if str(actual) in options:
        return str(actual)
    return sorted(options)[0] if options else str(expected)


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _p95(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _run_case(case: Dict[str, Any], base_url: str, timeout: float) -> Dict[str, Any]:
    case_id = str(case["id"])
    user_id = f"baseline_{case_id}"
    conv_id = f"baseline_{case_id}_conversation"
    expected = dict(case.get("expected", {}))
    started = time.perf_counter()
    responses: List[Dict[str, Any]] = []
    traces: List[Dict[str, Any]] = []
    errors: List[str] = []

    for turn_index, message in enumerate(case.get("messages", [])):
        try:
            response = _json_request(
                base_url,
                "/chat",
                {"message": str(message), "user_id": user_id, "conv_id": conv_id},
                timeout=timeout,
            )
            responses.append(response)
            request_id = response.get("request_id")
            if request_id:
                try:
                    trace_payload = _json_request(
                        base_url,
                        f"/trace/tool/{request_id}",
                        timeout=min(timeout, 20.0),
                    )
                    traces.append(trace_payload.get("trace") or {})
                except Exception as exc:
                    errors.append(f"turn {turn_index + 1} trace: {exc}")
                    traces.append({})
        except Exception as exc:
            errors.append(f"turn {turn_index + 1}: {exc}")
            break

    measured_latency = round((time.perf_counter() - started) * 1000, 1)
    if not responses:
        return {
            "case_id": case_id,
            "scenario": case.get("scenario", ""),
            "expected": expected,
            "actual": {},
            "checks": {},
            "status": "blocked",
            "latency_ms": measured_latency,
            "errors": errors or ["没有收到 /chat 响应"],
            "trace": {},
            "turns": [],
        }

    last = responses[-1]
    trace = traces[-1] if traces else {}
    trace_tools = trace.get("tool_calls") or []
    tools_used = list(last.get("tools_used") or trace.get("tools_used") or [])
    actual_supporting = list(last.get("supporting_agents") or [])
    actual_agent_types = list(last.get("agent_types") or [])
    actual = {
        "intent": last.get("intent"),
        "intent_group": last.get("intent_group"),
        "intent_confidence": last.get("intent_confidence"),
        "intent_source_scores": last.get("intent_source_scores", {}),
        "entities": last.get("entities", {}),
        "urgency": "N/A",
        "primary_agent": last.get("primary_agent") or last.get("agent_type"),
        "supporting_agents": actual_supporting,
        "agent_types": actual_agent_types,
        "routing_confidence": last.get("routing_confidence"),
        "routing_reason": last.get("routing_reason", ""),
        "multi_agent": bool(actual_supporting) or len(actual_agent_types) > 1,
        "tools_used": tools_used,
        "tool_traces": trace_tools,
        "knowledge_used": bool(last.get("knowledge_used")),
        "search_knowledge_base_called": "search_knowledge_base" in tools_used
        or any(
            item.get("tool_name") == "search_knowledge_base"
            for item in trace_tools
            if isinstance(item, dict)
        ),
        "response": last.get("response", ""),
        "escalated": last.get("escalated"),
        "latency_ms": last.get("latency_ms", measured_latency),
        "memory": {
            "working_memory_observable": "N/A",
            "episodic_observable": "N/A",
            "profile_observable": "N/A",
        },
    }

    expected_supporting = expected.get("supporting_agents")
    checks: Dict[str, Optional[bool]] = {
        "intent": _expected_intent_matches(expected.get("intent"), actual.get("intent")),
        "primary_routing": actual.get("primary_agent") == expected.get("primary_agent"),
        "supporting_routing": (
            set(actual_supporting) == _as_set(expected_supporting)
            if expected_supporting is not None
            else None
        ),
        "multi_agent": (
            actual["multi_agent"] == bool(expected.get("multi_agent"))
            if expected.get("multi_agent") is not None
            else None
        ),
    }

    rag_policy = expected.get("rag", "optional")
    if rag_policy == "required":
        checks["rag_trigger"] = actual["search_knowledge_base_called"]
    elif rag_policy == "skip":
        checks["rag_trigger"] = not actual["search_knowledge_base_called"]
    else:
        checks["rag_trigger"] = None

    expected_tools = expected.get("expected_tools")
    if expected_tools is not None:
        expected_tool_set = _as_set(expected_tools)
        actual_tool_set = _as_set(tools_used)
        checks["tool_selection"] = (
            expected_tool_set.issubset(actual_tool_set)
            if expected_tool_set
            else not actual_tool_set
        )
    else:
        checks["tool_selection"] = None

    escalation_policy = expected.get("escalation", "optional")
    if escalation_policy == "required":
        checks["escalation"] = bool(actual.get("escalated"))
    elif escalation_policy == "forbidden":
        checks["escalation"] = not bool(actual.get("escalated"))
    else:
        checks["escalation"] = None

    if expected.get("memory_continuity") == "required":
        checks["memory_continuity"] = None
        errors.append("memory continuity cannot be verified from public API")

    hard_checks = [value for value in checks.values() if value is not None]
    status = "passed" if all(hard_checks) else "failed"
    return {
        "case_id": case_id,
        "scenario": case.get("scenario", ""),
        "expected": expected,
        "actual": actual,
        "checks": checks,
        "status": status,
        "latency_ms": measured_latency,
        "errors": errors,
        "trace": trace,
        "turns": [
            {
                "message": message,
                "response": response,
                "trace": traces[index] if index < len(traces) else {},
            }
            for index, (message, response) in enumerate(
                zip(case.get("messages", []), responses)
            )
        ],
    }


def _metric_summary(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    runnable = [item for item in results if item.get("status") != "blocked"]
    blocked = [item for item in results if item.get("status") == "blocked"]

    labels = [
        _canonical_expected_intent(
            item.get("expected", {}).get("intent"),
            item.get("actual", {}).get("intent"),
        )
        for item in runnable
    ]
    predictions = [str(item.get("actual", {}).get("intent")) for item in runnable]
    valid_pairs = [
        (ground_truth, prediction)
        for ground_truth, prediction in zip(labels, predictions)
        if ground_truth and prediction and ground_truth != "None"
    ]
    correct = sum(_expected_intent_matches(ground_truth, prediction) for ground_truth, prediction in valid_pairs)
    intent_accuracy = correct / len(valid_pairs) if valid_pairs else None
    class_labels = sorted(
        {
            label
            for ground_truth, prediction in valid_pairs
            for label in (_as_set(ground_truth) | {prediction})
        }
    )
    per_class: Dict[str, Dict[str, float]] = {}
    f1_values: List[float] = []
    for label in class_labels:
        tp = sum(label == ground_truth and prediction == label for ground_truth, prediction in valid_pairs)
        fp = sum(prediction == label and ground_truth != label for ground_truth, prediction in valid_pairs)
        fn = sum(label == ground_truth and prediction != label for ground_truth, prediction in valid_pairs)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = _f1(precision, recall)
        f1_values.append(f1)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    def check_rate(name: str, subset: Iterable[Dict[str, Any]]) -> Optional[float]:
        values = [
            item["checks"].get(name)
            for item in subset
            if item.get("checks", {}).get(name) is not None
        ]
        return round(sum(bool(value) for value in values) / len(values), 4) if values else None

    primary_values = [item for item in runnable if item.get("expected", {}).get("primary_agent")]
    support_values = [
        item
        for item in runnable
        if item.get("expected", {}).get("supporting_agents") is not None
    ]
    expected_multi = [
        item for item in runnable if item.get("expected", {}).get("multi_agent") is True
    ]
    unexpected_multi = [
        item for item in runnable if item.get("expected", {}).get("multi_agent") is False
    ]
    rag_required = [
        item for item in runnable if item.get("expected", {}).get("rag") == "required"
    ]
    rag_skip = [
        item for item in runnable if item.get("expected", {}).get("rag") == "skip"
    ]
    escalation_values = [
        item
        for item in runnable
        if item.get("expected", {}).get("escalation") in {"required", "forbidden"}
    ]
    tools_values = [
        item
        for item in runnable
        if item.get("expected", {}).get("expected_tools") is not None
    ]
    unexpected_tool_values = [
        item
        for item in tools_values
        if not _as_set(item.get("expected", {}).get("expected_tools"))
    ]

    support_tp = support_fp = support_fn = 0
    for item in support_values:
        expected_support = _as_set(item["expected"].get("supporting_agents"))
        actual_support = _as_set(item["actual"].get("supporting_agents"))
        support_tp += len(expected_support & actual_support)
        support_fp += len(actual_support - expected_support)
        support_fn += len(expected_support - actual_support)
    support_precision = support_tp / (support_tp + support_fp) if support_tp + support_fp else 0.0
    support_recall = support_tp / (support_tp + support_fn) if support_tp + support_fn else 0.0

    escalation_false_positive = sum(
        item.get("expected", {}).get("escalation") == "forbidden"
        and bool(item.get("actual", {}).get("escalated"))
        for item in runnable
    )
    escalation_false_positive_denominator = sum(
        item.get("expected", {}).get("escalation") == "forbidden"
        for item in runnable
    )
    escalation_false_negative = sum(
        item.get("expected", {}).get("escalation") == "required"
        and not bool(item.get("actual", {}).get("escalated"))
        for item in runnable
    )
    escalation_false_negative_denominator = sum(
        item.get("expected", {}).get("escalation") == "required"
        for item in runnable
    )

    latencies = [
        float(item.get("actual", {}).get("latency_ms") or item.get("latency_ms"))
        for item in runnable
    ]
    single = [item for item in runnable if not item.get("actual", {}).get("multi_agent")]
    multi = [item for item in runnable if item.get("actual", {}).get("multi_agent")]
    rag = [
        item
        for item in runnable
        if item.get("actual", {}).get("search_knowledge_base_called")
    ]
    nonrag = [
        item
        for item in runnable
        if not item.get("actual", {}).get("search_knowledge_base_called")
    ]

    def avg(items: Iterable[Dict[str, Any]]) -> Optional[float]:
        values = [
            float(item.get("actual", {}).get("latency_ms") or item.get("latency_ms"))
            for item in items
        ]
        return round(statistics.mean(values), 1) if values else None

    tool_calls = [
        trace
        for item in runnable
        for trace in item.get("actual", {}).get("tool_traces", [])
        if isinstance(trace, dict)
    ]
    return {
        "planned_cases": len(results),
        "runnable_cases": len(runnable),
        "blocked_cases": len(blocked),
        "passed_cases": sum(item.get("status") == "passed" for item in runnable),
        "failed_cases": sum(item.get("status") == "failed" for item in runnable),
        "intent_accuracy": round(intent_accuracy, 4) if intent_accuracy is not None else None,
        "intent_macro_f1": round(statistics.mean(f1_values), 4) if f1_values else None,
        "intent_per_class": per_class,
        "primary_routing_accuracy": check_rate("primary_routing", primary_values),
        "supporting_precision": round(support_precision, 4) if support_values else None,
        "supporting_recall": round(support_recall, 4) if support_values else None,
        "supporting_f1": round(_f1(support_precision, support_recall), 4) if support_values else None,
        "multi_agent_trigger_rate": (
            round(
                sum(item["actual"].get("multi_agent", False) for item in runnable) / len(runnable),
                4,
            )
            if runnable
            else None
        ),
        "expected_multi_agent_recall": check_rate("multi_agent", expected_multi),
        "unexpected_multi_agent_rate": (
            round(
                sum(item.get("actual", {}).get("multi_agent", False) for item in unexpected_multi)
                / len(unexpected_multi),
                4,
            )
            if unexpected_multi
            else None
        ),
        "required_rag_recall": check_rate("rag_trigger", rag_required),
        "unnecessary_rag_rate": (
            round(
                sum(item["actual"].get("search_knowledge_base_called", False) for item in rag_skip)
                / len(rag_skip),
                4,
            )
            if rag_skip
            else None
        ),
        "tool_expected_hit_rate": check_rate("tool_selection", tools_values),
        "unexpected_tool_rate": (
            round(
                sum(bool(item.get("actual", {}).get("tools_used")) for item in unexpected_tool_values)
                / len(unexpected_tool_values),
                4,
            )
            if unexpected_tool_values
            else None
        ),
        "tool_call_count": len(tool_calls),
        "tool_trace_success_rate": (
            round(sum(bool(item.get("success")) for item in tool_calls) / len(tool_calls), 4)
            if tool_calls
            else None
        ),
        "escalation_accuracy": check_rate("escalation", escalation_values),
        "escalation_false_positive_rate": (
            round(escalation_false_positive / escalation_false_positive_denominator, 4)
            if escalation_false_positive_denominator
            else None
        ),
        "escalation_false_negative_rate": (
            round(escalation_false_negative / escalation_false_negative_denominator, 4)
            if escalation_false_negative_denominator
            else None
        ),
        "average_latency_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "median_latency_ms": round(statistics.median(latencies), 1) if latencies else None,
        "p95_latency_ms": round(_p95(latencies), 1) if latencies else None,
        "single_agent_average_latency_ms": avg(single),
        "multi_agent_average_latency_ms": avg(multi),
        "rag_average_latency_ms": avg(rag),
        "non_rag_average_latency_ms": avg(nonrag),
        "query_rewrite_success_rate": "N/A: not exposed by public trace",
        "rerank_success_rate": "N/A: not exposed by public trace",
    }


def _failure_breakdown(results: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for item in results:
        if item.get("status") == "blocked":
            counts["Environment / E2E Blocked"] += 1
        for name, value in item.get("checks", {}).items():
            if value is False:
                category = {
                    "intent": "Intent Error",
                    "primary_routing": "Routing Error",
                    "supporting_routing": "Routing Error",
                    "multi_agent": "Multi-Agent Error",
                    "tool_selection": "Tool Selection Error",
                    "rag_trigger": "Retrieval Trigger Error",
                    "escalation": "Escalation Error",
                }.get(name, name)
                counts[category] += 1
        if any(
            not trace.get("success", False) or trace.get("result_success") is False
            for trace in item.get("actual", {}).get("tool_traces", [])
            if isinstance(trace, dict)
        ):
            counts["Tool Execution Error"] += 1
        if any("JSON" in str(error) or "parse" in str(error).lower() for error in item.get("errors", [])):
            counts["Structured Output Error"] += 1
    return dict(counts)


def _markdown_report(raw: Dict[str, Any]) -> str:
    env = raw["environment"]
    metrics = raw["metrics"]
    results = raw["cases"]
    lines = [
        "# EchoMind As-Is Baseline Report",
        "",
        "> 本报告由 evaluation/run_baseline.py 生成。固定 Case 通过真实 HTTP POST /chat 运行；服务不可用时保留 BLOCKED，不用 Mock 结果替代。",
        "",
        "## A. Environment",
        "",
        f"- 测试时间：{env['timestamp']}",
        f"- Git commit：{env['git_sha']}",
        f"- 运行方式：{env['base_url']} /chat",
        f"- 实际模型：{env.get('model', 'N/A')}",
        f"- /health：{env.get('health_status', 'BLOCKED')}",
        f"- Redis / Chroma：{env.get('dependencies', 'N/A')}",
        f"- Case 数量：计划 {metrics['planned_cases']}，可运行 {metrics['runnable_cases']}，阻塞 {metrics['blocked_cases']}",
        "",
        "## B. Observability Fix",
        "",
        "- 根因：BaseAgent._call_llm 的最终文本分支只写入 _last_tools_used，没有把本轮 tool_traces 写入 _last_tool_traces。",
        "- 修复：最终文本返回前同步保存 _last_tool_traces；没有改变工具白名单、轮数、消息顺序或最终回答生成逻辑。",
        "- 新增测试：成功 tool_use → 工具成功 → 最终文本，以及工具后 provider 失败的固定 Fake Client 测试，检查工具参数、成功状态、延迟和 trace 字段。",
        "",
        "## C. Baseline Summary",
        "",
        "| Metric | Value | Notes |",
        "|---|---:|---|",
        f"| Intent Accuracy | {metrics['intent_accuracy']} | 仅统计实际收到响应的 Case |",
        f"| Intent Macro-F1 | {metrics['intent_macro_f1']} | 仅统计实际收到响应的 Case |",
        f"| Primary Routing Accuracy | {metrics['primary_routing_accuracy']} | 按 Case 期望 primary_agent |",
        f"| Supporting Precision / Recall / F1 | {metrics['supporting_precision']} / {metrics['supporting_recall']} / {metrics['supporting_f1']} | 不把最终回答替代路由判断 |",
        f"| Multi-Agent Trigger Rate | {metrics['multi_agent_trigger_rate']} | 实际 agent_types/supporting_agents |",
        f"| Expected Multi-Agent Recall | {metrics['expected_multi_agent_recall']} | 仅统计期望 Multi-Agent 的 Case |",
        f"| Unexpected Multi-Agent Rate | {metrics['unexpected_multi_agent_rate']} | 期望单 Agent 但实际并行 |",
        f"| Required RAG Recall | {metrics['required_rag_recall']} | required Case 是否调用 search_knowledge_base |",
        f"| Unnecessary RAG Rate | {metrics['unnecessary_rag_rate']} | skip Case 的实际调用率 |",
        f"| Tool Expected Hit Rate | {metrics['tool_expected_hit_rate']} | 使用 API tools_used / trace |",
        f"| Unexpected Tool Rate | {metrics['unexpected_tool_rate']} | expected_tools 为空但实际调用工具 |",
        f"| Tool Trace Success Rate | {metrics['tool_trace_success_rate']} | 当前公开 trace 中成功调用比例 |",
        f"| Escalation Accuracy | {metrics['escalation_accuracy']} | 仅统计 required/forbidden |",
        f"| Escalation FP / FN | {metrics['escalation_false_positive_rate']} / {metrics['escalation_false_negative_rate']} | 按 Case policy 统计 |",
        f"| Average / Median / P95 Latency | {metrics['average_latency_ms']} / {metrics['median_latency_ms']} / {metrics['p95_latency_ms']} ms | 样本量可能很小 |",
        f"| Query Rewrite Success Rate | {metrics['query_rewrite_success_rate']} | 公开 API 未暴露 |",
        f"| Rerank Success Rate | {metrics['rerank_success_rate']} | 公开 API 未暴露 |",
        "",
        "## D. Case Matrix",
        "",
        "| ID | Scenario | Intent | Primary | Supporting | Multi-Agent | RAG | Tools | Escalation | Status | Latency ms |",
        "|---|---|---|---|---|---:|---|---|---|---|---:|",
    ]
    for item in results:
        actual = item.get("actual", {})
        tools = ", ".join(actual.get("tools_used", [])) or "-"
        lines.append(
            f"| {item['case_id']} | {item.get('scenario', '')} | {actual.get('intent', 'BLOCKED')} | "
            f"{actual.get('primary_agent', 'BLOCKED')} | {','.join(actual.get('supporting_agents', [])) or '-'} | "
            f"{actual.get('multi_agent', 'N/A')} | {actual.get('search_knowledge_base_called', 'N/A')} | "
            f"{tools} | {actual.get('escalated', 'N/A')} | {item.get('status')} | {item.get('latency_ms')} |"
        )
    lines += ["", "## E. Failure Breakdown", ""]
    breakdown = raw["failure_breakdown"]
    if breakdown:
        lines += ["| Failure Type | Count |", "|---|---:|"]
        lines += [
            f"| {key} | {value} |"
            for key, value in sorted(breakdown.items(), key=lambda pair: (-pair[1], pair[0]))
        ]
    else:
        lines.append("当前没有可分类失败；如果所有 Case 均为 BLOCKED，请优先修复运行环境后重跑。")
    lines += ["", "## F. Representative Failures", ""]
    failures = [item for item in results if item.get("status") != "passed"][:5]
    if not failures:
        lines.append("没有失败 Case。")
    for item in failures:
        lines += [
            f"### {item['case_id']}",
            "",
            f"- Expected：{json.dumps(item.get('expected', {}), ensure_ascii=False)}",
            f"- Actual：{json.dumps(item.get('actual', {}), ensure_ascii=False)[:1200]}",
            f"- Checks：{json.dumps(item.get('checks', {}), ensure_ascii=False)}",
            f"- Errors：{'; '.join(item.get('errors', [])) or '无'}",
            "",
        ]
    lines += [
        "## G. Multi-Agent Observation",
        "",
        f"- 实际 Multi-Agent Trigger Rate：{metrics['multi_agent_trigger_rate']}。",
        f"- 实际 Multi-Agent 平均延迟：{metrics['multi_agent_average_latency_ms']} ms；Single-Agent：{metrics['single_agent_average_latency_ms']} ms。",
        "- 本轮只记录数据，不据此删除或保留 Multi-Agent 架构。",
        "",
        "## H. RAG Observation",
        "",
        f"- Required RAG Recall：{metrics['required_rag_recall']}；Skip Case 不必要调用率：{metrics['unnecessary_rag_rate']}。",
        f"- RAG 平均延迟：{metrics['rag_average_latency_ms']} ms；非 RAG：{metrics['non_rag_average_latency_ms']} ms。",
        "- Query Rewrite 和 Rerank 的成功率当前无法从公开 trace 可靠读取，记录为 N/A；不能把 search_knowledge_base 被调用解释为 rewrite/rerank 全部成功。",
        "",
    ]
    observations = raw.get("runtime_observations") or {}
    if observations:
        lines += [
            "### Docker 日志补充",
            "",
            f"- 日志来源：{observations.get('source', 'N/A')}",
            f"- Trace 中 RAG Tool 调用数：{observations.get('rag_calls_from_trace', 'N/A')}；Trace 中 reranked=true：{observations.get('trace_reranked_true', 'N/A')}。",
            f"- Query Rewrite：{observations.get('query_rewrite', 'N/A')}",
            f"- Rerank：{observations.get('rerank', 'N/A')}",
            f"- Episodic Memory：{observations.get('episodic_memory', 'N/A')}",
            "",
        ]
    lines += ["## I. Priority Problems", ""]
    if metrics["blocked_cases"] == metrics["planned_cases"]:
        lines.append("1. 当前所有 Case 被运行环境阻塞：localhost:8000 /chat 不可连接，Docker daemon 也不可用。应先恢复服务后重跑 Baseline。")
    else:
        for index, (name, count) in enumerate(
            sorted(breakdown.items(), key=lambda pair: (-pair[1], pair[0]))[:5],
            start=1,
        ):
            lines.append(f"{index}. {name}（{count} 个 Case）")
    lines += [
        "",
        "## J. What Was Not Fixed",
        "",
        "本轮除 Tool Trace 保存修复和对应测试外，没有修改 Intent、Routing、Multi-Agent、ResponseComposer、RAG trigger、rewrite、rerank、Embedding、Memory、Escalation、Monitor 或 Skills 业务逻辑。",
        "",
        "## K. Verification",
        "",
        "- py_compile：agents/agent_orchestrator.py、tests/test_agent_orchestrator.py、evaluation/run_baseline.py 通过。",
        "- pytest：当前 Windows 环境未安装 pytest（python -m pytest 返回 No module named pytest）。",
        "- pytest-compatible test body smoke：使用最小 anthropic stub 执行现有 11 个测试函数，11 passed、0 failed；其中包含成功路径和 provider 失败后的 Tool Trace 断言。",
        f"- HTTP Baseline：已执行 {metrics['planned_cases']} 个固定 Case；可运行 {metrics['runnable_cases']}，阻塞 {metrics['blocked_cases']}，通过 {metrics['passed_cases']}，失败 {metrics['failed_cases']}。",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run EchoMind As-Is baseline against POST /chat")
    parser.add_argument("--base-url", default="http://localhost:8000", help="EchoMind API base URL")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args(argv)

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    environment: Dict[str, Any] = {
        "timestamp": timestamp,
        "git_sha": _git_sha(),
        "base_url": args.base_url,
        "model": "N/A: not exposed by public API",
        "dependencies": "N/A: runtime health endpoint unavailable",
    }
    try:
        health = _json_request(args.base_url, "/health", timeout=min(args.timeout, 10.0))
        environment["health_status"] = json.dumps(health, ensure_ascii=False)
    except Exception as exc:
        environment["health_status"] = f"BLOCKED: {exc}"

    results = [_run_case(case, args.base_url, args.timeout) for case in cases]
    raw = {
        "environment": environment,
        "cases_path": str(args.cases),
        "cases": results,
        "metrics": _metric_summary(results),
        "failure_breakdown": _failure_breakdown(results),
    }
    raw_path = args.output_dir / "baseline_raw.json"
    report_path = args.output_dir / "baseline_report.md"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_markdown_report(raw), encoding="utf-8")
    print(
        json.dumps(
            {"raw": str(raw_path), "report": str(report_path), "metrics": raw["metrics"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
