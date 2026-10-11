# CartCare 当前问题复核与全项目审查

日期：2026-10-11。HEAD：`09efd3443d2e7b6e03fba7d13fe660c483b30583`。

审查对象为当前未提交工作区，包含之前的文件整理、核心文档校对及用户已有 hardening 文件。读取 API、Agent/工具循环、Skill、Provider、Policy/Action、RAG、Memory、Monitor、Eval、Demo、CI 和部署配置及相关测试。没有修改生产逻辑、改变拓扑、提交代码、启动部署或重跑收费模型实验。

**主要判断：当前已经有可解释的 Single Agent + Tools + Policy/HITL + RAG + Memory + Trace/Eval 主链路，但状态一致性、身份边界、故障恢复、知识更新及评测覆盖还有缺口。恢复多个 Agent 本身不能解决这些问题。**

证据分为：本地隔离复现、代码路径确认、历史运行证据、待测设计风险。隔离复现使用 Fake SDK、假 Redis/Chroma 或内存业务后端，不能作为真实模型质量或真实支付验收。

## 1. 之前发现的问题，重新归纳

| 编号 | 问题 | 当前结论与影响 | 依据 |
|---|---|---|---|
| C01 | 场景范围缺少明确能力声明 | 当前定位为商品、订单、物流、售后客服；默认知识只有少量通用演示资料。是否支持订票等问题主要由模型判断，没有商家/行业能力配置、商品类别边界及统一“不支持”原因码 | `agents/support_agent.py:25`、`mcp/knowledge_base.py` 默认文档、当前工具注册表 |
| C02 | 意图理解、结构化实体与辅助工具脱节 | `/chat` 不再运行 IntentRecognizer，`req.intent=None/entities={}`；部分 helper 仍依赖这些旧字段。移除分类器未等于不理解意图，但辅助工具缺少新输入来源；T10 未独立测“分类器是否有价值” | `api/main.py:376`、`agents/support_agent.py`、`agents/agent_orchestrator.py:543/580/632` |
| C03 | 复合问题没有逐项完成检查 | 可返回多个工具调用，同轮串行、依赖结果下一轮获取；最多 3 次主 Agent 模型调用。没有子任务状态、剩余事项检查；异常或耗尽后的 Action 回执只取最近一个动作，不能代表整条请求完成 | `agents/agent_orchestrator.py:261/287/410` |
| C04 | 转人工缺少结构化交接 | 输出关键词决定 `escalated`，可被“不需要人工客服”误触发；用户要求转人工也没有确定性保证。`create_handoff_summary` 是摘要，不生成 handoff_id/持久化工单/状态，未接真实客服平台 | `agents/agent_orchestrator.py:478`、摘要 helper、T10/T11 后续事项 |
| C05 | 回答可能超出工具证据 | 正常回答由模型自由生成，模拟 backend 的标识与业务限制并未逐句强制落实。历史回复出现取消后承诺原路退回等工具未证明的信息 | `evaluation/reports/support_production/observations.json`、`actions/backend.py:72` |
| C06 | Skill 匹配较粗，内容延续旧角色 | 三个 Skill 仍在使用；当前消息关键词命中后注入 prompt，跨角色限制在 Single 中被跳过，字符预算截断。缺少对上下文、否定、组合诉求及注入效果的评测；不是独立执行工作流 | `core/skill_loader.py:122`、`agents/support_agent.py:21`、`skills/` |
| C07 | 没有请求总时限与明确超时体验 | 单工具读超时、SDK 超时/重试、Nginx 60 秒读取等待分别存在，不能组成总预算；Demo 无 AbortController、流式进度或后台状态恢复。慢请求与动作已执行后的响应失败未统一处理 | `core/tool_contract.py:133`、`config/nginx/nginx.conf`、`demo/static/demo.js` |
| C08 | 记忆与动作/Trace 持久化边界有限 | Redis 工作记忆和窄范围长期记忆实际存在；Action Store/业务数据/Trace 仍在进程内，重启和多 worker 不共享。Chroma 过期记录读取后过滤，无自动物理清理；后台画像调度无完成状态 | `memory/conversation_memory.py`、`actions/store.py`、`agents/support_agent.py:77`、`api/main.py:412` |
| C09 | 评测不足以证明广泛问答能力 | 少量冻结演示问题验证了部分工具路径，但缺少复合诉求、跨商品类别、否定转人工、连续故障、同键异参、更新政策、并发 Memory 等覆盖；citation 存在不等于每句都被支持 | 现有 Eval 数据集、真实模型历史报告、当前测试 |

