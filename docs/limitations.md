# 已知限制

CartCare 是 Agent Harness 与演示用客服 Agent，不是生产客服系统。以下限制影响如何解读演示和评测数字。

## 身份与业务后端

- Demo `user_id` 不是正式认证；审批 API 沿用演示身份模型。生产环境需要替换 AuthAdapter、凭据生命周期和部署安全审查。
- 商城、支付、退款执行和人工交接都是明确标注的模拟后端；没有接入真实商城、支付网关、工单或坐席系统。
- 模拟业务表是进程内 fixture；PendingAction/检查点持久化在 Redis，不等于业务数据持久化。重启后业务状态从 fixture 重建。

## 单实例与并发

- Redis ActionStore/CheckpointStore 的锁是进程内 `RLock`，不是分布式锁；多 worker 并发不在承诺内。
- Memory 压缩和画像更新使用进程内 `asyncio.Lock`；单实例下避免压缩丢消息和画像 RMW 覆盖，多 worker 不承诺。
- `/ready` 检查 Redis/Chroma 服务可用，不检查知识库集合/文档完整性，也不检查业务表恢复情况。

## 状态变更与恢复

- 审批、执行和恢复是单实例可靠；执行已派发但没有回执时按 `execution_unknown` 失败，不自动重放。
- `execution_unknown` 使用原 idempotency key，同一请求重试会复用 failed 结果；需要人工核对或新请求。
- 退款 `completed` 只表示模拟命令完成；订单 `refund_pending`、退款 `pending` 都不代表资金到账。
- 没有 TTL 清理任务；动作/检查点不会自动过期。长期过期 Chroma 记录读取时过滤，物理清理未自动调度。

## RAG 与检索

- 生产默认仍是字符 n-gram 词法基线，阈值 0.35；不是神经语义检索。
- H2-5 的 bge-small 语义/hybrid 实验没有在 Recall@5 上赢 B0-calibrated，生产未切换；真实 embedding 后端、collection 重建和 `/chat` 复验未做。
- dev 只有 8 个负例，B0-calibrated 在 test 上 FPR 8/9，说明阈值泛化不足；不能把小样本校准当成统计保证。
- `usable` 只表示检索片段通过来源、版本和评分校验；引用不等于逐句事实核验。
- 外部 Chroma Server 是唯一存储路径，连接失败明确失败，不切换嵌入式数据库。

## 可观测与 Memory

- Trace 是进程内有界队列，重启丢失；工具结果是摘要和确定性 helper 白名单输出，不是完整原始输出。
- 不保存隐藏推理、prompt 或原始 Memory 内容；早期 Memory 读失败不生成 Agent Trace。
- 后台画像状态只标记 `scheduled_unobserved`，不把调度成功视为落库成功。
- 读工具超时后不自动重试，避免后台 worker 重叠；模型需要显式再发起。

## 评测口径

- 所有真实模型结果来自 `deepseek-flash`、演示业务后端和指定样本；不是生产 SLA、长期稳定性或大规模负载证据。
- H2-3 全量 180 的逐 check 安全/工具指标因中断不可恢复；H2-4/H3-6 的样本量较小，1–3 条差异可能只是噪声。
- H3-6 真实模型整体成功率有限；主要失败是反问确认、越权订单不调用 action、FAQ low_confidence/no_answer，不是 harness 执行错误。
- 没有真实支付成功率、完整客服交接集成或生产规模负载证据。

## 部署

- Docker `/ready` healthcheck 已写入配置，但 H5-2 未重建应用镜像；干净环境验证见后续任务。
- 旧 `ECHOMIND_*` 环境变量仍作为回退；历史 hardening 脚本仍引用旧容器名，属于历史证据，不是当前运行路径。
- 演示执行会改变当前进程内业务状态；新建会话不重置业务后端，重复退款/取消未必得到首次结果。

## 相关文档

- [架构与边界](architecture.md)
- [评测结果](evaluation.md)
- [运行与部署](operations.md)
- [命名迁移](naming.md)
