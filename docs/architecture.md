# CartCare 架构与边界

本文是 README 的详细版，说明可执行调用路径、Harness 分层和不可违反的边界。代码定位见 [`wiki/重点代码.md`](../wiki/重点代码.md)。

## 请求路径

```text
POST /chat
→ AuthAdapter → Principal（服务端身份；body/X-User-Id 不能创建身份）
→ MemoryManager.get_context（Redis 工作记忆 + Chroma 过滤后的长期记录）
→ SupportRuntime.run
→ SingleSupportAgent.handle
→ BaseAgent._call_llm（默认最多 3 轮 Tool Calling）
→ agents/tools.py + core/tool_contract.py
    → RAG：静态 FAQ / 版本化政策（Chroma HTTP）
    → Providers：订单、物流、库存、退款等实时事实
    → ActionService：Principal gate / Policy / HITL / 幂等 / Executor
    → HandoffService：Principal / 策略 / 幂等 / 模拟交接记录
→ 输出一致性检查 / 逐动作回执
→ Memory 回写、后台画像
→ ChatResponse + Trace
```

生产入口不经过 Intent → specialist dispatch、supporting Agent 或 Composer。旧 Multi 类保留给历史实验和回归，不是生产拓扑。

## Harness 七层

| 层 | 责任 | 关键位置 |
| --- | --- | --- |
| 工具循环 | 轮次、步数、token、重复调用、单步超时、停止原因 | `agents/agent_orchestrator.py`、`core/stop_reason.py` |
| 工具契约 | 严格 schema、read/write/dangerous、typed errors、结果截断 | `core/tool_contract.py` |
| 上下文管理 | 每轮上下文构成、预算、工具结果压缩 | `core/context_budget.py` |
| 状态与中断恢复 | PendingAction、检查点、崩溃恢复、幂等回执 | `actions/`、`core/checkpoint*.py` |
| 护栏 | Principal、归属、Policy、审批、输出一致性、幂等 | `core/auth.py`、`policies/`、`core/output_consistency.py` |
| 可观测 | 工具级 Trace、按步 token/延迟/工具/停止原因 | `core/step_trace.py`、`/trace/tool/{request_id}` |
| 评测框架 | 组件开关、假模型、回放、故障注入、轨迹评分、pass^k、消融 | `evaluation/` |

Harness 组件开关只在隔离评测环境中关闭；线上 `/chat` 不暴露开关。

## Agent 六项能力

| 能力 | 观察指标 | 主要证据 |
| --- | --- | --- |
| 选工具、抽参数 | 工具选择准确率、参数准确率 | H1-1、H2-3 |
| 缺信息先澄清 | 澄清率、误执行率 | H1-1、H2-3 |
| 基于证据回答/拒答 | Recall@5、引用正确率、拒答率 | H2-5 |
| 多诉求规划 | 复合任务严格成功率、诉求级完成率 | H3-6 |
| 根据错误纠错 | 故障注入下的恢复成功率 | H3-2、H3-6 |
| 如实汇报部分成功 | 回答与 ActionResult 一致率 | H3-4、H3-6 |

## 不可违反的边界

### RAG 与实时数据

- RAG 只用于相对稳定的 FAQ、退款/物流/售后政策、商品文档和会员规则。
- 订单、物流、库存、支付、退款状态和客户归属必须通过 Provider 查询；不能从检索文本或历史回复推断。
- `usable` 只表示检索片段通过来源、版本、评分和生命周期校验，不代表逐句事实正确。

### LLM 与确定性逻辑

- LLM 负责理解、澄清、选工具、收集参数、在单 Agent 工具循环内做多步规划和生成回复。
- 确定性代码负责退款/取消资格、金额限制、权限、归属、状态转换、幂等、风险门控和审批。
- 不可协商的业务规则不只写在 Prompt 里；退款/取消必须经过 PolicyEngine，危险动作必须经过 ActionService。

### 单 Agent + 工具

- 保持单 Agent + 工具，不重建多 Agent，不引入独立 Planner，不在主链路前加独立意图分类。
- 意图标签只用于越界兜底和离线分析。

### 工具与动作

- 工具区分 read / write / dangerous；只有幂等的只读工具可以自动重试。
- 读工具超时后不自动重试：同步 worker 可能仍在运行，自动重试会重叠。
- 状态变更动作必须具备严格输入校验、权限/归属、超时边界、幂等键、重复执行防护、typed errors 和可审计结果。
- 身份只来自服务端 Principal；客户端 user_id、X-User-Id 和 role 不能创建身份。

## 持久化与恢复

- PendingAction、审批检查点和恢复回执持久化在 Redis；检查点包含 request/conv/user、动作状态、H3-5 安全 steps 和剩余动作。
- 审批前/中/执行中/执行后的进程崩溃都有恢复路径；执行已派发但没有回执时按 `execution_unknown` 失败，不自动重放。
- 恢复回执使用 `wm:once:` marker 最多写一次。
- 单实例边界：Redis 锁和 Memory 锁都是进程内锁，多 worker 并发不在承诺内。
- 模拟业务表仍是内存 fixture；动作/检查点持久化不等于商城数据持久化。

## 可观测与隐私

Trace 记录 request_id、工具、校验参数、结果摘要、检索与引用、Policy 决定、审批状态、每步 token/延迟、停止原因和错误类型。不保存、不暴露隐藏推理，也不记录原始 Memory 内容。Trace 是进程内有界队列，重启丢失。

## 评测隔离

`/eval/run` 每轮通过独立 Runtime、模拟业务 state、ActionService/Store 和 RAG 管理器执行；使用固定测试 Principal，保留 Policy/HITL，不接入聊天 Memory。评测不会回退到生产 Runtime。

## 相关文档

- [评测结果与口径](evaluation.md)
- [运行与部署](operations.md)
- [已知限制](limitations.md)
- [命名迁移](naming.md)
