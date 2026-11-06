# 评测结果与口径

本文汇总可复核的实测结果、方法和限制。原始报告保留在 `docs/reports/` 与 `evaluation/reports/`，数字以原始报告为准。

## 证据层级

| 层级 | 含义 | 项目例子 |
| --- | --- | --- |
| 确定性 / Fake SDK | 进程内脚本模型、固定工具结果 | H2-3 确定性层、H3-6 确定性用例 |
| 真实 Redis / Chroma | 真实外部存储，不调用 LLM | H4-1/H4-2 live、H2-5 检索 |
| 真实模型 | 真实 LLM 调用 | H2-3 real2、H2-4、H3-6 六臂 |
| 真实 HTTP E2E | 真实 uvicorn + HTTP + 模型 + 隔离服务 | H1-1、T11 |

不同层级的数字不能混写。确定性层 `task_success=1.0` 不表示模型工具选择质量。

## H2-3 规模化评测（真实模型）

- 模型：`deepseek-flash`；180 条用例；演示业务后端 + 真实 Chroma。
- 正式口径：180 条全量 **143/180 = 79.44%**；含关键路径额外 run 共 300 case-runs，**250/300 = 83.33%**。
- 预算：696 次请求，USD **0.599955**；resume 阶段 0 Connection error。
- 延迟：p50 **6,968 ms** / p95 **10,328 ms**。
- 安全：2 次 forbidden attempt（`refund_deny_03` run 2/3），均被 Policy 拒绝、executor 0；**没有已执行的不安全动作**。
- 限制：real2 首段被系统低内存中断，全量 180 的逐 check 安全/工具指标不可恢复；工具选择 1.0、参数准确率 None 只覆盖新增 62 个 detailed run。FAQ 29.17%、cancel 41.67%、multi_turn 71.43% 是真实行为差距。

完整报告：[H2-3](reports/H2-3.md)。

## H2-4 “只有模型 + 工具”基线

- 模型、评测集、模拟后端与 H2-3 相同；保留 PolicyEngine，关闭其余 harness 组件。
- 首轮 180：**138/180 = 76.67%**；H2-3 全 harness 为 **143/180 = 79.44%**。
- 主要机制差异：ownership **9/16** vs H2-3 **16/16**；其他类别 1–3 条波动在 12–24 条样本的噪声范围内。
- 安全：`executed_violations=0`；`policy_blocked_attempts=6`；`approval_required_attempts=16`；`overclaim_cases=1`（`injection_13`）。
- 预算：首轮 180 为 404 次请求 / USD 0.330853。
- 限制：关闭 3 轮上限后没有出现额外轮次，`loop_control` 在本评测集上没有可观察贡献；`context_compression` 因不使用 Redis Memory 无可观察差异。

完整报告：[H2-4](reports/H2-4.md)。

## H2-5 检索对比（B0 / semantic / hybrid）

数据：冻结 `a05-corpus-v1` + `a05-dataset-v2`（30 题：21 有答案 / 9 无答案）；dev 校准后 test 只跑一次。

| Group | Threshold | Recall@5 | MRR | No-answer FPR | Citation precision | Candidate Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0-calibrated | 0.20 | **9/21 = 42.86%** | **0.4286** | **8/9 = 88.89%** | 9/17 = 52.94% | 18/21 = 85.71% |
| semantic | 0.65 | 7/21 = 33.33% | 0.3333 | **3/9 = 33.33%** | **7/10 = 70.00%** | **21/21 = 100%** |
| hybrid | 0.65 | 7/21 = 33.33% | 0.3333 | **3/9 = 33.33%** | **7/10 = 70.00%** | **21/21 = 100%** |

结论：

- 语义/hybrid **没有在 Recall 上赢 B0-calibrated**；优势在 no-answer FPR 和引用精度。
- 语义候选 Recall@5 为 21/21，瓶颈是 0.65 阈值过滤，不是候选排序本身。
- hybrid 只在通过语义阈值的候选内做 BM25/RRF，最终指标与 semantic 相同；不能写成“混合更好”。
- 生产默认仍是 B0 词法基线，**未切换**。B0 历史 0.35 结果和冻结数据未覆盖。

完整报告：[H2-5](reports/H2-5.md)。

## H3-6 复合售后与 Harness 消融

24 条复合用例，每条 2–3 个诉求；6 臂同模型、同评测集、每臂独立预算。实际总消耗 **453 次请求 / USD 0.443368**。

| Arm | Task success | Demand completion | Executed violations | Forbidden attempts | Overclaim | Fault recovery |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 11/24 = 45.83% | 35/57 = 61.40% | 0 | 0 | 0 | 1/3 |
| bare | 13/24 = 54.17% | 38/57 = 66.67% | 0 | 0 | 0 | 2/3 |
| no_guardrails | 7/24 = 29.17% | 29/57 = 50.88% | **4** | 0 | 0 | 1/3 |
| no_error_feedback | 11/24 = 45.83% | 38/57 = 66.67% | 0 | 0 | 0 | 1/3 |
| no_context_compression | 9/24 = 37.50% | 31/57 = 54.39% | 0 | 1（handoff，被拒） | 0 | 1/3 |
| no_loop_control | 13/24 = 54.17% | 40/57 = 70.18% | 0 | 0 | 0 | 2/3 |

关键结论：

- **护栏是本轮最明确的组件信号**：`no_guardrails` 关闭 `policy_guard` + `output_consistency` 后出现 4 个已执行越权完成；full 为 0。
- `bare` 和 `no_loop_control` 比 full 多通过同样 2 条，其中一条 full 因 `budget_exhausted` 停止；3 轮上限可能是复合请求的绑定因素，但每臂 1 次、温度非零，不能直接改生产默认。
- 真实模型主要失败来源是反问确认、越权订单只说明“查不到”而不调用 action、FAQ 多为 low_confidence/no_answer；不是 harness 执行错误。
- 故障恢复真实模型只有 1/3；确定性层 3/3 只证明 harness 能恢复或如实失败。

完整报告：[H3-6](reports/H3-6.md)。

## 历史基线（只读）

- **T10**：controlled demo workload，3 × 10 cases / topology，not production benchmark。Multi/Single 均 24/30；平均延迟 6,633.3 / 3,937.1 ms；tool calls 78 / 59；model calls 115 / 76。支持当前 workload 简化，不代表真实协作收益或生产 SLA。
- **T11**：真实 HTTP、模型、Redis/Chroma，18/18；包含跨轮订单号、动态 Provider 刷新、异步偏好落库、隔离和 Redis 故障关闭。不是生产规模或长期稳定性测试。
- **T09**：2026-09-30 十场景基线，intent 7/10、tool selection 7/10、arguments 6/6、unnecessary 5/10、strict E2E 6/10；不与新 citation contract 混算。

## 复现入口

```bash
uv lock --check
uv run python -m pytest -q

# H2-3 确定性层
uv run python -m evaluation.h2_3.run_suite

# H3-6 确定性复合 runner
uv run python -m evaluation.h3_6.run_composite

# 真实模型/检索实验按各报告中的预算和环境变量单独运行
```

真实模型实验需要显式预算授权；历史报告目录只读保留。

## 相关文档

- [架构与边界](architecture.md)
- [已知限制](limitations.md)
- [运行与部署](operations.md)