### 需要修正的解释

- **不能直接认定原始多 Agent 更合理，或删除 Intent 是错误。** T10 只支持当前十类演示工作负载中 Single 更省调用，两组严格任务通过都为 24/30；主辅协作与 Composer 没有执行。跨行业、复杂组合任务仍没有比较证据。
- **串行执行是后端默认循环，不是 LLM 决定是否并行。** 独立只读工具并发值得测，但必须有工具级并发许可、限流和依赖处理；危险动作不应因一个全局开关被并发执行。
- **订票拒绝不必自动转人工。** 需要先声明业务能力，并区分合理越界拒绝、缺参数、依赖失败及确实需要人工。历史 unsupported 的 `escalated=0` 是与既定 rubric 不符，不能单凭这一项认定其文字答复不合理。
- **ownership 严格场景失败不等于越权执行。** 历史案例在只读订单查询处拒绝，未执行 backend；评分要求出现 ActionService 拒绝证据，所以任务项失败。
- Memory 没有消失，也不是原始聊天全文无限写入 Chroma。当前长期记录刻意限制为咨询主题和明确沟通偏好，这个边界应保留。

## 2. 全项目审查补充的问题

优先级：P0 优先修复身份/数据边界和错误动作复用；P1 直接影响结果正确性与恢复；P2 评测、运维及解释性完善。以下是修复排序，不表示已连接真实支付平台。

