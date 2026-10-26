# H2-4 裸基线部分运行报告（系统内存中断）

> **后续状态**：已按用户要求 `--resume` 补齐首轮 180 条，并额外跑了 117 个关键路径 k=2/3 run（未在 H2-4 计划内）。最终数据见 `FIRST_PASS.md`（首轮 180，H2-4 正式口径）、`final.json`（全部 297 个 run）和 `details.jsonl`。本文件保留为中断时快照，其中的类别比率以 144 条为分母。

- 运行：`2026-10-26`，`deepseek-flash`，profile `bare`（PolicyEngine 保留，其余 harness 组件关闭）
- 中断原因：**系统内存不足，Claude Code 终止后台进程**；不是代码/模型/预算失败，`halted=false`
- 进度：**144 / 180** case-runs（按 cases.json 顺序，最后完成 `out_of_scope_04`）
- 预算：331 次请求，input 780,636 / output 29,924，USD **0.2700996**（上限 700 / USD 1.0；剩余 369 请求 / USD 0.73）
- 明细：`progress.jsonl`、`details.jsonl`（144 条逐 check 完整）、`ledger.json`、`run.log`

## 部分结果（144 条，仅作中间信号）

| 指标 | 值 |
| --- | ---: |
| task_success_rate | **107 / 144 = 0.7431** |
| policy_blocked_attempts | **6**（6 个 case） |
| executed_violations | **0** |
| approval_required_attempts | 15 |
| overclaim_cases | 3（0.0208，措辞启发式） |
| loop_truncated | 0 |
| model_calls p50 / p95 | 2 / 3 |
| turns over 3 rounds | 0 / 144 |

| 类别 | Cases | Task success | Policy blocked | Overclaim |
| --- | ---: | ---: | ---: | ---: |
| faq | 24 | 0.25 | 0 | 0 |
| order | 16 | 1.0 | 0 | 0 |
| logistics | 16 | 1.0 | 0 | 0 |
| inventory | 12 | 1.0 | 0 | 0 |
| refund_allow | 14 | 0.9286 | 0 | 0 |
| refund_approval | 14 | 0.9286 | 0 | 1 |
| refund_deny | 16 | 0.8125 | 3 | 1 |
| cancel | 12 | 0.5 | 1 | 1 |
| ownership | 16 | 0.5625 | 2 | 0 |
| out_of_scope | 4 / 12 | 0.75 | 0 | 0 |
| injection | 0 / 14 | N/A | N/A | N/A |
| multi_turn | 0 / 14 | N/A | N/A | N/A |

**解释限制**：
- 部分运行按文件顺序执行，`out_of_scope` 只完成 4 条，`injection`、`multi_turn` 未开始；不能把这 144 条当作 180 条的替代。
- `ownership` 0.5625、`faq` 0.25 明显低于 H2-3 全 harness（1.0 / 0.2917 附近），与关闭 `error_feedback` 后模型看不到 `not_found` 错误直接相关；最终报告需逐条核对失败样本再下结论。
- `policy_blocked_attempts=6`、`executed_violations=0`：危险尝试全部被保留的 PolicyEngine 拦下，没有已执行的不安全动作。

## 恢复方式

```bash
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
uv run python -m evaluation.h2_4.run_baseline --resume --max-requests 700 --max-usd 1.0
```

`--resume` 只运行缺失的 36 条，并基于 `details.jsonl` 重新汇总全部 180 条；不重复已完成的 144 条。需要在用户明确要求后执行，不自动重启。
