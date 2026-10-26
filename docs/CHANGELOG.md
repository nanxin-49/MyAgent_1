# 变更日志

记录**每轮工作的主要修改、验证结果和提交**。任务定义与状态见 `CARTCARE_PLAN.md`；单任务完整证据见 `docs/reports/<TASK-ID>.md`；稳定协作规则见 `CLAUDE.md`。

写法：每轮追加一节，保留日期、任务 ID、改动文件、验证命令与结果、遗留问题、提交号。历史条目不改写；纠正用新条目说明。

---

## 2026-10-25 — 接手与启动验证（无任务 ID）

- **目的**：按交接文档核对项目能否从当前源码启动。
- **结果**：
  - HEAD `ea8ae67`；`uv lock --check` 53 packages；`pytest` **577 passed / 3 skipped / 1 warning**；Node **12 passed**。
  - 当前源码在 `127.0.0.1:8010` 启动成功，`/health` 为 Single 拓扑 `support_0`，知识库加载 6 个片段；`/demo`、`/docs`、`/openapi.json` 均 200。
  - 鉴权 401 生效；真实模型单次冒烟 200；确定性交接 `请帮我转人工客服` 创建记录且 0 次模型调用。
- **发现（未修改）**：
  - 运行中的 `echomind-app` 是 2026-09-27 旧镜像，仍是多 Agent 拓扑，不能作为当前源码运行证明。
  - `我要人工客服` 未被确定性门识别，模型调用 `request_handoff` 后被策略复核拒绝，返回“未创建记录”。fail-closed，但属明确请求漏创建，关联 `H1-1`。
  - Claude Code 会话 shell 注入 `ANTHROPIC_BASE_URL`，`load_dotenv()` 不覆盖，导致首次启动打到本地代理；用户本机环境不受影响。
- **文件**：未修改受版本控制文件；测试日志在 `logs/`（gitignored）。

## 2026-10-25 — 文档归档与仓库清理

- **改动**：
  - 新增分支 `claude/cartcare-harness`。
  - 47 个历史文件归档到 `cash/archive-20261025/`，清单见其 `MANIFEST.md`。
  - 保留 `docs/engineering/A05-rag-evaluation.md`（被测试 SHA256 锁定）；新建 `docs/reports/`。
  - 更新 `README.md`、两份核心 Wiki、`CLAUDE.md`、`CARTCARE_PLAN.md` 中的失效引用。
- **验证**：`pytest` **577 passed / 3 skipped**；Node **12 passed**；活动文档无死链。

## 2026-10-25 — cash 纳入版本库与变更日志

- **改动**：
  - 新增 `cash/README.md`；`.gitignore` 改为只忽略 `cash/` 下的缓存、CI 临时检出、旧数据、本机配置和凭据，跟踪 `cash/archive-20261025/` 与 `cash/wiki/`。
  - 新增本文件 `docs/CHANGELOG.md`，作为后续每轮修改的统一记录。
- **验证**：`git status` 确认无 `.env`、凭据或缓存进入暂存区；`pytest` 与 Node 结果不变。
- **提交**：见本次提交 `chore: archive superseded docs, track curated cash archive, add changelog`。

## 2026-10-25 — 根目录二次清理

- **改动**：
  - 删除空的 `scripts/`（无代码引用、未被跟踪）。
  - 删除 207 个 `__pycache__` 目录、`data/test-cache/` 和本次启动验证产生的临时日志。
  - 将 `data/default-kb-backups/`、`data/demo_docs/` 归档到 `cash/archive-20261025/data/`。
  - 删除 `docker-deploy.sh` 会自动重建的空挂载点目录 `config/alerts`、`config/grafana/*`、`config/nginx/ssl`。
  - 保留 `data/chroma`（Compose 挂载点）和 `logs/`（运行时目录）。
- **结果**：根目录剩 19 个目录，全部对应源码、运行数据、测试、评测或文档；无空目录（除上述两个运行时目录）。
- **验证**：`pytest` **577 passed / 3 skipped**；Node **12 passed**。

## 2026-10-25 — H0-1 修复 CI setup-uv 版本

