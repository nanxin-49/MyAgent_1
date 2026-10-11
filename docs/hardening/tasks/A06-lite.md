# A06-lite｜Memory 竞态：审查已经复现，非“纯假设”

> 审查 N08/N09 均有明确隔离复现观察，**但六周资源有限，可以延后**。若延后，必须在已知风险中保留 `known_open`，不能用 T11 的 18/18 代替并发稳定性证明。不要重做 Redis TTL、用户隔离、动态业务事实重新查询等已完成的 T11 能力。

## A06-lite/N08（P1，建议优先于 N09）——压缩快照并发丢失

**依据**：`MEMORY_COMPRESSION_RACE`，`memory/conversation_memory.py:212`。快照读到 15 条后，又插入 6 条，`ltrim` 只保留最新 5 条，第一条新增引用既不在摘要，也不在工作记忆。

**红测**：以受控 interleaving 模拟快照 → 新消息入 Redis → 压缩提交；断言所有新消息至少存在于摘要或工作记忆，不能丢失。事务写入原子性不代表快照与提交一致。

**修复原则**：最小的乐观版本校验 / per-session 协调 / 原子脚本，按当前 Redis 结构选择一种；不要重写整套 Memory 组件。保留原有 fail-closed 语义。

## A06-lite/N09（P1）——后台画像更新读取错触发消息

**依据**：`PROFILE_UPDATE_RACE`，`memory/conversation_memory.py:150`、`api/main.py:412`。用户显式要求用英文回复后，异步任务执行前有下一条查询，后台却读取了新消息，丢失原偏好。并发 profile read-modify-write 覆盖风险目前只有代码线索，未独立测。

**红测**：创建画像更新任务但延迟调度，紧接另一个请求；画像更新必须绑定**触发请求的用户内容/安全提取结果**，而不是无关联的 latest message；另补 `scheduled/completed/failed` 结果观察，日志不保存原始个人信息。

**修复原则**：传递不可变触发上下文或安全提取的偏好事件；必要时控制 per-user 更新时序。正确跟踪后台任务完成和失败，不声称 `create_task` 等于落盘成功。

**DoD**：每轮选 N08 或 N09，各自具备受控竞态前失败和修复后通过的专项测试；相关 T11 Memory 契约不回退。时间不足两项均可 `deferred/known_open`，但文档必须诚实披露。
