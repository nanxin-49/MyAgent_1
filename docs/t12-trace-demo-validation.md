# T12 · Trace / Demo UI / README finishing

最终状态：**done**，2026-10-07 用户已验收并授权通过完整阶段 PR 合入 main。T01–T11 按本轮用户确认保持 done。

## Changed files

- `demo/static/index.html`, `style.css`, `demo.js`, `scenarios.json`：同源轻量 Demo；十个场景仅填入消息。展示回答、工具风险/校验参数/结果、检索状态、引用、Policy、审批按钮和最新动作状态。
- `demo/prepare.py`：复用现有演示 fixture 生成器，生成新鲜业务数据供启动注入；不更改 Provider、Policy 或历史报告。
- `api/main.py`：`/demo` 与静态资源入口；扩展既有有界 Trace 的 Memory 安全计数、读写状态及阶段耗时。
- `agents/agent_orchestrator.py`：仅扩展 Trace 投影，增加检索文档 title 和确定性 helper 结果白名单；不改变工具执行或 Agent 行为。
- `tests/test_demo_ui.py`, `tests/demo_ui.test.cjs`：HTTP/展示契约、citation 状态、nullable routing、Memory 读写状态、helper 输出安全投影、审批/拒绝/恢复渲染。
- `README.md`, Workbench HTML/progress, 两份核心 Wiki：当前架构、设计取舍、使用步骤、受条件限定的 Eval 证据、已知限制。
- `.gitignore`：忽略本地 uv cache；`docs/demo-screenshots/`、`docs/t12-demo-observations.json`：本轮真实浏览器证据。

## Final production architecture / call path

Client → API → MemoryManager → SingleSupportAgent → Unified Tool Runtime → RAG / Providers / ActionService（PolicyEngine / HITL / Executor）→ Response / Memory 回写 / Trace。

Eval 为独立触发。前后业务链路相同；新增 Client `/demo` 消费既有 API 和展示字段。没有重写 Trace backend，没有改 Policy rules、Provider、ActionService/HITL、RAG threshold、embedding、Memory policy 或生产 Single topology。

## Trace audit

| 观测项 | 证据 / 展示 |
|---|---|
| request_id / topology / agent_type / tools_used | `/chat` + `/trace/tool/{request_id}`；single / support |
| tool risk / validated input / tool result | 原有 risk_level / validated_input / business_result / action_result / retrieval_hits；本轮补充 helper_result 白名单 |
| RAG status / citations / source / title / policy_version | 原有 citation contract；新增 retrieval_hits.title，UI 按 document_id + chunk_index 关联 |
| policy decision / action status | 原始 Tool Trace 快照与当前 ActionResult 分开展示；没有从回复推断成功 |
| memory | read/write 状态、消息/长期记录/画像字段计数、摘要存在标志、阶段耗时；不存原始上下文 |
| latency | latency_ms 为 Agent runtime；request_latency_ms 为 Memory read + Agent + Memory write，响应序列化前；后台画像/网络时间不计 |

无隐藏 chain-of-thought。profile_update_status=scheduled_unobserved，不把调度当落库成功。早期 Redis 读失败仍返回 503，Agent 不执行，不生成 Agent Trace；写失败保留 failed 状态并沿用原异常行为。

## Demo scenarios / usage

十个场景：FAQ / policy、order lookup、logistics lookup、inventory clarification、refund allow、refund require approval、refund deny、cancel、ownership violation、unsupported request。

README 给出 Python 3.12 + uv、外部 Redis/Chroma、本地环境配置、生成 fixture、启动 API 与 `/demo` 使用步骤。退款窗口依时间判断，重复动作会改变内存状态；新建会话不重置业务 fixture，重新生成并重启才恢复演示业务状态。UI 没有预设成功或绕过审批。

## Tests

最终代码执行结果：

- `uv lock --check`：通过（53 packages）。
- `uv run python -m pytest -q -p no:cacheprovider`，显式启用 CARTCARE_TEST_LIVE_MEMORY=1 / CARTCARE_RUN_CHROMA_HTTP_TEST=1，CHROMA_HOST=127.0.0.1 / CHROMA_PORT=8001：**152 passed**，无 skip；包含真实 Redis/Chroma 隔离临时数据集成。
- 最终默认规范命令实际执行：**150 passed / 2 skipped**（两个 opt-in 集成未开启）；显式开启集成的完整结果为上面的 152 passed。
- `node --test tests/demo_ui.test.cjs`：**12 passed**（fake DOM/API，仅展示与 API 消费契约）。
- `node --check demo/static/demo.js`：通过。
- Workbench 内联 JS 语法检查：通过。
- `git diff --check`：通过。