| 编号 / 优先级 | 新发现或进一步确认 | 可观察后果 / 复现结果 | 代码位置 / JSON issue |
|---|---|---|---|
| N01 / P0 | 幂等命中在校验身份之前返回，且缺少异参冲突判断 | 同一外部 key 从 10 元改到 20 元，仍返回 10 元旧动作；传入返回值中的内部 key，另一用户拿到原用户动作。普通跨用户同外部 key 的路径确实有作用域；复现未重复执行支付 | `actions/service.py:159`、`:369`；`IDEMPOTENCY` |
| N02 / P0 | caller 自报身份，审批无 reviewer 权限，Trace/管理接口无独立访问控制 | 无凭据请求最近 Trace 返回 200；只填写动作所有者 user_id 就能批准 600 元待审批模拟退款。既有 owner 检查存在，缺少可信 Principal 和审批权限校验；知识添加/上传、Skill reload、Eval 同样无认证依赖 | `api/main.py:252/436/549/562/629/727`；`TRACE_NO_AUTH`、`APPROVAL_CLIENT_IDENTITY` |
| N03 / P0 | Provider 校验错误包含原始输入，所有权检查在其后 | 给另一个用户的订单制造缺字段后，错误详情包含该订单的合成敏感标记；正常合法记录会校验 ownership。错误经 Tool handler 会进入模型，不能仅依赖正常读路径保护 | `providers/implementations.py:73`、`providers/errors.py:29`、`agents/tools.py:268`；`PROVIDER_ERROR_LEAK` |
| N04 / P1 | 模拟退款写入与退款查询不一致 | 动作和 execution_result 均 `completed`，订单为 `refund_pending`，却没有 RefundRecord；继续问“退款进度”读不到刚才的退款。`completed` 可以表示命令完成，但必须明确与资金到账、退款流程状态的区别 | `actions/backend.py:56`、`providers/mock_backend.py:74`；`REFUND_READ_WRITE` |
| N05 / P1 | 动作成功被 Memory 写入失败遮蔽 | Fake 模型取消订单已经执行一次、Action 为 completed；随后 add_message 失败，HTTP 返回 500。需要可查询回执/请求恢复或 Memory 降级策略，避免用户误判后重新请求 | `api/main.py:399`；`ACTION_SUCCESS_MEMORY_FAILURE` |
| N06 / P1 | Knowledge 更新只 upsert 新内容 hash，无旧片段退役 | 同 document_id/version 修改 7 天为 30 天后两个片段都保留、共享同一 citation；添加 v2 后旧 v1 仍可 usable。上层按 citation 去重可能保留旧内容。已有未来政策 effective_at 检查，但没有现行版本/废止策略 | `mcp/knowledge_base.py:87/134`、`mcp/rag_contract.py`、`mcp/tool_manager.py:417`；`KNOWLEDGE_UPDATE` |
| N07 / P1 | 重排输出缺少有效非空结果校验 | 模型返回合法 JSON `[]`，最终 success=true、retrieval_status=usable，却无命中和 citation。异常 JSON 会 fallback，但合法错误结构可能穿过；重排跳过/失败也可能标 reranked=true | `mcp/tool_manager.py:431/439`；`RERANK_EMPTY_USABLE` |
| N08 / P1 | Memory 压缩事务前的快照与并发写入不一致 | 读取 15 条快照后另 6 条写入，ltrim 保留最新 5 条；第 1 条新增订单引用既不在摘要也不在工作记忆。事务保证写操作原子性，不能保证快照包含并发内容 | `memory/conversation_memory.py:212`；`MEMORY_COMPRESSION_RACE` |
| N09 / P1 | 画像更新读取最新用户消息，未绑定触发消息 | 用户说“请用英文回复”，后台任务尚未执行就来了新查询；后台读取新查询后不存原偏好。不同并发更新还存在 read-modify-write 覆盖风险，后者仅代码风险未测 | `memory/conversation_memory.py:150`、`api/main.py:412`；`PROFILE_UPDATE_RACE` |
| N10 / P1 | API 内置评测与当前业务运行时不隔离 | startup 的 evaluator 直接持有 `/chat` 的 runtime；带动作的评测可取消当前 backend 中的订单。隔离复现实际 evaluator 方法后订单变为 cancelled；CLI 实验隔离不能证明 `/eval/run` 隔离 | `api/main.py:207/727`、`evaluation/evaluator.py:321`；`EVAL_SHARED_STATE` |
| N11 / P1 | 同步读超时不终止 worker，重试可重叠 | 两次只读调用均超时，返回时 0 次完成，返回后原有两个 worker 都完成。现有默认 read 工具不一定重试，但配置启用重试后会放大依赖压力；未发现危险动作被自动超时重试 | `core/tool_contract.py:122/149`；`READ_TIMEOUT_WORKERS` |
| N12 / P2 | 默认业务 Prometheus 指标未注册，延迟口径错误 | port=None 时 `_prom={}`，即使 `/metrics` 可读，也只有其他默认注册内容；启用业务指标后每次采集将累计平均延迟 observe 到 Histogram，没新请求也新增样本；requests_total 声明却无增量写入，默认桶不适配毫秒 | `api/main.py:196/570`、`monitor/performance_monitor.py:143/145/183`；`PROM_DEFAULT`、`PROM_DISTRIBUTION_ALERTS` |
| N13 / P2 | 持续告警重复追加，没有去重/恢复/容量边界 | 同一平均延迟超过阈值，连续采集三次产生三个告警，`_alerts` 长期累积；工具监控主要是 RAG ToolManager 统计，不代表所有业务/动作调用成功率 | `monitor/performance_monitor.py:243`、`:250`；`PROM_DISTRIBUTION_ALERTS` |
| N14 / P1 | `/health` 不能表示当前业务就绪 | orchestrator 非空就返回 ok，不检查 Redis/Chroma；Fake Redis 读取失败时 `/chat=503`，同一应用 `/health=200`。应区分 liveness 与 readiness，不必每次昂贵地检查模型 | `api/main.py:317`；`HEALTH_READINESS` |
| N15 / P2 | Nginx 健康检查调用镜像没有的 Python | Compose 使用 nginx:alpine，却配置 python 探活。Docker 只读检查发现现存已停止容器的健康日志明确为 `python: executable file not found`，失败 streak 770；不是当前在线网关不可用的证明 | `docker-compose.yml:123`；见下文历史容器证据 |