- **改动**：`.github/workflows/tests.yml` 中 `astral-sh/setup-uv@v10` → `@v10.3.2`（标签已用 `git ls-remote` 核实存在）。
- **验证**：`uv lock --check` 53 packages；`pytest` **577 passed / 3 skipped**；Node **12 passed**；`git diff --check` 通过。
- **状态**：`verify` → 远端 PR 已通过（用户确认 All checks have passed），待用户确认置为 `done`。
- **报告**：`docs/reports/H0-1.md`。建议提交信息：`ci: pin setup-uv to v10.3.2`。

## 2026-10-25 — H1-1 第一批真实 `/chat` E2E

- **新增**：`evaluation/reports/H1-1/20261025T085310Z-batch1/` 独立运行器、fixture、5 个场景、原始证据与报告。
- **结果**：S3、S5 通过；S1 检索分数不足（0.168/0.215 < 0.35）、S2 未选检索、S4 未发起退款，共 2 pass / 3 fail。
- **预算**：真实模型 13 次请求，USD 0.013001（保守估算），未触发 halt。
- **隔离**：独立 Redis 6396 已停止；Chroma 前后 SHA 一致，无知识写入。
- **未改**：生产代码、Prompt、知识、阈值、Gold。
- **状态**：H1-1 `todo → doing`；修复运行（S2/S4/S1b，12 次请求 / USD 0.06）待授权。

## 2026-10-25 — H1-1 修复运行 1

- **改动**：`agents/support_agent.py` 增加通用 `[检索与显式动作]` 规则；新增 `tests/test_support_prompt_contract.py`（红 2 failed → 绿）。
- **结果**：S1B、S2、S4 **3/3 通过**；S1B 获得 `usable` citation，S4 直接提交退款并在 reviewer 审批后执行 1 次。
- **预算**：10/12 次请求，USD 0.0103392；Chroma 前后 SHA 一致；隔离 Redis 已停止。
- **未改**：PolicyEngine（≤500 自动、>500 审核）、知识、阈值、Gold；“所有退款都需人工审核”记为独立待办。
- **回归**：`pytest` **579 passed / 3 skipped**；Node **12 passed**。
- **状态**：H1-1 仍 `doing`；资格/缺参、审批拒绝/撤回、幂等、越权场景待后续批次。
- **后续调整**：按用户要求保持 ≤500 自动通过，Prompt 增加“先 `get_order` + `get_refund_status` 核对条件，再决定是否 `request_refund`”；契约测试已更新，尚未重跑真实模型。

## 2026-10-25 — H1-1 第二批真实 E2E

- **结果**：B1 调整后 S4、B2 过期拒绝、B3 缺参澄清、B4 越权查询 **4/4 通过**；真实模型 10 次请求，USD 0.012921。
- **B1 工具顺序**：`get_order` → `get_refund_status` → `request_refund`；审批前执行 0，审批后执行 1；退款 `pending`。
- **确定性 gate**：客户撤回、同键复用、异参冲突、跨用户不复用、过期 Policy 拒绝全部通过。
- **隔离**：Chroma 前后 SHA 一致；Redis 已停止。
- **状态**：H1-1 `doing → verify`，9 个验收场景均有成功证据，待用户验收。
- **遗留**：第一批 S1 长问法词法召回失败保留；审批撤回/幂等/Policy 拒绝为 unit gate 层级。

## 2026-10-25 — H1-1 学习与练习文档

- **新增**：`docs/H1-1-exercises-and-notes.md`，汇总 9 个独立练习、参考答案、证据层级与常见问题。
- **链接**：`docs/reports/H1-1.md` 增加“学习与练习”入口。
- **未改**：代码、Prompt、知识、阈值、Gold。

## 2026-10-25 — H2-1 评测框架：组件开关 + 脚本化假模型

- **新增**：`core/harness.py`（`HarnessConfig`，默认全开、非 evaluation 关闭即 raise）、`evaluation/scripted_model.py`（JSON 多轮脚本假模型）、`evaluation/scripts/` 示例、`tests/test_harness_switches.py`（10 测试）。
- **接入**：`EvaluationRuntimeFactory` → `ActionService`/`SupportRuntime`；`BaseAgent`、`SingleSupportAgent`、`MemoryManager` 接收配置。`ChatRequest`/`EvalRunInput` 无开关字段。
- **行为**：policy_guard、error_feedback、context_compression、loop_control、output_consistency 均可单独关闭；生产默认不变。
- **验证**：`pytest` **589 passed / 3 skipped**；Node **12 passed**；`git diff --check` 通过。
- **限制**：context_compression 在评测工厂中暂无可观察效果（工厂未构造 Memory）；policy_guard 仅评测假后端；loop_control 关闭仍有 1000 轮硬停止。
- **状态**：H2-1 `todo → verify`。

