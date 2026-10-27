# H3-6 Harness 消融实验（真实模型）

- 总请求/成本上限: 1200 / USD 2.0
- 模型: deepseek-flash（各臂相同）
- 评测集: `evaluation/h3_6/cases.json`（24 条复合用例）
- 每臂 1 次，同评测集、同 per-arm 上限

| Arm | Cases | Task success | Demand completion | Executed violations | Forbidden attempts | Overclaim | Fault recovery | Avg steps | Calls p50/p95 | Requests | Cost USD | Halted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| full | 24 | 0.4583 | 0.614 | 0 | 0 | 0 | 1/3 | 4.375 | 3 / 3 | 71 | 0.069866 | False |
| bare | 24 | 0.5417 | 0.6667 | 0 | 0 | 0 | 2/3 | 4.875 | 3 / 4 | 79 | 0.076372 | False |
| no_guardrails | 24 | 0.2917 | 0.5088 | 4 | 0 | 0 | 1/3 | 4.25 | 3 / 3 | 71 | 0.069507 | False |
| no_error_feedback | 24 | 0.4583 | 0.6667 | 0 | 0 | 0 | 1/3 | 4.6667 | 3 / 3 | 77 | 0.073868 | False |
| no_context_compression | 24 | 0.375 | 0.5439 | 0 | 1 | 0 | 1/3 | 4.25 | 3 / 3 | 70 | 0.068659 | False |
| no_loop_control | 24 | 0.5417 | 0.7018 | 0 | 0 | 0 | 2/3 | 4.6667 | 3 / 4 | 79 | 0.079638 | False |

## 逐诉求状态与审批

| Arm | completed | awaiting_approval | rejected | failed | no_answer | not_called | Policy blocked | Approval required |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 20 | 4 | 2 | 1 | 5 | 15 | 2 | 4 |
| bare | 21 | 5 | 3 | 1 | 6 | 12 | 3 | 5 |
| no_guardrails | 24 | 0 | 0 | 1 | 7 | 17 | 0 | 0 |
| no_error_feedback | 22 | 5 | 2 | 1 | 7 | 12 | 2 | 5 |
| no_context_compression | 18 | 3 | 1 | 1 | 6 | 19 | 1 | 3 |
| no_loop_control | 24 | 5 | 2 | 1 | 7 | 10 | 2 | 5 |

## 口径

- 安全违规按“实际执行/越权完成”计；被 Policy 拒绝的尝试单独看 policy_blocked 明细。
- 24 条、每臂 1 次，单条差异约 4pp；小于 2-3 条的差异不作为组件结论。
- `bare` 仍保留 PolicyEngine（H2-4 定义）；`no_guardrails` 才关闭 Policy 与输出一致性。
- `no_loop_control` 的 10 轮是 runner 实验界，不是交付护栏。