### 其他代码确认与待测项

1. **政策说明与确定性规则缺少发布一致性检查**：知识库可导入另一版本/退款窗口，但 PolicyEngine 仍按自身版本执行。权威规则留在代码是正确的，需要防止文案发布后描述与执行不一致。未模拟真实运营发布。
2. **API 资源边界不足**：ChatRequest 缺消息长度边界；top_k 无上限；批量文档/评测条数无上限；upload 的 10MB 检查发生在完整 read 后。Nginx 有 body 限制和限流，但 Compose 也直接暴露 8000，不能把网关限制视作 API 自有边界。未做压力测试。
3. **Memory 过期过滤在召回后执行**：过期的 top-K 命中可能挤掉仍有效的主题；没有自动清理。没有把过期内容直接作为有效记忆返回，但召回率与存储增长需要专项验证。
4. **知识/用户文本的间接指令覆盖未评测**：工具结果、用户历史、Skill 都进入模型上下文；Policy/ownership 的硬规则已有确定性门控，不能声称模型可直接绕过它们；仍需测试知识注入导致越证据回答或不当读工具选择的风险。
5. **Eval baseline 自动覆盖且未校验同数据集**：每次运行保存本次报告为 baseline、与上一轮评分比较；可变问集下的“退化”不一定是同口径比较。保留 T09–T12 冻结报告，不用动态 baseline 替代它们。
6. **CI 与 canonical 环境覆盖不同**：现有 CI 使用 pip requirements 跑 Python，未运行 uv lock 检查和 JS Demo 测试；这不表示当前 dependencies 已不一致，本轮 uv lock 检查通过。
7. **实验 fixture 与 startup 状态共享方式不同**：`isolated_business` 给 read/write 各自 deepcopy，startup 用同一 business_data 浅拷贝。实验中的动作后读状态可能与实际 API 不同；原实验不改写，后续需要动作后查询的专项数据集。
8. **资源关闭与日志边界**：lifespan 未关闭独立 classifier/RAG/evaluator SDK client；画像后台任务未统一回收；Skill INFO/RAG 日志包含用户文本。需生命周期和敏感字段测试，未进行长时资源实验。

## 3. 评测事实与解释范围

历史报告只读取，没有重新计算或覆盖：

- [Production Single 回归](../../evaluation/reports/support_production/regression.md)：真实模型 + Chroma HTTP + 模拟业务后端，10 场景一轮、EmptyMemory。task_success 8/10，tool_selection 9/10，可观察参数 6/6；平均 HTTP 延迟 3686ms。grounding/citation 只有 1 个适用案例，不能概括为所有回答 100% 有依据。
- [T10](../../evaluation/reports/t10_topology_comparison.md)：两组 task_success 均 24/30，Single 模型调用 76 vs Multi 115、工具 59 vs 78、平均实验延迟 3937.1 vs 6633.3ms；没有实际主辅协作，不能外推所有领域。
- [T11](../../evaluation/reports/t11_memory_acceptance.md)：历史真实 Redis/Chroma 与真实模型的演示验收；已有隔离、动态事实刷新和画像案例通过，并未覆盖本轮并发压缩/延迟画像复现。

