# CartCare 定位与技术亮点

CartCare 是 E-commerce Support Agent，面向 FAQ、政策、商品、订单、物流、库存和售后场景。生产 topology = **Single Support Agent**。当前外部业务使用明确标注的 JSON fixture / 内存演示后端，尚未接入真实商城或支付系统。

## 当前架构

```text
POST /chat
→ MemoryManager.get_context（Redis 工作记忆 / Chroma 筛选的长期记录）
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
- Memory 的工作层按用户/会话隔离并设置 24 小时 TTL；15 条触发确定性压缩，保留最近 5 条、订单号引用及待澄清字段。Chroma 只接收有来源和有效期的咨询主题与明确回复偏好，分别保留 30/180 天；订单、物流、库存和退款状态不进入长期事实。Monitor 继续观测工具和 Agent 成功率/延迟；Single 不再计算或反馈路由惩罚。
- Trace 标记 topology=single、agent_type=support。模型调用统计覆盖 Support 与 RAG SDK 调用，不包含 Memory/profile 和 SDK 内部重试；不保存隐藏推理。

## 为什么简化

T10 是 controlled demo workload，3 × 10 cases / topology，not production benchmark；表中延迟不是生产 SLA。

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

结果支持实验 Single 与生产入口的主要行为一致。不必要调用比例较历史 Single 高，单轮不能判定稳定变化；该十场景回归未验证 Redis/长期 Memory，也不能用这些演示样本宣称真实生产效果。unsupported escalation（0/1）、ownership 严格任务证据缺口、technical/真实协作 workload 未覆盖均保留为 follow-up，没有同时修改 prompt 或业务规则。生产迁移已验收 done。

历史 T09 10 场景基线保持原样（intent 7/10、tool selection 7/10、arguments 6/6、unnecessary cases 5/10、strict E2E 6/10），不能与新 citation contract 直接混算。其他 Wiki 中的 Multi 描述属于历史材料，本文件与重点代码是当前权威说明。

历史 [真实 Memory 验收](../evaluation/reports/support_production/memory_acceptance.md)记录旧实现的短期集成结果。T11 [新验收](../evaluation/reports/t11_memory_acceptance.md)保留原 16 项检查，新增演示订单状态变化后再次调用 Provider、异步偏好写入真实 Chroma，共 18/18；真实 Redis/Chroma 可选集成测试覆盖压缩、长期记录隔离与删除。Redis 读取故障返回 503 且 Agent 不执行。演示 user_id 仍非正式身份认证；长期记录按有效期读取，但物理过期清理尚未自动调度。

## 演示与可观察性（T12）

同源 `/demo` 是轻量静态展示层，十场景按钮仅填入用户消息；真实输出来自 `/chat`、`/trace/tool/{request_id}` 与既有 ActionService API。LLM 选择工具，Provider 提供事实，确定性 Policy 控制允许/拒绝/审批；UI 不补造工具结果或审批逻辑。

引用卡片关联 Trace 的文档标题、source、reference 与 policy_version；非 usable 状态不显示为可靠 citation。动作卡片区分原始请求快照与最新 ActionResult，Approve 可能直接完成执行。Memory 只展示计数、摘要存在标志、读写状态和阶段耗时，后台画像标为 scheduled_unobserved；不展示原始记忆或隐藏推理。

Trace 为进程内有界记录，早期 Memory 读失败无 Agent Trace；演示身份、内存 PendingAction、字符 n-gram 词面基线、unsupported 升级、外部商城/支付未接入和长期过期记录无后台物理清理等限制见当前 README。T11 18/18 是演示环境验收，不能代表生产规模稳定性。T12 等待用户验收。
