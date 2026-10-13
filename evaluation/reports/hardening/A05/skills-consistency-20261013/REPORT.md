# A05-SKILLS-CONSISTENCY：运行时 Skills 口径修复

阶段 **fixed / verify，等待人工验收**。A05 保持 **doing / partial**；B1/B1-PREP 保持 **blocked**，API保持停止。DEFAULT-KB-PUBLICATION的数据层“建议通过”记录已保留，仍verify，等待用户明确确认后done；不把本轮Skills任务指令当作该阶段的最终确认。

起始HEAD：`483a2743f8aae4d5286a1202669ba6201af88823`，工作区干净。本轮只改三个运行时Skill、Skills README、专项测试和必要状态文档，无提交推送。

## 可执行加载与注入链

`api/main.py:104` → SkillManager(root_dir, max_prompt_chars).load → `SupportRuntime.make_agent` (`agents/support_agent.py:128`) → SingleSupportAgent + AllRoleSkills → `BaseAgent._build_system_prompt` (`agents/agent_orchestrator.py:455`) → SDK messages.create 的 system 字段（同文件:271/283）。

- api启动读取ECHOMIND_SKILLS_DIR，默认当前仓库skills；ECHOMIND_SKILLS_MAX_PROMPT_CHARS默认5000。本轮.env及执行进程这两个配置均未设置，按默认路径/预算验证，没有启动API。
- SkillManager._discover_files（core/skill_loader.py:214）优先递归SKILL.md，再加载其他.md/.txt/.json，排除README。实际发现只有billing_support、general_customer_service、technical_support三项，enabled=true，加载errors=[]；未发现其他可加载的商城Skill。
- 匹配是关键词大小写不敏感的子串，不是分类器路由。AllRoleSkills.prompt_for（agents/support_agent.py:26）传agent_type=None，故原agents:billing/general/technical标签不会阻止当前Single注入。直接manager.prompt_for('退款','support')为空，但真实SupportRuntime对同一请求注入账单Skill；测试及前后SDK捕获证明此路径。
- SDK前捕获七类请求：退款、账单未接入能力、订单会员、401、混合三类、明确人工、无关键词。runtime_before.json与runtime_after.json保存实际system字符串、加载路径、关键词匹配、SDK请求数量和空role packet，不是凭文本搜索假定可达。
- 明确“请转人工客服”由SingleSupportAgent.handle:50的确定性门直接创建模拟记录，Fake SDK调用0；即使Skill匹配，也不表示该次请求发生模型注入。“xyzq”调用Fake SDK但不注入动态Skill。
- Single架构、get_tools注册表、模型轮次、权限和工具调用代码均未改。兼容agents标签和关键词保留，不恢复Intent/Multi-Agent分流。

## 原冲突与最小修订

