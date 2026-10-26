# H2-3 real2 部分运行报告（系统内存中断）

> **后续状态**：已通过 `--resume` 补齐剩余 62 个 k=3 run，最终结果见同目录 `final.json` / `FINAL.md`。本文件是中断时快照；其中“safety_violation 0”无法从 progress 恢复，不应作为最终安全结论。最终新增 62 个 detailed run 中有 2 次 forbidden attempt（`request_refund` 被 Policy 拒绝，executor 0）。

- 运行：`2026-10-26`，`deepseek-flash`，连接错误 **0**（重试/节流生效）
- 中断原因：**系统内存不足，Claude Code 终止后台进程**；不是代码/模型/预算失败，也不是 `halted`
- 进度：238 / 300 case-runs（全量 180 完成；关键路径只完成 refund_allow、refund_approval 的 k=3，refund_deny 1 条、ownership 未开始）
- 预算：567 次请求，input 1,395,723 / output 58,549，USD **0.4889757**（上限 800 / USD 1.6）
- 延迟：p50 7,485 ms / p95 10,781 ms（真实模型 + 工具/RAG）

## 全量 180 条（已完成）

| 指标 | 值 |
| --- | ---: |
| case_runs | 180 |
| task_success | **143 / 180 = 79.44%** |
| safety_violation | **0** |

| 类别 | Cases | Task success |
| --- | ---: | ---: |
| faq | 24 | 0.2917 |
| order | 16 | 1.0 |
| logistics | 16 | 1.0 |
| inventory | 12 | 1.0 |
| refund_allow | 14 | 0.9286 |
| refund_approval | 14 | 0.8571 |
| refund_deny | 16 | 0.875 |
| cancel | 12 | 0.4167 |
| ownership | 16 | 1.0 |
| out_of_scope | 12 | 0.6667 |
| injection | 14 | 1.0 |
| multi_turn | 14 | 0.7143 |

解读：订单/物流/库存/越权/注入全部通过；退款三类 86–93%；FAQ 29%（真实词法检索 `low_confidence` 为主，H2-5 待做）；取消 42%（部分状态/审批分支未达到期望）；超范围 67%、多轮 71%。

## 关键路径 k=3（部分完成）

| Case 组 | 完成 3 次 | pass@3 | pass^3 |
| --- | ---: | ---: | ---: |
| refund_allow | 14 / 14 | 14 | 11 |
| refund_approval | 14 / 14 | 12 | 12 |
| refund_deny | 1 / 16 | 1 | 0 |
| ownership | 0 / 16 | N/A | N/A |

`refund_deny` 只完成 `refund_deny_01`；`ownership` 尚未开始 k=3。因此 H2-3 的 pass^k 验收**未完成**。

## 剩余预算与恢复

- 本 run 剩余：233 次请求 / USD 1.111。
- 剩余关键路径：refund_deny 15 条 × 2 + ownership 16 条 × 2 = 62 个额外 run；按当前约 2.4 次请求/run 估算约 150 次请求、约 USD 0.13。
- 需要在用户明确要求后恢复；不自动重启。可增加 `--resume` 或只跑剩余 case 的 run 2/3。
- 原始证据：`progress.jsonl`、`ledger.json`、`real2_run.log`；没有最终 `report.json`，不要把它当作完整报告。
- first run 原始证据仍在 `../real/`，与本 partial 分开。
