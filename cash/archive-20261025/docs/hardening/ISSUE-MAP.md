# 审查问题 → 既有 A 系列任务映射（不是新的状态系统）

> 事实来源：`docs/engineering/project-audit-20261011.md`；基准为**2026-10-11 当时的未提交工作区**。表中“已复现”指**审查的隔离观察**，不是修复测试。每轮先核对当前 HEAD。真正的实施状态**只记现有 Workbench**。

| 审查 ID | 审查认定 / 证据性质 | 对应执行段 | V3 决策 |
| --- | --- | --- | --- |
| N01 | P0，幂等异参/内部 key 越权复用，已观察 | `A04/N01` | **首先修** |
| N02 | P0，自报身份/审批/Trace/管理未认证，已观察 | `A03-lite/N02-auth`、`N02-ops` | **必须**；最小 AuthAdapter + 端点守卫 |
| N03 | P0，校验错误早于 ownership 并泄露字段，已观察 | `A03-lite/N03` | **必须** |
| N04 | P1，模拟退款动作与退款查询不一致，已观察 | `A04/N04` | 先红测再修 |
| N05 | P1，成功动作被后续 Memory 失败遮蔽，已观察 | `A04/N05` | **优先**，与请求前 Redis 失败区分 |
| N06 | P1，知识 upsert 未退役旧文档，已观察 | `A05/N06` | RAG 实验前修 |
| N07 | P1，Rerank 空数组仍标 usable，已观察 | `A05/N07` | RAG 实验前修 |
| N08 | P1，压缩快照竞态丢新消息，已观察 | `A06-lite/N08` | 条件修复；若延期标 known_open |
| N09 | P1，画像更新不绑定触发消息，已观察 | `A06-lite/N09` | 条件修复；RMW 另待专项验证 |
| N10 | P1，API Eval 与业务状态共享，已观察 | `A07/N10` | **优先**，后续评测前隔离 |
| N11 | P1，同步读 timeout 后 worker 继续，已观察 | `A01/N11` | 条件修复，不误称危险动作被重试 |
| N12 | P2，默认 Prometheus 指标/采样语义问题 | 运维 backlog | 默认延期 |
| N13 | P2，告警重复累积及统计覆盖不全 | 运维 backlog | 默认延期 |
| N14 | P1，liveness 与 readiness 混用，已观察 | `A07/N14` | 有余力补，公网前重新验收 |
| N15 | P2，nginx:alpine healthcheck 调 Python | 运维 backlog | 默认延期；历史停止容器证据 |
| C01 | 业务范围/行业能力声明不足 | `A02/C04` | 先定义可拒绝 vs 可升级范围 |
| C02 | 旧 Intent/entities helper 输入不连通，代码线索 | 特性 backlog | 无独立收益证据，不重引分类器 |
| C03 | 复合诉求未逐项完成、末轮 Action 单一回执，代码线索 | `A01/C03` | 定向测，有缺口最小改 |
| C04 | 文字关键词不代表 handoff，代码与历史指标 | `A02/C04` | **必须做结构化闭环** |
| C05 | 回复可能越出工具证据，历史 observations | `A04/N04`、`A02/C04`、A07 | 追加基于业务事实的回答约束测试 |
| C06 | Skill 旧角色/关键词匹配粗，未评测 | 特性 backlog | 默认不重写 |
| C07 | 请求总预算与超时体验不统一，代码线索 | `A01/N11` | 有证据/时间再实现总预算 |
| C08 | 内存 Action/Trace、Memory 过期与后台观察边界 | A04/A06，部署 backlog | 不默认重做持久化 |
| C09 | 复合、版本、否定、并发等评测覆盖不足 | A02/A05/A07 | 用冻结增量测试弥补 |

## 明确不在六周主线内，但不得宣传为已解决

- 真实支付 exactly-once、多进程 ActionStore、真实坐席承接和正式 OAuth/OIDC 认证；本地 adapter 不是公网安全方案。
- 独立只读工具并行与依赖调度：后端当前串行，不能归因于模型决定；不允许对危险工具统一并行。
- 旧 IntentRecognizer 或 Multi-Agent 回迁：T10 只证明**受控十类演示任务**中 Single 更省调用，未比较复杂跨行业协作。
- Memory 过期召回挤占 Top-K；知识/Skill prompt injection；知识政策与 PolicyEngine 发布一致性；API 上传预读/条数边界；CI 的 `uv`/JS 覆盖差异；资源关闭和日志脱敏；Eval 不同数据集 baseline 误对比。

**审查报告状态 `verify` ≠ A 系列任务 `fixed`**。若以后选择处理任一 backlog，仍通过**已有 Workbench**登记，不建立平行进度 JSON。
