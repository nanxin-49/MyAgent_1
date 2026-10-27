"""H3-6 real-model ablation wrapper: six harness arms on the composite set.

Each arm is a separate ``evaluation.h2_3.real_model`` process with its own
ledger and hard request/USD cap. Defaults: 6 x 190 requests / USD 0.31 plus a
30-request smoke run, all below the authorized 1200 requests / USD 2.0.

The subprocess environment drops the inherited ``ANTHROPIC_BASE_URL`` so the
repository ``.env`` (loaded by the runner) is used instead of the local Claude
Code proxy. The wrapper never reads or prints ``.env``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from evaluation.h3_6.composite import evaluate_demands, summarize_arm

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUT = ROOT / "evaluation/reports/H3-6"
ARM_PROFILES = (
    "full",
    "bare",
    "no_guardrails",
    "no_error_feedback",
    "no_context_compression",
    "no_loop_control",
)
DEFAULT_PER_ARM_REQUESTS = 190
DEFAULT_PER_ARM_USD = 0.31
DEFAULT_TOTAL_REQUESTS = 1200
DEFAULT_TOTAL_USD = 2.0
SMOKE_REQUESTS = 30
SMOKE_USD = 0.05
DEMO_CASE = "composite_refund_cancel_faq"


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    # Claude Code's shell sets a local Anthropic proxy; dotenv does not
    # override existing variables, so the model runner would hit the proxy.
    env.pop("ANTHROPIC_BASE_URL", None)
    return env


def build_command(profile: str, *, cases: Path, output: Path, max_requests: int,
                  max_usd: float, only: list[str] | None = None,
                  resume: bool = False) -> list[str]:
    command = [
        sys.executable, "-m", "evaluation.h2_3.real_model",
        "--cases", str(cases),
        "--output-dir", str(output),
        "--profile", profile,
        "--max-requests", str(max_requests),
        "--max-usd", str(max_usd),
        "--no-key-runs",
    ]
    if only:
        command += ["--only", ",".join(only)]
    command.append("--resume" if resume else "--fresh")
    return command


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rescore_details(details: list[dict], cases_by_id: dict[str, dict]) -> list[dict]:
    """Re-score stored composite rows with the current deterministic checker.

    The real-model runner writes checks at run time. Re-scoring from the stored
    traces keeps the ablation summary on one version of the rules even when a
    case is resumed or the scorer is fixed after the run.
    """
    for row in details:
        case = cases_by_id.get(row.get("case_id"))
        if not case or not case.get("demands"):
            continue
        turn = (row.get("turns") or [{}])[0]
        checks, demands = evaluate_demands(
            case, turn.get("tool_traces") or [], turn.get("response") or "",
            row.get("fault_events") or [])
        row["checks"] = checks
        row["demand_results"] = demands
        row["passed"] = bool(checks) and all(checks.values())
    return details


def load_arm(profile: str, output: Path, cases_by_id: dict | None = None) -> dict:
    details = _read_jsonl(output / "details.jsonl")
    if cases_by_id:
        details = rescore_details(details, cases_by_id)
    ledger = _read_json(output / "ledger.json")
    summary = summarize_arm(details)
    if cases_by_id:
        summary["cases_expected"] = len(cases_by_id)
        summary["partial"] = summary["cases"] < len(cases_by_id)
    summary.update({
        "profile": profile,
        "requests": int(ledger.get("requests", 0) or 0),
        "input_tokens": int(ledger.get("input_tokens", 0) or 0),
        "output_tokens": int(ledger.get("output_tokens", 0) or 0),
        "cost_usd": round(float(ledger.get("cost_usd", 0.0) or 0.0), 6),
        "budget_max_requests": ledger.get("max_requests"),
        "budget_max_usd": ledger.get("max_usd"),
        "halted": bool(ledger.get("halted", False)),
    })
    return summary


def run_arm(profile: str, *, cases: Path, out_root: Path, max_requests: int,
            max_usd: float, resume: bool = False,
            cases_by_id: dict | None = None) -> dict:
    output = out_root / "arms" / profile
    output.mkdir(parents=True, exist_ok=True)
    command = build_command(profile, cases=cases, output=output,
                            max_requests=max_requests, max_usd=max_usd,
                            resume=resume)
    log_path = output / "run.log"
    with log_path.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(command, cwd=ROOT, env=subprocess_env(),
                                   stdout=handle, stderr=subprocess.STDOUT,
                                   text=True, check=False)
    summary = load_arm(profile, output, cases_by_id)
    summary["exit_code"] = completed.returncode
    summary["command"] = " ".join(command)
    return summary


def run_smoke(*, cases: Path, out_root: Path,
              cases_by_id: dict | None = None) -> dict:
    output = out_root / "smoke"
    output.mkdir(parents=True, exist_ok=True)
    _, payload = _load_case_ids(cases)
    only = payload[:2]
    command = build_command("full", cases=cases, output=output,
                            max_requests=SMOKE_REQUESTS, max_usd=SMOKE_USD,
                            only=only)
    log_path = output / "run.log"
    with log_path.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(command, cwd=ROOT, env=subprocess_env(),
                                   stdout=handle, stderr=subprocess.STDOUT,
                                   text=True, check=False)
    summary = load_arm("full", output, cases_by_id)
    summary["exit_code"] = completed.returncode
    summary["smoke_cases"] = only
    return summary


def _load_case_ids(path: Path) -> tuple[dict, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, [case["id"] for case in data.get("cases") or []]


def _demo_markdown(full_output: Path, case_id: str = DEMO_CASE) -> str:
    details = _read_jsonl(full_output / "details.jsonl")
    row = next((item for item in details
                if item.get("case_id") == case_id and item.get("passed")), None)
    if row is None:
        row = next((item for item in details
                    if item.get("passed")
                    and len(item.get("demand_results") or []) >= 2), None)
    if row is None:
        row = next((item for item in details if item.get("case_id") == case_id), None)
    lines = ["# H3-6 录屏候选链路（真实模型）", ""]
    if row is None:
        lines.append(f"- 未找到 case `{case_id}` 的真实模型记录。")
        return "\n".join(lines) + "\n"
    turn = (row.get("turns") or [{}])[0]
    lines += [f"- case: `{row.get('case_id')}`", f"- passed: {row.get('passed')}",
              f"- stop_reason: {turn.get('stop_reason')}", "",
              "## 用户消息", "", turn.get("message", ""), "",
              "## Agent 回复", "", turn.get("response", ""), "",
              "## 逐诉求终态", "",
              "| 诉求 | 期望 | 实际 | 通过 |", "| --- | --- | --- | --- |"]
    for demand in row.get("demand_results") or []:
        lines.append(f"| {demand['id']} | {demand['expected_status']} | "
                     f"{demand['status']} | {demand['passed']} |")
    lines += ["", "## 动作回执", "",
              "| 工具 | 状态 | action_id | Policy | 复用 |",
              "| --- | --- | --- | --- | --- |"]
    for trace in turn.get("tool_traces") or []:
        action = trace.get("action_result") or {}
        if not action:
            continue
        lines.append(f"| {trace.get('tool_name')} | {action.get('status')} | "
                     f"{action.get('action_id')} | {action.get('policy_decision')} | "
                     f"{action.get('reused')} |")
    lines += ["", "## 按步轨迹", "",
              "| step | input | output | latency_ms | tools | stop_reason |",
              "| ---: | ---: | ---: | ---: | --- | --- |"]
    for step in turn.get("steps") or []:
        tools = ", ".join(item.get("tool_name", "?") for item in step.get("tools") or [])
        lines.append(f"| {step.get('step')} | {step.get('input_tokens')} | "
                     f"{step.get('output_tokens')} | {step.get('latency_ms')} | "
                     f"{tools} | {step.get('stop_reason')} |")
    lines += ["", "## 录屏提示", "",
              "1. 用同一条消息重新发起 `/chat`，记录 request_id。",
              "2. 打开 `/trace/tool/{request_id}` 展示 `steps`、`tool_calls` 和逐诉求回执。",
              "3. 对照逐诉求终态说明哪些已完成、哪些等待审批或失败。",
              "4. 这里的数字是真实模型 + 模拟业务后端，不是生产 SLA。"]
    return "\n".join(lines) + "\n"


def _ablation_markdown(arms: list[dict], *, total_requests: int,
                       total_usd: float) -> str:
    lines = ["# H3-6 Harness 消融实验（真实模型）", "",
             f"- 总请求/成本上限: {total_requests} / USD {total_usd}",
             f"- 模型: deepseek-flash（各臂相同）",
             f"- 评测集: `evaluation/h3_6/cases.json`（24 条复合用例）",
             f"- 每臂 1 次，同评测集、同 per-arm 上限", "",
             "| Arm | Cases | Task success | Demand completion | Executed violations | "
             "Forbidden attempts | Overclaim | Fault recovery | Avg steps | Calls p50/p95 | "
             "Requests | Cost USD | Halted |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |"]
    for arm in arms:
        calls = f"{arm.get('model_calls_p50')} / {arm.get('model_calls_p95')}"
        recovery = (f"{arm.get('fault_recovered')}/{arm.get('fault_cases')}"
                    if arm.get("fault_cases") else "n/a")
        lines.append(
            f"| {arm['profile']} | {arm.get('cases')} | {arm.get('task_success_rate')} | "
            f"{arm.get('demand_completion_rate')} | "
            f"{arm.get('cases_with_executed_violation')} | "
            f"{arm.get('cases_with_forbidden_attempt')} | "
            f"{arm.get('cases_with_answer_overclaim')} | {recovery} | "
            f"{arm.get('average_tool_steps')} | {calls} | {arm.get('requests')} | "
            f"{arm.get('cost_usd')} | {arm.get('halted')} |")
    lines += ["", "## 逐诉求状态与审批", "",              "| Arm | completed | awaiting_approval | rejected | failed | "
              "no_answer | not_called | Policy blocked | Approval required |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for arm in arms:
        counts = arm.get("demand_status_counts") or {}
        lines.append(
            f"| {arm['profile']} | {counts.get('completed', 0)} | "
            f"{counts.get('awaiting_approval', 0)} | {counts.get('rejected', 0)} | "
            f"{counts.get('failed', 0)} | {counts.get('no_answer', 0)} | "
            f"{counts.get('not_called', 0)} | {arm.get('policy_blocked_attempts', 0)} | "
            f"{arm.get('approval_required_attempts', 0)} |")
    lines += ["", "## 口径", "",
              "- 安全违规按“实际执行/越权完成”计；被 Policy 拒绝的尝试单独看 policy_blocked 明细。",
              "- 24 条、每臂 1 次，单条差异约 4pp；小于 2-3 条的差异不作为组件结论。",
              "- `bare` 仍保留 PolicyEngine（H2-4 定义）；`no_guardrails` 才关闭 Policy 与输出一致性。",
              "- `no_loop_control` 的 10 轮是 runner 实验界，不是交付护栏。"]
    partial = [arm for arm in arms if arm.get("partial")]
    if partial:
        lines += ["", "## 未完成臂", ""]
        for arm in partial:
            lines.append(
                f"- `{arm['profile']}`: {arm.get('cases')}/{arm.get('cases_expected')} 条；"
                "后台任务被系统低内存终止，未完成，不能与完整臂直接比较。")
    return "\n".join(lines) + "\n"


def _existing_arms(out_root: Path, cases_by_id: dict | None = None) -> dict[str, dict]:
    arms = {}
    for profile in ARM_PROFILES:
        output = out_root / "arms" / profile
        if (output / "ledger.json").exists():
            arms[profile] = load_arm(profile, output, cases_by_id)
    return arms


def _write_reports(out_root: Path, arms: list[dict], *, total_requests: int,
                   total_usd: float) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "echomind.h3_6.ablation", "version": 1,
               "total_requests_cap": total_requests, "total_usd_cap": total_usd,
               "arms": arms}
    (out_root / "ablation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    (out_root / "ablation.md").write_text(
        _ablation_markdown(arms, total_requests=total_requests,
                           total_usd=total_usd),
        encoding="utf-8")
    (out_root / "DEMO.md").write_text(
        _demo_markdown(out_root / "arms" / "full"), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--profiles", default=",".join(ARM_PROFILES))
    parser.add_argument("--per-arm-requests", type=int, default=DEFAULT_PER_ARM_REQUESTS)
    parser.add_argument("--per-arm-usd", type=float, default=DEFAULT_PER_ARM_USD)
    parser.add_argument("--total-requests", type=int, default=DEFAULT_TOTAL_REQUESTS)
    parser.add_argument("--total-usd", type=float, default=DEFAULT_TOTAL_USD)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                        help="re-score existing arm artifacts and rewrite reports")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    cases = Path(args.cases)
    out_root = Path(args.out)
    data, _ = _load_case_ids(cases)
    cases_by_id = {case["id"]: case for case in data.get("cases") or []}
    if args.smoke:
        summary = run_smoke(cases=cases, out_root=out_root, cases_by_id=cases_by_id)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 0 if summary.get("exit_code") == 0 else 1
    if args.report_only:
        arms = [load_arm(profile, out_root / "arms" / profile, cases_by_id)
                for profile in ARM_PROFILES
                if (out_root / "arms" / profile / "ledger.json").exists()]
        _write_reports(out_root, arms, total_requests=args.total_requests,
                       total_usd=args.total_usd)
        print(json.dumps([{"profile": arm["profile"], "cases": arm["cases"],
                           "task_success_rate": arm["task_success_rate"]}
                          for arm in arms], ensure_ascii=False, indent=2))
        return 0
    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    arms = []
    spent_requests = spent_usd = 0.0
    for profile in profiles:
        if spent_requests >= args.total_requests or spent_usd >= args.total_usd:
            print(f"total budget reached before {profile}", file=sys.stderr)
            break
        summary = run_arm(profile, cases=cases, out_root=out_root,
                          max_requests=args.per_arm_requests,
                          max_usd=args.per_arm_usd, resume=args.resume,
                          cases_by_id=cases_by_id)
        arms.append(summary)
        spent_requests += int(summary.get("requests") or 0)
        spent_usd += float(summary.get("cost_usd") or 0.0)
        print(json.dumps({"profile": profile,
                          "passed": summary.get("case_passed"),
                          "cases": summary.get("cases"),
                          "requests": summary.get("requests"),
                          "cost_usd": summary.get("cost_usd"),
                          "halted": summary.get("halted")}, ensure_ascii=False),
              flush=True)
    merged = _existing_arms(out_root, cases_by_id)
    for arm in arms:
        merged[arm["profile"]] = arm
    ordered = [merged[profile] for profile in ARM_PROFILES if profile in merged]
    _write_reports(out_root, ordered, total_requests=args.total_requests,
                   total_usd=args.total_usd)
    return 0 if all(not arm.get("halted") for arm in ordered) else 1


if __name__ == "__main__":
    raise SystemExit(main())
