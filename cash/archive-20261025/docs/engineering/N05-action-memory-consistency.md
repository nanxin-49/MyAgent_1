# N05 — Action 与 Memory 写入结果一致性

2026-10-12；A04/N05，outcome=`fixed`，status=`verify`，待用户验收。
起始 HEAD：`001919c15a34923c239db52ab25b6ca1aaba9523`；工作区干净，N01/N02/N03 已在 HEAD。未提交、推送或执行其他 N 项。

## 根因与复现

原 `/chat` 顺序：Principal/owner 校验 → Memory.get_context → SupportRuntime/SingleSupportAgent → guarded ActionService → Memory.add_message(USER) → Memory.add_message(ASSISTANT) → response。Action 在 Memory 写入之前已执行并存为 completed，但任一写入异常被重新抛出，HTTP 变为 500。用户可能据此重试危险业务动作；现有 N01 同参数复用可阻止本进程内重复执行，但 HTTP 与已完成业务结果仍不一致。

原审查 `audit_20261011_probe.py:http_probes` 和 `audit-20261011-observations.json:ACTION_SUCCESS_MEMORY_FAILURE` 为只读证据，观察到 HTTP 500、completed、backend_executions=1。原脚本混合 N02 旧身份和其他缺陷断言、主入口覆盖旧 JSON，因此本轮复用其 N05 逻辑，补上当前服务端认证，在正式测试中独立复现。

`tests/test_action_memory_consistency.py` 使用 Fake SDK、模拟 Action backend、FaultMemory、真实 HTTP `/chat` 和当前 Principal gate。修复前 17 项中 **7 failed / 10 passed**：4 个用户/助手写入及 RuntimeError/RedisError 用例、2 个重复提交用例均因预期 200 而实际 500 失败；另 1 项因新 action_results 尚不存在失败。动作均仍 completed、仅执行一次。这是安全行为红测，而非审查的“缺陷成立即通过”断言。

## 最小边界与响应

`api/main.py:_observed_action_results` 只接受本请求危险工具的动作编号；completed 候选必须有工具执行成功和业务结果成功标记。通过 `ActionService.get(action_id, user_id, principal)` 重新确认归属和状态，状态须与 Trace 一致，深复制回执，不从模型文字、历史会话或任意 Store 全表搜索推断成功。沿用既有 ActionResult，Trace 的 reused 标记保留 N01 复用事实。至少一个回执 success=true、status=completed、execution_result 非空才允许后续 Memory 写入故障降级。

`/chat` 新增字段：

| 字段 | 意义 |
| --- | --- |
| action_results | 本次工具调用经 ActionService 确认的回执列表；空列表不证明执行成功。每项保留真实状态、action_id、execution_result、reused |
| memory_write_status | completed 或 failed，仅指本次 Memory 写入 |
| warning_codes | 正常为空；满足已完成动作条件的 Memory 故障为 `["memory_write_failed"]` |

正常模型文本保持原样；业务状态以结构化回执为准。HTTP 200 表示交付了可判断的结果，不代表所有业务动作成功。复合请求可以同时包含 completed 和 awaiting_approval/failed，不能合并成整体成功；后者从未因此重新执行。模拟 completed 不代表退款资金到账。回执可通过原有受保护的 `GET /actions/{action_id}` 查询。

| 场景 | 处理 |
| --- | --- |
| Action 完成，Memory 正常 | 原正常文本/HTTP 200；返回动作回执，写入 completed |
| Action 完成，用户或助手消息写入异常 | HTTP 200，动作仍 completed，Memory failed 和固定 warning；跳过画像调度 |
| Action 失败，Memory 正常 | 原 HTTP 200 聊天响应，结构化 ActionResult success=false/status=failed；不能据 HTTP 或模型文字认定业务成功 |
| Action 失败/待审批/未确认完成，Memory 写入异常 | 保留原 HTTP 500，不伪造业务成功，不自动执行或恢复动作 |
| 必要 Redis 上下文读取失败 | 原 503/memory_unavailable；模型与危险动作不执行 |
| 只读请求，Memory 写入异常 | 保留原 HTTP 500，Trace 明确 failed |
| 同身份同参数重复提交 | 原 N01 显式/自动 key 复用原 action_id、reused=true，本进程内副作用仅一次 |

