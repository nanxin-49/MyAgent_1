# N04 — 退款执行与查询一致性

2026-10-12；A04/N04，outcome=`fixed`，status=`verify`，等待用户验收。
起始 HEAD `d02427a7bde8cac12353745c7480978ce855647b`，工作区干净；N01/N02/N03/N05 已在 HEAD。只处理 N04，未提交、推送或启动 N06/N07/N10。

## 根因与原始证据

审查 `audit_20261011_probe.py:action_probes` / `audit-20261011-observations.json:REFUND_READ_WRITE` 观察到 Action completed、execution_result completed、订单 refund_pending、refund_record=null。这些历史文件本轮只读，不运行会覆盖旧 JSON 且含旧身份假设的完整审查脚本。

`InMemoryBusinessActionBackend.execute_refund` 原来只修改订单、返回 completed，没有创建 RefundRecord。startup 向读写 Backend 传同一 business_data，但它们各自复制表字典：原订单对象可通过浅拷贝共享，新增 refund 字典键不会自然进入查询表。因此单纯在写 Backend 增加一条记录仍不足以修复真实运行路径。

## 状态与调用顺序

| 状态 | 本轮意义 |
| --- | --- |
| Action completed / execution_result completed | 模拟业务命令已完成，并已有退款申请回执 |
| Order refund_pending / Refund pending | 申请已创建，等待后续处理 |
| Refund settled | 本轮不生成此状态；无真实支付完成依据，不声称资金到账 |

已有 RefundStatus 的 requested/approved/processing/completed 等值保留；增加 pending，不将它别名为 completed。未来若提供 settled/资金完成语义，必须有独立可信证据和状态转换规则。

新路径：Principal/ownership → 原 ActionService 与 Policy/HITL → Executor → 模拟 Backend 在共享锁内预校验 RefundRecord → 创建 pending 记录 + 订单 refund_pending → 返回带 refund_id/refund_status 的模拟命令回执 → ActionService 标 completed。后续 `/chat` 由 Fake SDK 选择 get_refund_status → 原 RefundProvider → 同一业务 state → 返回正确订单、owner、金额、pending。

待审批、客户拒绝、依赖失败和提交回滚均不创建新申请。N01 同 key 同参数复用同 Action、单次副作用；异参保持 idempotency_conflict。同 action_id 的直接模拟命令重放也只能复用其同订单/owner/有效金额记录，不重复新增记录；订单已 refund_pending/refunded 时新命令被拒绝。未添加自动执行重试。

允许对已有 failed/rejected 申请重新发起合法请求时，历史记录不会被删除。按订单查询改为选择最新 updated_at（UTC 比较，时间相同取后插入记录），避免第一条旧失败记录遮蔽新 pending 申请；按 refund_id 查询保留历史。无法解析更新时间的记录仍交给 Provider 校验，不用过滤悄然隐藏异常。

## 最小实现与部分更新窗口

- `providers/mock_backend.py:InMemoryBusinessState`：现有表字典加一个 RLock；读 Backend 的单次读取和按订单退款选择在锁内取得快照，更新了“未接 API”的过时模块说明。
- `actions/backend.py:execute_refund`：复用 RefundRecord 校验，生成 `REF-{action_id}`，填订单/owner/金额/币种、UTC 时间和明确模拟原因。先生成并校验记录和回执，再提交记录、订单状态和成功调用计数。异常时撤销新记录、恢复订单状态及调用计数，返回固定模拟提交错误；execute_cancel 也遵守共享状态锁。
- `api/main.py:lifespan`：显式传 business_backend.state，消除读写新增记录的隔离。未修改 N05 的错误处理或 API 认证。
- `providers/models.py` / `policies/engine.py`：增加 pending 并纳入既有活跃退款集合；阈值、资格窗口、审批及身份规则不变。
- `tests/test_action_service.py:make_service`：测试组合根使用与 startup 相同的显式 state；原断言不放宽。历史实验 `isolated_business` 的各自 deepcopy 不改，其结果不能证明生产写后读。

锁只保证遵守同一 state.lock 的本进程读写方法不观察到“新退款记录、旧订单状态”的提交中间窗口；两次独立查询不构成全局事务。先校验后提交、异常回滚针对默认普通字典和可恢复异常：测试注入“退款插入后抛异常”与“订单更新后抛异常”，验证动作 failed、无新退款、订单恢复、零成功执行计数。不可恢复内存错误、进程崩溃、绕过锁直接访问内部表或回滚自身失败不在保证范围。

