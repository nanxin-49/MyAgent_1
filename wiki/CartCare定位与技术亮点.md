# CartCare 定位与技术亮点

CartCare 是 E-commerce Support Agent，面向 FAQ、政策、商品、订单、物流、库存和售后场景。生产 topology = **Single Support Agent**。当前外部业务使用明确标注的 JSON fixture / 内存演示后端，尚未接入真实商城或支付系统。

## 当前架构

```text
POST /chat
→ MemoryManager.get_context（原有 Redis / Chroma Memory）
→ SupportRuntime → SingleSupportAgent（BaseAgent，统一工具注册表）
    → RAG：静态 FAQ / 版本化政策
    → Providers：动态业务事实和 ownership
    → ActionService：Policy / PendingAction / HITL / idempotency
→ Memory 回写、异步 profile 更新
→ ChatResponse、Trace
```

Agent 负责理解、澄清、参数收集、选择工具和生成回复。生产请求不经过 Intent → specialist dispatch，也不调用 supporting Agent 或 Composer。IntentRecognizer 仅用于显式评测诊断，不决定 /chat 的执行 Agent。

## 工程边界

- 动态事实来自 Provider；RAG 不替代订单、物流、库存或退款状态查询。
- Tool Contract 保留严格 schema、read/write/dangerous 风险元数据、timeout、retry、typed errors 和 trace。危险动作不能由模型提供 approved 标志绕过控制。
- 退款和取消由确定性 PolicyEngine 决策；ActionService 管理 PendingAction、审批/拒绝/恢复、执行时二次校验与幂等。LLM 不直接执行业务写入。
- RAG 经外部 Chroma HTTP 存取；字符 n-gram embedding 是演示词面基线。usable 命中才有可用引用；来源、document_id、policy_version 与 chunk 信息保留。阈值仍为 0.35，fallback 不能作为可靠依据。
- Memory 架构未修改。Monitor 继续观测工具和 Agent 成功率/延迟；Single 不再计算或反馈路由惩罚。
- Trace 标记 topology=single、agent_type=support。模型调用统计覆盖 Support 与 RAG SDK 调用，不包含 Memory/profile 和 SDK 内部重试；不保存隐藏推理。

## 为什么简化

T10 已验收 done。[完整报告](../evaluation/reports/t10_topology_comparison.md)保留三轮各十场景的原始证据。

| 指标 | Multi（30） | Single（30） |
|---|---:|---:|
| task success | 24/30 | 24/30 |
| 不必要调用场景 | 10/30 | 5/30 |
| 平均延迟 ms | 6633.3 | 3937.1 |
| tool calls | 78 | 59 |
| model calls | 115 | 76 |

Multi 的最终样本未使用 supporting Agent 或 Composer；当前电商 workload 没有验证协作收益。相同任务成功率、较少工具/模型调用及较少 routing 层支持迁移到 Single。旧 Multi 类保留供 evaluation/run_topology_comparison.py 回归，不再描述为生产架构。

## 生产迁移验证与限制

[真实生产入口回归](../evaluation/reports/support_production/regression.md)为一轮实际 HTTP /chat、真实模型和 Chroma HTTP、演示业务后端、固定空 Memory adapter：task success 8/10、工具选择 9/10、参数 6/6 observable、引用 1/1、危险动作正确性 4/5、安全违规 0；不必要调用 3/10、工具调用 21、模型调用 25、平均 HTTP 延迟 3686.0 ms。

结果支持实验 Single 与生产入口的主要行为一致。不必要调用比例较历史 Single 高，单轮不能判定稳定变化；未验证 Redis/长期 Memory，也不能用这些演示样本宣称真实生产效果。unsupported escalation（0/1）、ownership 严格任务证据缺口、technical/真实协作 workload 未覆盖均保留为 follow-up，没有同时修改 prompt 或业务规则。生产迁移状态为 verify，等待用户验收。

历史 T09 10 场景基线保持原样（intent 7/10、tool selection 7/10、arguments 6/6、unnecessary cases 5/10、strict E2E 6/10），不能与新 citation contract 直接混算。其他 Wiki 中的 Multi 描述属于历史材料，本文件与重点代码是当前权威说明。

后续 [真实 Memory 验收](../evaluation/reports/support_production/memory_acceptance.md)已补齐短期集成证据：真实 Redis/Chroma、原有 MemoryManager、真实模型与 HTTP `/chat` 的跨轮订单号沿用、用户/会话隔离和服务故障路径均通过。之前的十场景回归仍为固定空 Memory 条件，不混作 Memory 验收。压缩、长期情景检索与画像质量未在本轮验证；迁移现可建议 done，Workbench 保持 verify 待用户确认。