## 2026-10-25 — H2-2 录制回放 + 故障注入 + 轨迹打分 + pass^k

- **新增**：`evaluation/trajectory.py`（schema/录制器/H1-1 ledger 转换）、`evaluation/fault_injection.py`（5 类故障、on_call/sticky）、`evaluation/run_harness_eval.py`、`evaluation/cases/h2_2_cases.json`、`evaluation/trajectories/` 样本、5 个测试文件（16 测试）。
- **扩展**：`ScriptedModel` 支持 canonical content/stop_reason/usage/error 与 `from_trajectory`；`agent_trace_eval` 增加轨迹/禁止调用/终态评分；`system_eval` 增加 `pass_metrics`（pass@runs / pass^runs）。
- **运行**：`python -m evaluation.run_harness_eval` → pass@runs 6/6，pass^runs 5/6，trajectory_accuracy 7/8，forbidden_call_rate 0/8。
- **验证**：`pytest` **605 passed / 3 skipped**；Node **12 passed**；`git diff --check` 通过。
- **限制**：invalid_arguments handler 级非 validation 原形；RAG 失败统一 degraded；动作无 timeout；无本次真实模型调用。
- **状态**：H2-2 `todo → verify`。

## 2026-10-25 — H2-3 规模化评测集（确定性层）

- **新增**：`evaluation/h2_3/`（fixture、generator、180 条 cases、RAG stub、runner）、`tests/test_h2_3_suite.py`、`evaluation/reports/H2-3/report.json`/`report.md`。
- **覆盖**：FAQ 24、order 16、logistics 16、inventory 12、refund_allow 14、refund_approval 14、refund_deny 16、cancel 12、ownership 16、out_of_scope 12、injection 14、multi_turn 14。
- **确定性结果**：180 条，task success 1.0，safety 0，forbidden 0，citation 1.0；工具选择/参数/延迟/token 指标为 None（deferred）。
- **CI**：`pytest tests/test_h2_3_suite.py` 2 passed（约 1.8s）；全量 **607 passed / 3 skipped**；Node 12。
- **真实模型层**：deferred，估算约 830–960 次请求 / USD 0.9–1.1（保守上限 2.0），需单独预算授权。
- **状态**：H2-3 `todo → doing`（partial，真实模型层未跑）。

## 2026-10-26 — H2-3 真实模型 first run（原始证据）

- **运行**：300 case-runs，345 次成功请求，USD 0.2983；task_success 0.3233，safety 0。
- **问题**：314 个 turn 中 156 个 `Connection error`，指标被网络噪声严重污染，**不能作为模型质量结论**；原始记录在 `evaluation/reports/H2-3/real/RAW_RUN.md`。
- **修正**：连接错误最多 1 次重试 + 0.6s 节流；新增 `expected_agent` 区分组件回放与真实 Agent 安全行为；`answer_excludes` 增加否定语境判断。
- **real2 未运行**：权限门要求用户明确授权具体预算。建议授权 `800 次请求 / USD 1.6`，两轮合计 ≤USD 1.9。
- **状态**：H2-3 仍 `doing`。

## 2026-10-26 — H2-3 real2 部分运行（系统内存中断）

- **授权**：用户明确授权 800 次请求 / USD 1.6。
- **结果**：全量 180 完成，task_success **143/180=79.44%**，safety_violation 0；567 次请求 / USD 0.4889757；0 Connection error；p50 7,485ms / p95 10,781ms。
- **关键路径 k=3**：refund_allow 14/14（pass@3 14、pass^3 11）、refund_approval 14/14（12、12）、refund_deny 1/16、ownership 0/16。
- **中断**：系统内存不足终止后台进程，不是代码/模型/预算失败；无最终 report.json。
- **剩余**：233 请求 / USD 1.111；约 150 请求可完成剩余 k=3；恢复需用户明确要求。
- **状态**：H2-3 仍 `doing`。

## 2026-10-26 — H2-3 real2 完成（resume k=3）

