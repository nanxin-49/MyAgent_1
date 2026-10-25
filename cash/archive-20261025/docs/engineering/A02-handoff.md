# A02 / C04 — Structured Handoff

2026-10-12；起始 HEAD `c47eb8671898f336efc72ff79c25fd62d70cf499`，起始工作区干净。结果：`fixed`，状态：`verify`，待用户验收。本轮仅 A02；未提交、推送、部署或运行收费模型。

## 原问题与红测

生产路径为 `/chat → Memory → SupportRuntime → SingleSupportAgent → BaseAgent / execute_tool`。原 BaseAgent 根据**回复**中的“转人工 / 人工客服 / 无法处理”等词设置 escalated：否定句“您不需要人工客服”及合理订票拒绝可误报；明确人工请求得到普通回复可漏报。即使 escalated=true，也没有创建逻辑或可查询 handoff_id。`create_handoff_summary` 仅生成摘要。

新增预期安全行为的 HTTP 回归首跑 `6 failed`：人工请求缺少 handoff 回执；否定和越界拒绝误标 escalated；正常请求缺状态契约。进一步故障回归 `4 failed / 17 passed`：工具被拒绝但模型仍声称已成功转接。修复后均通过。生产 Single 覆盖旧关键词标记；旧 BaseAgent 行为保留给冻结的历史实验，未重写 T10 `0/3` 报告。

## 设计选择与状态

| 字段 | 定义 |
|---|---|
| handoff_required | 当前确定性策略认可需要人工协助 |
| handoff_requested | 已实际调用模拟交接创建逻辑；模型提议或策略拒绝不算 |
| handoff_created | 记录已存入本进程 Service；存在 handoff_id |
| handoff_failed | 创建失败或请求作用域冲突；不能据此声称已转接 |
| status | not_required / required / requested / created / failed；当前同步接口返回终态 |

状态过程为 required → requested → created 或 failed。同步实现不对外开放中间态查询；终态布尔字段保留是否实际发起创建。身份失败先拒绝，不建记录；策略拒绝为 not_required + handoff_policy_rejected。异参冲突为 failed + handoff_idempotency_conflict，handoff_requested=false（本次未再次调用创建逻辑）。API 的 handoff 是 HandoffResult，Trace 根节点同形；工具调用各自保留 handoff_result 和错误码。

**确定性兜底**：当前用户消息明确请求转/找/联系人工（包含“我想转人工客服”）时，SingleSupportAgent 通过同一 request_handoff Tool Contract 直接申请，不依赖模型是否调用工具，也无需模型事后生成回执。按句读取，带不需要/不要/不想/不用等否定的子句不触发；不使用模型输出或历史消息判断请求。此语法规则是保守演示范围，未声称覆盖所有自然语言、双重否定或间接引语。

**Agent 判断**：复杂电商投诉用 complex_complaint；服务再次核对当前消息含订单/退款/售后/商品/物流和投诉/争议/未解决表达。business_dependency_failure 仅接受当前请求此前实际 get_order/get_shipment/get_refund_status 的 dependency_failure/service_unavailable/timeout Trace，不接受模型自报依赖故障。否定人工拒绝可选升级。其他理由码拒绝；普通退款咨询、缺订单号、FAQ、RAG 无答案和一次普通业务规则拒绝不自动升级。

**合理拒绝**：CartCare 已声明商品、订单、物流、库存和售后范围；订票不属于支持能力，允许直接解释范围并拒绝，unsupported 不能成为建单理由。越界请求同时明确要求人工时，尊重明确人工请求，但模拟记录不保证有人能办理越界业务。没有新增通用意图分类器、行业能力平台或 Multi-Agent。

## 可执行路径与记录

```text
AuthAdapter → Principal → /chat 身份校验 → Memory 读取
→ SupportRuntime（共享本 Runtime 的 HandoffService，每请求独立 SingleSupportAgent）
→ 明确请求门控 或 Agent tool_use
→ execute_tool(request_handoff, risk=write, 自动重试=无)
→ build_handoff_tools.handler → HandoffService.request
→ 再次 Principal 校验 → 策略 → 作用域/指纹 → 模拟创建/存储
→ 工具 handoff_result / 根 Trace handoff / API handoff
→ 后端渲染交接回执 → Memory 写回
```

Service 的身份来自已验证 Principal，Request.user_id 必须一致。模型只可提交 reason_code，不能传 owner、handoff_id、status、凭据或整段摘要。记录仅含 owner、requested_by、UUID handoff_id、created、受限 reason_code、simulated 和固定安全摘要；不存原始消息、会话全文或凭据。UUID 在创建记录时生成；失败回执没有 ID。`GET /handoffs/{handoff_id}` 要求 customer Principal，仅 owner 可查；跨 owner/不存在均404，无认证401，reviewer/admin不会自动获得客户访问权限。

摘要 helper 保留；它不调用 HandoffService、也不使任何创建字段为真。生产使用 request_handoff 才能创建。通用升级关键词不再设置生产 escalated，兼容定义为 `handoff_created`；failed 时 escalated=false，因此新消费者应读取完整 handoff 状态。

## 重复、故障与可信回执