不能把所有异常转成成功：模型失败、业务失败、未知执行状态、缺回执和读取故障各自保留现有边界。后续模型异常由已有 BaseAgent 的观察回执恢复路径处理，本轮不重写它。ActionStore 缺失、状态不一致或无 execution_result 都不能触发本次降级。

Trace 保留原 action_result，追加 memory.write_failed_role、messages_written、error_code=memory_write_failed 及耗时；messages_written 计数的是 add_message **成功返回**次数，不保证异常调用没有部分 Redis 写入（例如 LPUSH 完成后 EXPIRE/压缩失败）。日志只包含固定错误码、request_id、写入角色及是否确认完成，未记录 Memory 异常原文、用户消息、凭据或隐藏推理。不保证故障后会话完整，也不自动补写。

## 验证证据

环境：Windows、Python 3.12.3、uv 0.12.19。数据：prepare(NOW=2026-10-02) 生成的隔离演示 fixture；无收费模型、真实支付、部署或 live Redis/Chroma 验收。
原始本轮响应、Trace、Store 状态和后端计数见 [N05 observations](N05-action-memory-observations.json)，8 组观察，与历史报告分开保存。

按要求顺序执行：

| 命令 | 结果 |
| --- | --- |
| `uv run python -m pytest -q tests/test_action_memory_consistency.py` | 22 passed，覆盖七类要求，以及模型前/后故障、缺失/不一致回执、复合动作、跨客户拒绝 |
| `uv run python -m pytest -q tests/test_action_service.py` | 31 passed |
| `uv run python -m pytest -q tests/test_memory_boundary.py tests/test_memory_live_services.py` | 7 passed、1 skipped |
| `uv run python -m pytest -q tests/test_action_service.py tests/test_auth_boundary.py tests/test_provider_safety.py` | 80 passed（N01 31、N02 37、N03 12） |
| `uv run python -m pytest -q` | 235 passed、2 skipped |
| `uv lock --check` | 通过，53 packages |
| `git diff --check` | 通过 |

跳过项为 opt-in live Redis/Chroma Memory 与真实 Chroma RAG HTTP 测试，未开启相应环境变量。保留既有 AnyIO DeprecationWarning；最终深复制回执和文档同步后完整复跑仍 235 passed/2 skipped，另出现 pytest stepwise 缓存写入 Permission denied 的沙箱警告，不影响测试断言。修改前相关既有测试基线 100 passed。N01 绑定、N02 认证/独立审核与 Trace/admin gate、N03 Provider 脱敏全部保持；未改 ActionService/Store、Policy/HITL、MemoryManager、依赖及 T01–T12 历史报告。

## 取舍、限制与独立练习

本缺陷位于已知完成动作之后的辅助写入边界，现有回执和受保护查询足以作局部修复；Outbox、队列、分布式事务会引入超出本轮范围的存储和恢复机制。当前 ActionStore、模拟业务状态及有界 Trace 都在进程内，重启、多个 worker 和外部业务已执行但本地未记 completed 的窗口仍无恢复保证。该情况不得凭空认定成功，也不能自动重新执行；今后需独立设计持久化/外部对账。网络断开、响应序列化失败和客户端改变幂等键不在本次保障范围。N04/N06/N10 未执行。

独立练习：不依赖 Codex，在本地新增 FaultMemory：先执行真实测试替身的 add_message，再抛出合成 RedisError，分别注入 USER 与 ASSISTANT 阶段。运行 Fake SDK `/chat`，检查 action_id/completed、backend_executions=1、memory.failed、固定警告及 Trace；同参数再提交，断言同 action_id 且无第二次执行。解释为什么 messages_written 可能小于实际已写入条数、为什么不能仅凭 HTTP 200 判断全部业务成功；不要停止共享 Redis 或调用真实模型。

建议提交：`fix: preserve completed action receipts on memory write failure`。