有一项上游 Starlette/AnyIO BlockingPortal deprecated warning，不影响通过。Windows 沙箱的 socketpair 卡住导致最初 HTTP 测试未完成；允许本地 socket 的执行环境重跑通过。uv 默认缓存权限错误通过仓库内 UV_CACHE_DIR 解决。第一次 opt-in RAG 使用 .env 的容器地址 chromadb:8000 得到 502；显式配置本机 127.0.0.1:8001 后全量通过。未改变 Chroma 客户端或加入本地 fallback。

## Real browser evidence

2026-10-07，独立 localhost:8012、生产 lifespan/真实模型/真实 Redis/Chroma HTTP、新鲜演示 commerce/action fixture；使用 computer-use 技能检查浏览器。

- FAQ request_id `e3910aa9`：usable，标题“退款政策”，source `demo:cartcare-default/refund-policy`，policy_version `refund-cancel-v1`，回答保留 citation；Agent 5031 ms、request 5125 ms。
- Refund approval request_id `c0d5308d`：get_order / get_refund_status / request_refund / create_handoff_summary；require_approval / awaiting_approval。get_refund_status 的 not_found 如实展示。Agent 4657 ms、request 4765 ms。
- 点击 Resume：仍 awaiting_approval。点击 Approve：completed，execution_result.simulated=true。原 Tool Trace 仍 awaiting_approval；当前 ActionResult 单独展示。
- 原始浏览器 API/Trace 与最终 ActionResult 保存于 `t12-demo-observations.json`；截图见 `demo-screenshots/faq.jpg`, `pending-approval.jpg`, `approved.jpg`, `approval-detail.jpg`。

用于验证的独立 8012 服务已停止；按 README 启动自己的 API 后访问 `/demo`。

这些是两个真实演示场景的 smoke，未声称本轮完成十场景真实模型验收。Reject/Resume 和其他场景由确定性 API/业务回归与 JS 渲染契约覆盖。记录和截图捕获于本轮 helper_result 追加前，故该历史浏览器 Trace 的 helper 缺少输出；最终 helper 投影另有自动化测试。T10/T11 历史报告原样保留。

## Acceptance criteria

| DoD | 结果 |
|---|---|
| 单请求关联工具、引用、Policy、动作、Memory 与耗时 | 已接通；既有 Trace backend 复用，有限输出投影和早期失败边界如上 |
| 轻量 UI / 十场景 | 已提供，不新增前端框架或依赖 |
| HITL 消费现有 API | Approve / Reject / Resume / Refresh；后端决定语义 |
| citation 状态区分 | usable 才有可靠引用；其余状态和未检索明确显示 |
| README / 最终架构 | Single 主架构，设计原因、三类例子、T10/T11 条件与全部要求限制 |
| 核心业务保持 | 无业务规则或数据适配实现改动 |
| 测试与公开展示清理 | Python 152 + JS 12 通过，核心展示中未发现 EchoMind/bear/3.14 残留；兼容标识保留 |

## Newly discovered issues / remaining limitations

- 本机可选独立 Prometheus 端口不可绑定（WinError 10013）；本地 Demo 使用既有 PROMETHEUS_PORT=0，/metrics 仍可访问；未修改 Monitor。
- Chroma PostHog capture 兼容日志仍出现，未阻止 HTTP 检索或测试；不在 T12 重构。
- demo user_id 非正式认证；in-memory commerce/action backend 和 PendingAction Store/Trace 持久化有限，未接外部商城/支付。
- lexical embedding 与阈值是基线；unsupported escalation、ownership 严格在线证据缺口仍保留。
- 长期过期 Chroma 记录按有效期过滤，但无后台物理清理任务。
- 工具结果为受控投影，不是完整原始结果；profile 完成状态和早期 Memory 读失败 request trace 尚未补齐。

## Documentation drift

README、Workbench/progress、两份核心 Wiki 已更新。Workbench 原 Memory LLM 摘要/未来边界、Provider 无写动作以及旧目标架构表达已按当前实现校正；T09 数据标为历史基线。其他 Wiki 与 assets 是历史材料，没有批量重写；使用 README 与核心 Wiki 为当前权威。浏览器 localStorage 可能保留旧进度，需通过 Workbench 导入更新后的 progress JSON。

## Suggested task state / commit

**T12 = done**，实现与测试完成，2026-10-07 用户已确认验收。

`feat(demo): finish trace UI and CartCare documentation`