原始字节归档source_before/*.bin（加载器不支持该格式，且不在skills目录）；逐处完整unified diff见 **skills_diff.patch**，修订文件直接保留原名称、章节及兼容metadata。不把17条测试或14个红测失败当作14个独立业务缺陷。

| 原指令/漂移 | 修订后的指导 | 权威代码或审批资产 |
|---|---|---|
| billing：退款金额按“实际支付金额” | order.total_amount；不存在实付字段，省略申请金额用总额，不能称总额为已核实实付 | providers/models.py:61/66；actions/service.py:217；policies/engine.py:180 |
| billing：所有部分退款/虚拟商品/活动价/合同均须人工 | 不额外增加规则；部分退款不自动审核，大于0且不超过总额；超过500需审核，500不因金额单独触发 | policies/engine.py:181/189/197；真实Policy矩阵验证 |
| 未说明审核人权限/独立性/执行复核 | reviewer角色、review_customers范围、非该客户/非申请人；用户“同意”和approved参数不构成授权，执行前复核 | actions/service.py:91-110、262-285；tests/test_auth_boundary.py及test_action_service.py |
| billing：原路退款、等待支付渠道、账单成功 | 仅模拟退款申请；动作completed不等于退款完成/资金到账；无真实资金时效或渠道承诺 | 已批准退款正文；actions/backend.py、actions/service.py；既有退款读写一致性回归 |
| billing：开票税号流程、订阅取消、优惠补差/券退回 | 明确未接入，删除虚构流程及多余敏感字段收集；不能用取消订单当取消订阅 | 实际工具注册表agents/tools.py；六篇已批准默认知识正文 |
| general：识别/转独立专属Agent | 当前SingleSupportAgent按工具处理，静态知识/Provider/ActionService职责分开；无依据不补全 | agents/support_agent.py:22/30/128；api/main.py:104-117 |
| general/technical：笼统人工/二线升级 | request_handoff受三个理由码限制，成功回执及编号仅证明模拟记录，不等于接单/通知/查件或动作审批 | core/handoff.py:37/53/69；SingleSupportAgent:50/85 |
| technical：建议已存在密码重置/重授权、套餐开通 | 明确密码/解锁/两步验证/真实日志/清缓存/支付诊断未实现；401/403/500只是排查方向 | 当前helper工具范围、已批准账户与技术正文 |
| general：会员、费用、资格可按常规流程处理 | 未实现会员积分、运费报价/免邮、发票订阅等，不补数字或未验证入口；物流日期可空且是估计 | providers/models.py:78/85；批准的配送、会员、账户正文 |
| 普通Skill文档声称对应领域Agent、中文逗号均可、宽泛升级 | 说明AllRoleSkills实际行为；实际解析器仅按英文逗号拆分；reload/查询需可信admin，本轮不可调用 | core/skill_loader.py:133/214/_as_list；api/main.py:361/369 |

合法同客户同键同参数重试仍返回既有动作当前结果、不另行执行或绕过审批；同键异参不能复用（actions/service.py:254）。没有把新退款重复记录限制错误解释为所有幂等重试禁止。人民币演示定位保留，同时明确程序未实现币种准入/换算校验；没有虚构币种白名单，也没有修改PolicyEngine。

## 与六篇审批知识正文的逐项核对

批准资产完整SHA256仍为 `17e3c606365c203589919321b166e942e6aab569d539ce631f447a5439cd018d`，文件及Metadata完全不改。
- 退款：总额、7×24h窗口、金额/审批、记录限制、合法重试、模拟资金与币种边界一致；具体状态/资格依赖代码结果，不靠提示词代替。
- 订单：本人可访问记录、工具必要参数、未找到记录不确认他人是否存在，总额不当实付，订单/物流状态分开。
- 配送：可选预计日期不承诺，运费/免邮/加急/查件等不能称已实现；交接不等于查件或改地址。
- 账户：密码重置/解锁/两步验证/自动锁定均不能声称已实现。
- 技术：状态码不证明根因，日志/缓存/支付诊断工具边界一致。
- 会员：积分、等级、余额、资格、折扣等无接入依据不得补数值。
本轮受审范围未再发现上述原业务承诺冲突。这是指令内容和源码/批准正文的一致性，不能推导所有业务问题均可回答或模型一定遵循。

## 注入预算

单Skill正文：billing=1868、general=1253、technical=1484字符；含名称/说明的完整块分别1930/1312/1545，加块分隔共 **4791 < 5000**；各正文均<3200。混合请求实际SDK system中三个块及金额、reviewer、未实现能力等关键边界完整出现，无尾部预算截断。

首轮修订后的预算测试1 failed/16 passed：内容合计5797，虽关键前置边界可见，仍存在尾部截断。仅压缩重复回复格式、示例和未接入流程，保持预算及加载策略不变；再测17 passed。自定义更小预算或更多外部Skill可能截断，后续配置变更须重验；本轮不改配置。

## 测试与证据

| 检查 | 结果及证据 |
|---|---|
| 先红测 | 14 failed / 3 passed，red.txt；原错误指令可在Fake SDK system内直接观察 |
| 新专项 | 17 passed；实际加载/匹配/SDK注入、无匹配、明确交接绕过模型、真实Policy金额矩阵 |
| 关联回归 | 150 passed / 1既有AnyIO警告，targeted.txt；Support、handoff、Policy、ActionService（含N01）、Auth、Provider错误 |
| 完整回归 | **498 passed / 3 skipped / 1既有AnyIO警告，8.72s**，full_regression.txt |
| live跳过 | Memory Redis/Chroma及两项HTTP RAG opt-in，明确设为0；不是服务故障，也未偷偷用Fake替代live验收 |
| uv lock --check | 53 packages，未新增依赖或下载 |
| git diff --check | 通过 |
| 文件保护 | preservation_validation.json：仅七份授权Skill/文档tracked文件改变，其他**497**份tracked字节hash不变 |
| 资源/API | 完整回归前可用物理内存1.6668GiB、结束记录约1.5554GiB；仅轻量Fake/unit pytest，不是B1资源重试。API容器false/exited，无8000/8080监听 |

完整命令：
```powershell
$env:CARTCARE_RUN_CHROMA_HTTP_TEST='0'
$env:CARTCARE_TEST_LIVE_MEMORY='0'
uv run python -m pytest -q tests/test_runtime_skills_consistency.py tests/test_support_production.py tests/test_handoff.py tests/test_policy_engine.py tests/test_action_service.py tests/test_auth_boundary.py tests/test_provider_safety.py
uv run python -m pytest -q
uv lock --check
git diff --check
```
早期一次关联命令使用不存在的test_action_idempotency_binding.py导致未收集测试；正确N01用例实际位于test_action_service.py，随后150关联和498全量通过。早期补丁/允许清单错误经实际diff及离线保护检查确认后修正，不将失败命令当作有效回归。

静态代码审查和真实SkillManager/SupportRuntime使用Fake SDK验证，关联HTTP路径用Fake/TestClient，不监听服务端口。**真实模型调用0，真实/chat E2E 0，Chroma/Redis live调用0**；没有模型回答质量、真实资金操作或真实客服证据。没有代码规则、Agent框架、知识资产、默认集合、RAG阈值、Gold/B0/B1或历史报告变更。

## 剩余风险与下一阶段

- Fake SDK只捕获system参数，固定回复不会验证真实模型理解、工具选择、话术遵循或事实充分性。权限/审批和动作变更仍由原确定性代码保护。
- AllRoleSkills继续忽略agents标签；子串匹配可能因“500元”触发技术Skill，或因单独“积分/物流”没有现有关键词而不注入对应Skill。没有改匹配器、关键词或分类器；关键边界已在已测混合请求中完整注入。
- Single继承General基础system_prompt中的“建议转接专业客服”和较宽的profile升级条件仍存在；当前Single的后置request_handoff限制、确定性门与修订Skill明确模拟边界，未恢复真实独立领域Agent。真实模型是否误解须后续E2E验证，本轮不改框架。
- Skills的规则说明不能冒充RAG引用；无usable证据时是否仍臆造回答、订单总额是否被说成实付、动作completed是否被说成到账、预计日期是否被说成保证，留给独立Answerability用例。
- 既有退款新检索用例0.339462在0.35下low_confidence仍是已知限制，未改阈值/正文或借此开启B1。
- 外部Skill目录、热加载内容可信度及生产认证不在本轮修复范围；当前默认3文件通过，不代表任意运营自定义文件安全。
- 没有实际reload或API重启；后续受限内部E2E先确认代码及Skills版本，不能直接重启10月2日旧API镜像。需单独授权真实模型/网络资源，遵守现有Owner/Reviewer/工具边界。

建议先人工验收本轮Skills差异和注入证据，再单独定义并验证Answerability，最后在新代码与明确资源授权下开展真实/chat内部E2E。DEFAULT-KB-PUBLICATION仍等待用户最终数据层确认；A05不标done，B1不启动。

文档：Skills README修正实际加载与能力边界，README仅更新当前验证状态，既有Workbench/progress增加本阶段；两份核心Wiki当前Single路径描述仍准确，未改其他Wiki或历史文档。

独立练习：不启动API，运行新增专项测试；查看runtime_after.json中“退款”的SDK system与“请转人工客服”的sdk_calls=0，再用真实Policy矩阵区分100/500/500.01；不得将Fake通过说成真实模型验收。
建议提交消息（仅建议，未提交）：`Align runtime support Skills with deterministic demo business boundaries`。