- **结果**：300 case-runs（180 全量 + 60 关键路径 × 2）→ **250/300 = 83.33%**；pass@3 **57/60**，pass^3 **50/60**。
- **预算**：696 次请求，input 1,710,330 / output 72,380，USD **0.599955**；resume 阶段 0 Connection error。
- **分类**：order/logistics/inventory/injection 1.0；ownership 0.9375；refund_allow 0.9048；refund_deny 0.8958；refund_approval 0.8571；multi_turn 0.7143；out_of_scope 0.6667；cancel 0.4167；faq 0.2917。
- **安全**：2 次 forbidden attempt（refund_deny_03 run2/3）均被 Policy 拒绝、executor 0；全量 180 逐 check 安全率因首段中断不可恢复，只有新增 62 detailed run 有明细。
- **恢复**：`--resume` 只补缺失 62 run，未重复已完成 238 run；证据 `real2/final.json`、`FINAL.md`、`details.jsonl`。
- **状态**：H2-3 `doing → verify`，待用户验收。

## 2026-10-26 — H2-4 “只有模型 + 工具”基线

- **新增**：`evaluation/h2_4/`（`profile.py` 裸基线配置、`metrics.py` 安全与 overclaim 计数、`run_baseline.py` 入口、`summarize_details.py` 离线首轮汇总）、`tests/test_h2_4_baseline.py`（31 测试）。
- **扩展**：`evaluation/h2_3/real_model.py` 支持 `--profile full|bare`、`--max-tool-rounds`、`--no-key-runs`、单轮异常保留证据、`baseline_metrics`；`evaluation/topology_experiment.py` 把 harness 传给 `ActionService`。生产 `/chat` 不变。
- **真实运行**（授权 700 请求 / USD 1.0）：首轮 180 条 **138/180 = 76.67%**，404 请求 / USD 0.330853；全 harness 同轮 143/180 = 79.44%。
- **安全**：Policy 拦截 6 次危险尝试（6 个 case），已执行违规 **0**，进入审批 16 次；overclaim 1 条（`injection_13`，交接被拒后仍称已创建）；loop 截断 0，>3 轮 turn 0。
- **归因**：关闭 `error_feedback` 后 ownership 1.0 → 0.5625（`not_found` 被隐藏成“已受理”）；关闭 `output_consistency` 后出现 1 条完成声明；`context_compression` 在本 runner 无 Memory，记 N/A。
- **中断与额外运行**：首段在 144/180 被系统低内存终止；`--resume` 补齐首轮，但因 H2-3 runner 默认关键路径 k=2/3，多跑 117 run（296 请求 / USD 0.2658），到 700 请求上限停止；部分 pass@3 54/58、pass^3 40/58，不计入 H2-4 验收。`run_baseline` 已默认 `--no-key-runs`。
- **验证**：全量 `pytest` **638 passed / 3 skipped**；Node **12 passed**；相关回归 43 passed；`git diff --check` 通过。
- **证据**：`evaluation/reports/H2-4/bare/FIRST_PASS.md`（首轮口径）、`final.json`（297 run）、`PARTIAL.md`（中断快照）。
- **状态**：H2-4 `todo → verify`。

## 2026-10-26 — H3-1 工具循环控制

- **新增**：`core/stop_reason.py`（六种 `StopReason` + 窄澄清分类）、`tests/test_h3_1_loop_control.py`（15 测试）。
- **扩展**：`HarnessConfig` 增加 `max_tool_steps=8`、`max_tokens_per_turn=60000`、`duplicate_call_limit=3`、`tool_timeout_s=30`；`BaseAgent` 循环累计 token、检测连续重复调用、检查步数预算，超限返回回执或固定话术并写停止原因；`execute_tool` 支持只读超时上限；`SupportResult`/Trace 增加 `stop_reason`；trace 增加 `attempts`/`timeout_s`。
- **默认值依据**：H2-3 real2 + H2-4 首轮共 373 个真实 turn，工具步数 p50=2 / p95=3 / max=4，仅 1 个 >3；轮次上限保持 3。
- **行为变化**：生产默认下，连续第 3 次相同调用、第 9 个工具步或单轮 60k token 会主动停止；`loop_control=False` 时四项限制一起关闭；两个旧测试显式提高 `duplicate_call_limit` 以隔离重复检测（未放宽断言）。
- **验证**：全量 `pytest` **653 passed / 3 skipped**；相关回归 113 passed；180 条确定性套件 180/180、safety 0；Node **12 passed**；`git diff --check` 通过。
- **限制**：写动作仍不设执行超时（N11 归 H4-3）；`needs_clarification` 仅观测；token 预算未在真实模型下验证。
- **状态**：H3-1 `todo → verify`。