Backend 更新与 ActionStore 标 completed 仍有独立窗口：业务表已更新，但进程退出/Store 写入失败时，本轮不保证 Action、退款和订单的持久化原子性，不自动再执行。当前接口和模拟状态均进程内，不引入分布式事务、数据库或支付系统来扩大本任务。

## 红绿证据与验收

Windows、Python 3.12.3、uv 0.12.19。隔离数据来源为 `tests/fixtures/business_provider_data.json`，Policy clock 固定 2026-09-25；新增记录时间为执行时 UTC。Fake SDK / Memory / RAG / Monitor / Eval 替身，不调用外部服务或真实支付。

初始专项 **9 failed / 3 passed**：自动执行、审批后执行、同 key 重试、8 线程复用、跨用户生成记录查询、两处提交故障、pending 规则、实际 lifespan HTTP 写后读为红；待审批/拒绝/预置 backend failure 为绿。原缺陷仍是 completed + 单次执行 + 查不到退款。

首次最小修复后 12 passed；补命令重放/新 key/无效金额/提交中读取测试后 16 passed。随后补已有 failed/rejected 记录的重新申请红测 **2 failed / 16 deselected**，证明查询返回旧金额和旧状态；调整最新记录选择后最终专项 **18 passed**。

| 执行顺序 / 命令 | 最终结果 |
| --- | --- |
| `uv run python -m pytest -q tests/test_refund_read_write_consistency.py` | 18 passed |
| `uv run python -m pytest -q tests/test_action_service.py tests/test_business_providers.py tests/test_business_tools.py tests/test_policy_engine.py` | 60 passed |
| `uv run python -m pytest -q tests/test_action_service.py tests/test_auth_boundary.py tests/test_provider_safety.py tests/test_action_memory_consistency.py` | 102 passed（N01 31、N02 37、N03 12、N05 22） |
| `uv run python -m pytest -q` | 253 passed、2 skipped；既有 AnyIO 弃用警告 |
| `uv lock --check` | 通过，53 packages |
| `git diff --check` | 通过 |

API/退款状态契约核查后额外运行 `node --test tests/demo_ui.test.cjs`：12 passed。

两个跳过项为 opt-in live Redis/Chroma Memory 与 Chroma HTTP RAG 测试，未启用对应环境变量。修改前相关基线 117 passed。没有真实模型、真实支付、部署或跨进程/重启验收。七组新原始 Action/退款 Tool/跨用户错误/后端计数观察保存于 [N04 observations](N04-refund-read-write-observations.json)，不覆盖历史报告。

`test_real_lifespan_refund_approval_and_http_query` 实际执行 production lifespan，保持真实读写 Backend、ActionService、Policy、Tool 和 API；只替换外部依赖和 clock。HTTP `/chat` 先创建待审批动作，独立 reviewer `/approve` 返回 completed，再以 `/chat` 选择退款查询，在 Trace 观察 result_success=true/status=pending，执行一次。不是手工复制 startup 或仅调用独立 deepcopy fixture。

## 文档、限制与独立练习

README 与核心《重点代码》同步新增 pending、回执字段、最新记录选择和共享状态。Demo 已核查：业务状态直接展示既有结果，执行回执新增字段兼容原结构，无需改 UI；核心定位和历史 T01–T12 无需重写。

重启后 fixture 重新加载，ActionStore/业务状态/Trace 不持久；多个 worker 各自维护状态和锁，无跨进程承诺。真实支付、到账、退款结算状态及外部对账均未接入。N10 评测共享运行时风险仍存在，本轮不修。新增 pending 在旧客户端应作为待处理状态消费，不能解释为到账。

独立练习：不依赖 Codex，复制专项测试的共享 state 组合，创建一笔 600 元申请，验证审批前无新 RefundRecord；由独立 reviewer 批准后查询 owner/amount/pending。将退款表替换为“插入后抛异常”的测试字典，对另一笔独立订单验证 failed、订单回滚、没有新记录；然后测试同 key/600.00 复用和同 key/599 冲突，解释 Action completed 与资金到账的区别。只用模拟 backend，不操作共享 Redis 或支付服务。

建议提交：`fix: make simulated refund execution queryable and consistent`。
