# A05-ANS24-REPLY：fixed / verify

等待人工验收，本轮完成后停止。A05 整体仍 doing / partial，B1 / B1-PREP 保持 blocked。

## 修改及调用链

起始 HEAD `cae395ff38cf96e3a021999ec0f6b9c5b166afa4`，存在前轮未提交的历史交接路由修复、Workbench/progress 更新和真实 E2E 报告。本轮唯一生产代码修改为 `agents/support_agent.py`，另新增 `tests/test_handoff_reply.py`、本目录证据，并更新现有 Workbench/progress 的 REPLY 状态。未提交或推送。

实际路径仍为 `/chat → SupportRuntime → SingleSupportAgent.handle → 原结构化回执分支/文字保护 → render_rag_citations → API`。三条保存的输出分别来自 ledger 请求 5、11、12；各自仅生成 text，无工具调用、无成功/失败工具回执；Trace.tool_calls 为空，handoff=not_required。before.json 中旧 Single 离线正文与历史 API 正文逐字相同，定位到 Single 后处理而非 API 引用渲染。

旧保护按“人工/真人/转接”等宽泛词逐句删除，并无条件附加交接状态。现在：存在请求/失败/工具调用时，原结构化回执分支完全保留；无回执且出现未受否定/条件限定的已完成交接承诺时，整体替换为既有安全交接说明；其他回答完整保留，不追加状态。有限的完成动作及就近限定词检查只用于文字保护，不是意图路由或事实验证器，不增加模型调用。详细生产差异见 minimal.diff。

不做句子拼接可避免残缺标题和悬空指代；代价是混合回答一旦包含被识别的错误成功承诺，整篇有用内容也被安全回退取代。现有实际创建、失败、权限拒绝路径继续以结构化回执为准，模拟成功仍不等于真人接单。

## 三条真实失败对照

- case_03：旧版删除“单笔超过 500 元需人工审核；恰好 500 元不因金额单独触发审批”，留下空金额审核标题。新版第 3 条退款审核说明及整篇正文逐字保留，未附加交接说明。
- case_08：旧版删除人工交接建议，留下无明确前文的“这个交接记录”问句。新版建议、问句和末尾订单/物流/退款说明完整保留，格式完整。
- repair_case10：旧版删除无法确认真人接手、模拟记录不代表接单/通知等否定说明，留下孤立 Markdown 标记。新版完整保留原始否定说明及段落；未调用交接工具、未创建新记录。

三条新记录数均 0 → 0。每次离线 replay 仅一次 Fake SDK，新增真实模型调用 0。完整三条正文、后处理前后及 API 对照见 before_after.md / comparison.json。模型原始正文及历史评分均未修改，保存正文并不证明其中所有历史事实、订单事实或建议均已核验。

## 红绿与回归

初始专项 22 项：18 failed / 4 passed（red.txt）；修复后补充代表性否定、条件和不同完成表达，最终新专项 26 项全绿。红测原样保留，未调整真实失败输入或已批准规则。

| 验证 | 命令 | 结果 |
|---|---|---|
| 交接专项 | uv run python -m pytest -q tests/test_handoff_reply.py tests/test_handoff.py tests/test_handoff_explicit_request.py | 90 passed |
| 关联回归 | 见 related.txt 对应本轮记录及下方清单 | 244 passed |
| 完整回归 | uv run python -m pytest -q | 577 passed / 3 skipped / 1 既有 AnyIO warning |
| 环境与差异 | uv lock --check；git diff --check | 通过；53 packages |

关联回归文件为 test_handoff_reply、test_handoff、test_handoff_explicit_request、test_support_production、test_auth_boundary、test_action_service、test_business_tools、test_policy_engine、test_rag_contract、test_answerability_boundary、test_runtime_skills_consistency。3 项跳过为既有 Memory live 及两项 Chroma HTTP opt-in；本轮未启动外部服务或真实 API。TestClient 调用实际 handler 并注入 Fake SDK/隔离业务状态，未启用生产 lifespan，属于离线证据，不能冒称新的真实 E2E。

安全覆盖包括无回执错误创建/转接/真人接单承诺仍回退、正确否定/条件/人工退款审核保留、合法模拟交接、权限拒绝，以及原身份、归属、幂等、订单、退款、知识和 Skills 回归。历史路由代码与测试、原 E2E 报告/模型 ledger、其他所有起始跟踪文件通过 SHA256 保护核对（validation.json），仅允许 Single 与 Workbench/progress 三个已有文件改变。

## 风险、文档及边界

有限文字保护不能理解全部自然语言：未覆盖的同义成功表达可能漏拦截，引用他人肯定话语、复杂或跨句否定/条件可能误回退；没有新增通用事实核验能力。本轮只证明固定真实失败文本及代表性边界的后处理行为，未验证新模型输出分布。repair_case10 的历史 ID/通知说明被保留，但未额外查询或认证历史记录；case_03 原文动态订单/金额也不在本轮核验范围。混合错误回答整体回退的内容损失仍存在。

真实 RAG 在原 E2E 未触发，继续留待单独授权验证；历史 5/3/2 结论保持。本轮真实调用/新费用/API 启动均 0；未改 RAG、Gold、Embedding、六正文、0.35 阈值、PolicyEngine、ActionService、Provider、权限或历史路由。不扩展评测框架。

现有 Workbench/progress 仅追加 REPLY fixed/verify 证据；旧 E2E preflight 条目属于历史准备记录，与后来实际已保存的 E2E 进展存在时间差，本轮不重写历史阶段或批准下一阶段。README/核心 Wiki 无架构与调用链责任漂移，无需修改。

独立开发练习：运行 `uv run python -m pytest -q tests/test_handoff_reply.py`，对照 comparison.json 中 raw_model_body 和 after_fix_API_answer；再检查无回执虚假成功与正确否定测试，解释为何文字保护不应删除退款人工审核，也不能认证真实接单。无模型或服务启动需要。

建议提交信息（未执行）：`fix: preserve supported replies and guard unconfirmed handoff claims`。