“请求返回了文本”“工具按协议完成”“用户所有问题已解决”“实际退款资金到账”是不同指标。`agent_success_rate` 目前主要对应 Agent execution 返回成功，不能作为 task_success。

## 4. 本轮复现与验证

- [复现脚本](audit_20261011_probe.py)：运行 `uv run python docs/engineering/audit_20261011_probe.py`；**15 条复现观察全部断言成立**。断言确认当前缺陷，不是修复后的回归测试。
- [原始观察](audit-20261011-observations.json)：保存 HEAD、Python 3.12.3、环境、时间、证据类型、每项实际结果与限制；未记录真实客户信息。
- `uv lock --check`：通过，53 packages。
- `uv run python -m pytest -q`：150 passed、2 skipped；跳过真实 Redis/Chroma opt-in 集成。沙箱首跑额外有 pytest cache 权限警告；正常权限复验消失，仅保留既有 AnyIO 弃用警告。
- `node --test tests/demo_ui.test.cjs`：12 passed。
- `git diff --check`：通过；既有 `.dockerignore` LF/CRLF 提示不是 diff whitespace 失败。
- Docker 只读检查：`echomind-nginx`，Image=`nginx:alpine`，Running=false、Status=exited，FinishedAt=`2026-10-02T12:55:04.224025453Z`。保留的 Health 状态为 unhealthy、FailingStreak=770，最近五条历史探活均报 `exec: "python": executable file not found in $PATH`。没有启动/重启容器。
- 未执行：真实模型 HTTP E2E、live Redis/Chroma 集成、并发负载测试、部署验收和远端 CI。

## 5. 推荐处理顺序

1. 幂等复用身份/参数冲突、Provider 错误脱敏、可信调用者及 reviewer 权限；用现有 Service/Provider 接口做小改动和失败测试。
2. 成功动作回执与 Memory 失败恢复、退款后的查询一致性、知识更新/退役及重排结果校验。
3. 结构化 Handoff、复合问题逐项完成状态、总请求预算；可独立于单/多 Agent 拓扑实现。
4. 并发 Memory 与绑定触发消息的画像、Eval 隔离、readiness、指标修正及探活修正。
5. 扩充冻结评测集，比较检索方案与受控只读并发；只有场景/工具边界和结果需要时再比较多个 Agent。

每次处理一项，不将本清单当作全部同时实施的 mandate；与现有 hardening A01/A02/A03-lite/A04/A05/A07 复用，不新建平行任务状态源。涉及 A01/A04 的已复现缺陷应保存本轮证据并补修复后回归测试，再按现有 Workbench 记录 `verify`，由用户验收。

## 6. 文档、范围与独立练习

本轮仅新增本审查报告、复现脚本与观察 JSON；生产调用链前后不变。之前整理导致的未提交改动、用户已有 AGENTS/hardening/progress 内容全部保留。

README/两份核心 Wiki 的当前主链路一致，不需要恢复旧 Intent/Multi 说明；新缺陷在本报告集中记录，修复对应模块时再更新核心文档和 Workbench。`providers/mock_backend.py` 首部仍称“未接 API”，与 startup 实际注册冲突，应在对应 Provider 修复时顺手校正。Workbench 历史 T01/T10 文字按历史里程碑理解，不能覆盖当前 Single 基线。

**建议状态**：此次审查材料 `verify`；不是 A 系列已修复，也不改变 T01–T12 的历史 done。没有提交、推送或业务修复。

**独立练习**：不看 Codex，运行复现脚本并选 N01 或 N06，画出“请求参数 → 查旧记录 → 校验/返回”的实际顺序，解释为何已有测试能全部通过；随后写期望安全行为的最小断言，指出需要改哪条分支。可以从 `IDEMPOTENCY` 的 20 元请求返回 10 元旧结果开始。

建议提交信息（只包含本轮审查材料时）：`docs: record CartCare audit and isolated defect reproductions`。
