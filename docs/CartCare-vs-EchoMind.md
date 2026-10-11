# CartCare 与原始 EchoMind 的差别

CartCare 从通用多 Agent 客服演示收敛为电商 Single Support Agent。主要变化是动态业务事实、确定性规则、审批与执行边界、可重复评测和可观察演示，而不是增加 Agent 数量。当前商城和退款执行仍是 fixture / 内存模拟；正式认证、真实支付和客服平台接单尚未接入。

## 比较基线

这里的“原始 Ecomind”按仓库原名 **EchoMind** 理解。Git 首次上传为 `b8c2979`；该提交的 README、AgentOrchestrator 和 Memory 可说明最初方向，但当时没有 `api/main.py`，不能据此声称完整 HTTP 链路已运行。为比较可执行请求路径，另取 CartCare 业务层加入前的 `5d6c7e7`：其 `/chat` 已接入 Memory、IntentRecognizer 和 AgentOrchestrator。当前对照为 `09efd3443d2e7b6e03fba7d13fe660c483b30583` 加本轮目录与文档整理；本轮不改变业务主链路。

## 具体变化

| 方面 | 原始方向或业务层加入前基线 | 当前 CartCare | 代码或验证入口 |
|---|---|---|---|
| 产品范围 | 通用客服，General / Technical / Billing / Escalation 多角色 | FAQ、政策、商品、订单、物流、库存、售后 | `agents/support_agent.py`、`demo/static/scenarios.json` |
| 主链路 | `5d6c7e7`：Memory → recognize_intent → AgentOrchestrator 路由 → Agent | Memory → SupportRuntime → SingleSupportAgent → Tool Calling；Intent 不参与 `/chat` dispatch | `api/main.py:chat`、`tests/test_support_production.py` |
| 多 Agent 取舍 | 以意图路由、协作与合成为设计方向 | T10 演示对比后选择 Single；旧 Multi 只供实验，BaseAgent / 类型仍被主链复用 | `evaluation/reports/t10_topology_comparison.md` |
| 动态业务事实 | `5d6c7e7` 工具主要为上下文、字段检查、诊断、金额比较和 handoff 摘要；无当前 Provider 业务层 | 五类只读 Provider + 工具，按请求身份核查归属；fixture 明确标为模拟 | `providers/`、`agents/tools.py:build_business_tools` |
| 敏感动作 | 无当前 PolicyEngine / PendingAction / ActionService 执行路径 | 确定性退款/取消规则，allow / deny / require_approval；审批、恢复、二次校验和幂等模拟执行 | `policies/`、`actions/`、`tests/test_action_service.py` |
| 工具边界 | 早期工具注册与调用；没有当前共享严格契约 | schema、read/write/dangerous、typed errors、读工具重试与 Trace；危险动作受 ActionService 控制 | `core/tool_contract.py`、`tests/test_tool_contract.py` |
| RAG | 早期知识检索与 fallback；不具备当前来源和状态契约 | 静态知识与动态事实分离；来源/文档/政策版本；usable / low_confidence / no_answer / degraded，只有 usable 给可靠 citation | `mcp/rag_contract.py`、`mcp/knowledge_base.py` |
| Chroma | 初次上传使用 PersistentClient；`5d6c7e7` 仍有本地分支 | 仅外部 HttpClient，连接失败明确报错；词面 embedding 为待校准基线 | `memory/conversation_memory.py`、`mcp/knowledge_embeddings.py` |
| Memory | 工作记忆、摘要、情景记忆、画像；早期包含模型摘要和画像提炼 | Redis 24h，15 条压缩保留最近 5 条；长期主题/明确偏好 30/180 天；动态业务状态不作为长期事实 | `memory/policy.py`、`tests/test_memory_boundary.py` |
| 可观察性 | 早期 Monitor / Eval，后续基线已有工具 Trace | 有界请求 Trace、工具参数与结果、引用、Policy/HITL、Memory 状态和模型调用；同源 `/demo` | `core/model_observation.py`、`demo/`、`docs/t12-trace-demo-validation.md` |
| 评测与环境 | 早期 requirements / Docker 与宽泛主观评测 | Python 3.12 + uv 锁定；业务控制专项测试、独立 component replay、真实 HTTP 演示记录 | `pyproject.toml`、`uv.lock`、`evaluation/README.md` |

## 为什么采用 Single

[T10 历史实验](../evaluation/reports/t10_topology_comparison.md)为 3 轮 × 10 场景 × 2 拓扑，共 60 个真实模型演示样本。Multi / Single task success 均为 24/30；工具调用 78 / 59，模型调用 115 / 76，平均实验延迟 6633.3 / 3937.1 ms。这支持当前 workload 下减少路由复杂度，不能证明 Single 普遍优于 Multi，也不代表生产 SLA。真实协作 workload 未覆盖。

[T11 Memory 验收](../evaluation/reports/t11_memory_acceptance.md)的 18/18 是模型、Redis、Chroma 和模拟商城的演示 HTTP 证据；[Single 回归](../evaluation/reports/support_production/regression.md)为另一组固定空 Memory 的十场景，task success 8/10。两者条件和指标不同，不能合并成生产成功率。

## 保留与未完成的部分

CartCare 仍沿用 FastAPI、Anthropic SDK、Redis、Chroma、Prometheus、skills、既有 BaseAgent 与部分 helper。`mcp/` 仍是自研本地工具层，并非标准 MCP 协议接入。`ECHOMIND_*`、Compose 服务名和容器名为兼容保留。

请求体 demo user_id 不等于认证主体；审批接口仍是演示身份模型。Action Store / Trace 随进程重启丢失，handoff 目前是摘要而非已创建工单。RAG 语义质量与阈值、长期数据物理清理、真实商城/支付集成和生产负载验证仍是后续工作。详见 [README](../README.md) 与 [hardening 入口](hardening/README.md)。

## 可独立复核的练习

在根目录执行 `git show 5d6c7e7:api/main.py`，找到 `/chat` 的 `recognize_intent`；再阅读当前 `api/main.py:chat` 和 `agents/support_agent.py:SupportRuntime.run`，解释 Intent 为何不再决定生产执行路径。运行 `uv run python -m pytest -q tests/test_support_production.py` 验证接线与安全边界。