## 2026-10-26 — H3-2 结构化错误回传

- **新增**：`core/tool_contract.py` 的 `suggested_action_for()`、`truncate_tool_payload()`；`evaluation/h3_2/`（恢复探针、5 条故障用例、对比 runner）；`tests/test_h3_2_structured_errors.py`（23 测试）。
- **行为**：失败工具 payload 统一补齐 `error_code`/`error_type`/`retryable`/`suggested_action`，业务嵌套 `error` 与动作字段保留；模型可见 tool_result 超过 `max_tool_result_chars=8000` 时截断并标 `truncated`；Trace 记录该标记；`error_feedback=False` 仍在截断后覆盖为 ack。
- **实测**（确定性恢复探针）：`error_feedback` 开 **5/5 恢复**，关 **0/5**；两臂 `executor_calls=0`。不是真实模型结论，真实对比留给 H3-6。
- **验证**：全量 `pytest` **676 passed / 3 skipped**；相关回归 83 passed；180 条确定性套件 180/180、safety 0（历史 report.json 已恢复）；Node **12 passed**；`git diff --check` 通过。
- **限制**：`suggested_action` 只是建议；截断只作用于模型可见 payload；非字典超长 payload 变成带 `preview` 的对象。
- **状态**：H3-2 `todo → verify`。

## 2026-10-26 — H3-3 上下文预算与工具结果压缩

- **新增**：`core/context_budget.py`（token 估算、六类构成、按优先级压缩）、`evaluation/h3_3/`（8 条用例、两臂对比 runner）、`tests/test_h3_3_context_budget.py`（8 测试）。
- **接入**：`BaseAgent` 每轮记录 `context_rounds`（`estimated_tokens`、`compressed`、`over_budget`），超 `max_context_tokens=16000` 且 `context_compression` 开启时压缩旧工具结果/背景/对话；system、工具 schema、当前用户消息不动。Trace 根节点可查。
- **实测**（确定性，预算 4000）：on/off task success 均 **1.0**；估算 token **59,953 vs 170,170（−64.8%）**；压缩轮次 7 vs 0；executor_calls 均 1。token 是估算值，不是 tokenizer 口径；真实模型质量对比留给 H3-6。
- **验证**：全量 `pytest` **684 passed / 3 skipped**；相关回归 102 passed；180 条确定性套件 180/180、safety 0（历史 report.json 已恢复）；Node **12 passed**；`git diff --check` 通过。
- **限制**：固定部分本身超预算时标 `over_budget`，不破坏 system/tools；`context_compression` 同时控制 Memory 压缩和 prompt 压缩。
- **状态**：H3-3 `todo → verify`。

## 2026-10-26 — H3-4 输出一致性检查

- **新增**：`core/output_consistency.py`（退款/取消完成声明、到账声明、`evaluate_action_claims`）；`tests/test_h3_4_output_consistency.py`（23 测试）。
- **接入**：`SingleSupportAgent.handle` 在 `output_consistency` 开启时比对回答与本轮 `action_result` / 交接回执；不一致时改写为动作回执或固定如实话术，并把 `consistency_warnings` 写入 `SupportResult` 与 Trace 根节点。
- **覆盖**：`refund_completed_without_execution`、`cancel_completed_without_execution`、`refund_arrival_unverifiable`、`handoff_created_without_receipt`；`output_consistency=False` 仅评测消融。
- **回放**：H2-4 `injection_13` 的“已创建模拟交接”被改写为“本次未创建人工交接记录。”；审批中的“退款已到账”被改写为等待审批回执。
- **口径统一**：H2-4 `metrics.py` 复用 core 声明函数；同一批 180 条明细仍为 task 0.7667、Policy 拦截 6、overclaim 1。
- **验证**：全量 `pytest` **707 passed / 3 skipped**；相关回归 116 passed；180 条确定性套件 180/180、safety 0（历史 report.json 已恢复）；Node **12 passed**；`git diff --check` 通过。
- **限制**：窄措辞启发式；“到账”在模拟后端永不可证明，即使动作 completed 也改写；未做真实模型回归。
- **状态**：H3-4 `todo → verify`。
