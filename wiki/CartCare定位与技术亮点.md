# CartCare 定位与技术亮点

CartCare 是 E-commerce Support Agent，面向 FAQ、政策、商品、订单、物流、库存和售后场景。生产 topology = **Single Support Agent + 工具**。外部业务使用明确标注的 JSON fixture / 内存演示后端，尚未接入真实商城或支付系统。

## 当前架构

```text
POST /chat
→ AuthAdapter → Verified Principal
→ MemoryManager.get_context（Redis 工作记忆 / Chroma 筛选的长期记录）
→ SupportRuntime → SingleSupportAgent（BaseAgent，统一工具注册表）
    → RAG：静态 FAQ / 版本化政策
    → Providers：动态业务事实和 ownership
    → ActionService：Principal gate / Policy / PendingAction / HITL / idempotency
    → HandoffService：策略 / Principal / 幂等 / 模拟交接记录
→ Memory 回写、异步 profile 更新
→ ChatResponse、Trace
```

Agent 负责理解、澄清、参数收集、选择工具和生成回复。生产请求不经过 Intent → specialist dispatch，也不调用 supporting Agent 或 Composer。IntentRecognizer 仅用于显式评测诊断，不决定 `/chat` 的执行 Agent。详细调用路径和 Harness 七层见 [架构与边界](../docs/architecture.md) 与 [重点代码](重点代码.md)。

## 工程边界

- 动态事实来自 Provider；RAG 不替代订单、物流、库存或退款状态查询。
- Tool Contract 保留严格 schema、read/write/dangerous 风险元数据、timeout、retry、typed errors 和 trace。危险动作不能由模型提供 approved 标志绕过控制。
- 退款和取消由确定性 PolicyEngine 决策；ActionService 管理 PendingAction、审批/拒绝/恢复、执行时二次校验与幂等。LLM 不直接执行业务写入。
- 需要人工审核的动作由范围内独立 reviewer 批准；动作 owner 与审核主体分开记录。Trace 和管理接口要求 admin。受控回环 Demo Auth 仅用于本地演示，不等于生产认证。
- RAG 经外部 Chroma HTTP 存取；生产默认字符 n-gram embedding 是词面基线。`usable` 命中才有可用引用；来源、document_id、policy_version 与 chunk 信息保留。语义检索实验（H2-5）未在 Recall 上赢 B0，生产未切换。
- Memory 工作层按用户/会话隔离并设置 24 小时 TTL；15 条触发确定性压缩，保留最近 5 条、订单号引用及待澄清字段。Chroma 只接收有来源和有效期的咨询主题与明确回复偏好，不保存动态业务状态。
- Trace 标记 topology=single、agent_type=support；记录工具、参数、结果摘要、Policy/审批、每步 token/延迟和停止原因，不保存隐藏推理。
- 交接以 required/requested/created/failed 和可查询模拟记录为证据；摘要不建单，越界合理拒绝不自动升级，created 不代表真人接单。

## 为什么简化

T10 是 controlled demo workload，3 × 10 cases / topology，not production benchmark；Multi/Single 均 24/30，Single 延迟和工具/模型调用更少。该结果支持当前 workload 的简化选择，不代表真实协作任务收益或生产 SLA。完整表和限制见 [评测结果](../docs/evaluation.md)。

## 生产迁移验证与限制

真实生产入口回归（H1-1）使用实际 HTTP `/chat`、真实模型和 Chroma HTTP、演示业务后端、固定空 Memory adapter：task success 8/10、工具选择 9/10、参数 6/6、危险动作正确性 4/5、安全违规 0。该十场景回归未验证 Redis/长期 Memory，也不能用演示样本宣称真实生产效果。

真实 Memory 验收 T11 为 18/18，覆盖跨轮订单号、动态 Provider 状态刷新、异步偏好落库、隔离和 Redis 故障关闭；它仍是演示环境验收，不是生产规模稳定性。详细报告和证据层级见 [评测结果](../docs/evaluation.md) 与 `docs/reports/`。

## 演示与可观测性（T12）

同源 `/demo` 是轻量静态展示层，十场景按钮仅填入用户消息；真实输出来自 `/chat`、`/trace/tool/{request_id}` 与既有 ActionService API。LLM 选择工具，Provider 提供事实，确定性 Policy 控制允许/拒绝/审批；UI 不补造工具结果或审批逻辑。

引用卡片关联 Trace 的文档标题、source、reference 与 policy_version；非 `usable` 状态不显示为可靠 citation。动作卡片区分原始请求快照与最新 ActionResult。Memory 只展示计数、摘要存在标志、读写状态和阶段耗时，不展示原始记忆或隐藏推理。

完整限制见 [已知限制](../docs/limitations.md)。