幂等作用域是 `(Principal.subject_id, customer_id, conv_id, handoff_key 或服务端 request_id)`，绑定当前消息 SHA256。没有客户端 key 时，仅同一服务端请求中的模型/工具重试去重；不同 HTTP 请求相同文本不自动合并。客户端重试必须复用 conv_id + handoff_key，新真实请求用新 key。key 不来自 LLM；身份在复用前校验，不同主体/owner独立。消息变化返回冲突，不泄露原 ID。理由码在去重前仍经过策略，但同请求多个合法理由不会重复建单。RLock 覆盖同 Service 的并发查询、创建和复用；8线程测试只建一条记录。

失败返回固定 handoff_service_unavailable，不暴露异常字符串，也不伪造记录。失败回执也绑定原请求；同 key 重放原失败，新 key 可在服务恢复后重新申请。没有自动写重试或不明外部执行状态。

成功事实保留在 Request 的后端回执中，后续工具被策略拒绝或模型异常/耗尽不会覆盖已有 created。Trace 每次调用仍保留各自结果（例如后来 policy_rejected），根/API保留可信成功回执。最终交接答复由后端固定渲染，成功包含 ID 和“模拟、非真实接单”，失败包含错误码和未完成事实；已有 Action 回执可一并保留。没有工具回执时，对生成内容中涉及人工/转接的句子做保守措辞替换，明确未创建记录；**措辞规则不产生业务状态**。该输出约束可能删去正常人工建议，任意间接措辞的语义一致性仍需真实模型评测。

沿用 N05：已创建交接后的 Memory 写故障返回200、memory_write_status=failed 和 memory_write_failed，保留可查询记录；未成功创建且没有确认完成 Action 时沿用原写失败行为。Memory 读取失败仍503并停止执行。未改 MemoryManager、Policy/HITL 或已有 Action/Provider 契约。

## Trace、独立评测和验收证据

`evaluation/handoff_cases.json` 的独立版本 a02-handoff-v1 覆盖明确人工、否定人工、合理越界拒绝、真实需介入的复杂投诉、创建失败、正常请求、重复请求。`evaluation/handoff_eval.py` 分别评分 should_handoff、requested、created、false_handoff、API/Trace一致、最终回执一致、记录数量及重复 ID。created 必须由实际 owner 查询记录证实；仅提供成功文本或伪造布尔字段不能通过。失败预期本身可正确通过，但不计为创建成功。未改既有 Eval baseline/T10 rubric。

复现命令（只 Fake SDK / FastAPI TestClient，不访问模型/Redis/Chroma）：

```powershell
uv run python -m evaluation.run_handoff_eval
uv run python -m pytest -q tests/test_handoff.py
```

原始 `/chat` body、工具 Trace、owner查询记录、评分及HEAD/Python另存 [A02-handoff-observations.json](A02-handoff-observations.json)，7/7。明确请求的 HTTP200 返回 status=created，required/requested/created=true、failed=false、handoff_id可查询；Trace根节点与API同形。失败用例HTTP200返回status=failed、error_code=handoff_service_unavailable、ID=null、无记录；重复用例同ID/reused=true。属于执行真实路由的进程内 Fake SDK HTTP集成，未启动网络服务，不代表真实模型或真人验收。

| 检查 | 结果 |
|---|---|
| Handoff专项（HTTP/状态/故障/权限/并发/Eval伪造回执） | 26 passed |
| Agent Loop / Tool Contract / Support | 45 passed（A02新增后更新冻结提示词完全相等的旧断言；历史实现/报告不改） |
| N01/N02/N03/N04/N05/N10安全与业务回归 | 134 passed |
| RAG/Tool/N06/N07契约及可选HTTP | 130 passed / 2 skipped（真实Chroma未启用） |
| 完整 uv run python -m pytest -q | 382 passed / 3 skipped |
| node --test tests/demo_ui.test.cjs | 12 passed；Demo展示代码未改 |
| uv lock --check / git diff --check | 53 packages / 通过 |

完整跳过项为 live Redis/Chroma Memory 与两个真实 Chroma HTTP测试；保留既有 AnyIO 弃用警告。部分专项运行出现既有 cash pytest缓存写权限警告，最终完整执行无该警告。没有运行收费模型、支付、真实人工服务、live数据服务或部署。

## 限制、文档与独立练习

模拟记录创建不等于真实客服接单；没有通知、分配、坐席、SLA、外部工单或持久化。进程内字典无TTL/容量管理，重启丢失、多worker不共享；锁仅当前Service内有效。复杂投诉和依赖故障仍需要Agent选择工具，Fake SDK通过不证明模型升级召回率；规则语言范围及拒绝解释质量需后续专项评测。原审查 C01 更广泛能力配置、C05 通用回复超证据、A01复合问题、N08/N09等本轮不处理。

README、两份核心Wiki和既有Workbench/progress同步当前路径；不修改其他Wiki或历史实验报告。N01/N02/N03/N04/N05/N06/N07/N10现有回归全部保留；A02只是复用Principal、Tool Contract、Trace和N05回执保留原则。

**独立故障注入练习**：将 HandoffService._create_record 暂换为抛异常；同 conv_id/key 连续两次要求人工，断言 failed、null ID、第二次reused=true、记录数0。恢复创建函数后同key仍failed，换新key变created且owner可查；再让模型下一步抛异常，解释为什么created回执不会被覆盖。画出 required→requested→created/failed 状态图并区分策略拒绝和真实创建失败。

建议提交信息：`feat(handoff): add principal-scoped structured demo handoff receipts`。停在verify，等待用户验收。
