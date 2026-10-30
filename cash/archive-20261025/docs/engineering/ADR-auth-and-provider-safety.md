# 可信身份、审批授权与 Provider 错误边界

2026-10-11，HEAD `b00344be38e83af5d1f13d81b8d0f2f4a628a950`；本轮工作区起始干净，N01已在HEAD中。outcome=`fixed`，状态=`verify`，待用户验收。只实施N03，N02-auth/N02-ops未实施。

## 证据与决策

审查报告N03、`audit_20261011_probe.py:provider_probe()`及观察JSON的`PROVIDER_ERROR_LEAK`一致：给订单移除必填字段并加入合成敏感标记，另一用户查询时先触发Pydantic校验，原始输入进入`exc.errors()`，经`ProviderError.to_dict()`进入工具与模型。历史脚本断言缺陷成立，不能作为修复成功测试，本轮未运行或覆盖原脚本/JSON。

决策：沿用现有Provider、Tool Contract、SingleSupportAgent和ActionService，不引入身份框架。先对有归属的原始Mapping检查`customer_id`；缺失、不可判定或不匹配均拒绝，再校验模型。保留模型校验后的二次归属检查。该共享路径覆盖Order、Shipment、Refund Provider；Product/Inventory保持模型校验。

`_BaseProvider._read()`的校验诊断只保留`validation_error_count`和去重后的`validation_error_types`，不保存input/msg/ctx/loc，不打印原始记录。校验及依赖异常使用`from None`抑制常规traceback中的原异常内容。底层异常仍可能存在于Python异常上下文中；不得绕过该安全边界直接记录`__context__`、backend raw或完整locals。本轮不新增日志输出。

`ProviderError.to_dict()`为公开投影：消息来自固定错误码映射，未知码降级为provider_error，details始终为空。保留由调用请求产生的resource_id及Provider固定resource_type；这些字段是查询定位信息，不是原始后端记录。内部`.code`仍为typed code，供确定性Action/Policy逻辑使用。

读工具对UnauthorizedError公开映射为not_found，与不存在记录共用安全消息；合法owner的畸形记录公开返回invalid_data及固定消息。此决策隐藏错误码/message层面的存在性差异，不承诺网络时序不可区分。ActionService内部授权错误及接口契约未变，N02可信身份/审批权限不在本轮范围。

## 路径与兼容

前：Provider model_validate → 带原始输入的校验错误 → ownership（未执行）→ Tool error.to_dict → execute_tool/Trace/model tool_result → HTTP。

后：原始归属判定 → model_validate → 安全诊断/typed error → 公开投影 → 原有Tool/Trace/model/HTTP路径。`agents/tools.py`已有统一error.to_dict调用，不需要另建转换或修改Agent/API。正常合法owner查询回归保留，动作审批/幂等测试继续通过。

公开读工具错误码从unauthorized变为not_found，原test_business_tools对应断言同步；内部Provider UnauthorizedError及N01 ActionService unauthorized断言保持。README/核心Wiki没有逐错误码描述，无新增架构漂移，本轮无需修改。未来N02设计时再补Principal章节，当前Demo user_id不能视为认证。

## 验证

环境：Windows、Python3.12.3、uv canonical依赖，Fake SDK/Memory及内存fixture backend。测试仅含合成敏感标记，无真实客户数据。

| 阶段 | 命令 | 结果 |
| --- | --- | --- |
| 修复前安全红测6例 | `uv run python -m pytest -q tests/test_provider_safety.py` | 6 failed，1既有AnyIO警告 |
| 最终相关回归 | `uv run python -m pytest -q tests/test_provider_safety.py tests/test_business_providers.py tests/test_business_tools.py tests/test_action_service.py` | 58 passed，1既有AnyIO警告 |
| 全量 | `uv run python -m pytest -q` | 176 passed、2 skipped、1既有AnyIO警告 |
| 依赖/格式 | `uv lock --check`；`git diff --check` | 53 packages，通过 |

新增12例：合法/非法owner的畸形订单错误不带原始输入，ProviderError任意message/details不直接公开，foreign/missing读错误统一，Fake SingleSupportAgent真实生产接线中将tool_result原样回显至/chat并检查HTTP、Trace及模型第二次输入；另覆盖Order/Shipment/Refund的缺失归属和异主体。traceback/caplog不含标记。既有成功查询及31个ActionService测试通过。

2项跳过为live Redis/Chroma Memory和真实Chroma HTTP RAG opt-in；未执行真实模型HTTP E2E、支付、容器、部署或远端CI。不把Fake回显测试称为真实模型行为保证。

原证据SHA256保持：probe=`D29C48289C1A608695EDA966C8168A9C1E40057635AEF21B205B85D1DD47A462`，observations=`67B5ACC58B189CB1A4AD26B5D4891025EBE32AF9531FB819461692EF80ACE1B1`。历史T09–T12只读。

## 未解决边界与独立练习

N02可信Principal、独立reviewer及Trace/管理权限仍未实施，不能因此宣称公网安全。本轮不扩展到N04/N05或其他风险，也不改变N01跨进程/重启一致性限制。

独立练习：新增一例合法owner订单`total_amount`含合成敏感字符串的测试，经get_order工具断言invalid_data、details为空且字符串不在结果中；再检查Provider内部诊断仅含decimal校验类型和数量。运行该测试并说明内部诊断为何不能直接作为模型tool_result。

## A03-lite/N02：可信身份与审批授权（2026-10-11）

本轮HEAD=`cfa7d0781275bc164e21ee909d0f9a1cfbabdad7`，起始工作区干净，N01/N03已在HEAD。用户明确要求同时处理N02-auth与N02-ops，范围以本轮指令为准。outcome=`fixed`；状态=`verify`。本轮未提交、推送，未改N04等后续问题。前述N03章节为历史证据，N02“未实施”仅描述该轮状态。

审查N02的`TRACE_NO_AUTH`、`APPROVAL_CLIENT_IDENTITY`观察确认无凭据读取Trace及仅填写owner user_id就批准600元模拟退款。原脚本/观察JSON保持只读，SHA256未变。根因：Provider只回答“当前传入customer_id是否拥有记录”，不能证明这个customer_id属于HTTP调用者；approve把owner身份当审批权限，管理/Trace路由没有认证依赖。

### 信任与执行链

`HTTP → get_auth_adapter → get_principal → Principal → API role/identity gate → Request.principal/customer_id → business tool gate → Provider ownership / ActionService gate → Policy/HITL/Executor`。

Principal是服务端构造的不可变dataclass，包含subject_id、customer_id、roles和review_customers；不接受body、X-User-Id或X-Roles生成身份。get_auth_adapter可用FastAPI依赖覆盖，或由服务端显式安装app.state.auth_adapter。未安装真实验证器时使用DenyAuthAdapter；验证器异常/无有效Principal均401，角色/身份冲突403。

`/chat`先解析customer权限及身份，再读取Memory；user_id可省略，存在时必须等于Principal.customer_id。Provider仍保持现有接口，业务read Tool在调用它之前要求Principal匹配user_id；敏感Tool将Principal显式交给ActionService。ActionService公开request_refund/request_cancel/get/reject/resume拒绝无Principal或客户权限不匹配，不能只通过直接调用Tool/Service绕过HTTP gate。私有内部函数及手工构造Principal仅属于受信进程代码，不能把这类内部调用当成外部认证。

approve在原Store锁内先检查Principal/reviewer，再查Stored Action，核对可选owner声明、review_customers范围及独立主体，随后按原状态机与Policy二次校验执行。禁止reviewer.customer_id等于owner，也禁止reviewer.subject_id等于requested_by，即使同主体另持reviewer凭据也不能自审。admin不隐式获得reviewer权限。新动作记录requested_by，批准时记录reviewed_by，action.user_id始终保持owner。重复批准保留原reviewed_by与原执行结果，不重复执行。customer可reject自己的待审核动作作为撤回；本轮reviewer仅批准，不新增reviewer拒绝流程。未来遗留Store若requested_by缺失，主体自审检查缺少该字段证据；当前演示为内存Store，不承诺持久化/热迁移认证兼容。

GET Action及resume/reject的跨客户结果在HTTP公开为404，伪造body/query user_id与Principal冲突403；Service内部仍保留N01 typed unauthorized语义。未认证请求均401，无权限审批不会写入状态或审核字段。

### 接口权限与Demo兼容

- customer：/chat、自己Action的get/reject/resume；不能approve或查看Trace。
- reviewer：仅approve其review_customers内、非本人发起的动作；审批保留owner与独立reviewer actor。
- admin：Trace单条/列表、Skills查询/reload、Knowledge添加/上传/统计、/eval/run、/monitor、/metrics及诊断/search。admin无默认客户身份或审核权限。
- 公开：静态/demo与资源、API schema文档、/health的既有运行状态；这些不是身份入口。本轮不宣称完全隐藏服务指纹或资源时序。

DemoAuthAdapter仅在CARTCARE_AUTH_MODE=demo、APP_ENV=development、API_HOST回环、请求peer与Host为回环时验证服务端CARTCARE_DEMO_CREDENTIALS。该JSON的key为自行生成至少32字符Bearer token，value为subject_id/customer_id/roles/review_customers。没有默认token、匿名回退或客户端角色映射。错误配置/未知token拒绝。不要将该模式接入公网或公共反向代理；正确peer识别还依赖部署层，不能用本Demo检查替代代理边界审查。

Demo页面增加三个password输入，customer发/chat、get/reject/resume，reviewer发approve，admin查询Trace。只在页面字段中保存，不进入localStorage/URL、Trace或模型上下文。场景body user_id保留为兼容断言，不再决定身份；更换客户场景须使用对应客户凭据。CLI从CARTCARE_CLI_TOKEN经过同一Adapter生成Principal后再初始化业务组件，不能靠cli_user绕过认证。原HTTP capture/baseline调用者若未提供Bearer会401，历史报告不回写，也不自动启动真实模型实验。

测试中的HTTP依赖覆盖只由显式authenticated_http fixture启用，凭据固定映射测试Principal，不从body推断身份；Trace回归使用显式customer+admin测试主体，approve另用reviewer。N02测试独立使用替换AuthAdapter或真实DemoAuthAdapter，不使用该旧测试覆盖。原N01直接Service回归显式传customer/reviewer；独立组件replay和topology实验runner针对自身新建的内存fixture显式生成合成Principal，仅适配新工具契约，不改变在线/evaluator身份信任、不重跑或回写历史实验。

### 实际结果与限制

环境：Windows、Python3.12.3、uv canonical依赖，内存fixture、Fake SDK/Memory；无真实支付。

| 检查 | 命令 | 实际结果 |
| --- | --- | --- |
| 修复前红测 | `uv run python -m pytest -q tests/test_auth_boundary.py` | 11 failed；包括匿名审批已执行的观察 |
| N02专项（最终37例） | 同上 | 37 passed |
| N02+N01+N03 | `uv run python -m pytest -q tests/test_auth_boundary.py tests/test_action_service.py tests/test_provider_safety.py` | 80 passed |
| 完整回归 | `uv run python -m pytest -q` | 213 passed、2 skipped、1既有AnyIO弃用警告 |
| Demo JS | `node --test tests/demo_ui.test.cjs` | 12 passed，包括独立凭据header验证 |
| 配置/格式 | `uv lock --check`；`git diff --check` | 53 packages，通过 |

初版Demo测试5例因锁定Starlette的TestClient不支持client参数失败，改用httpx.ASGITransport真实ASGI peer，未放宽回环检查。初版全量2 failed/207 passed是Memory HTTP测试缺依赖覆盖、组件replay缺fixture Principal，已显式适配；未关闭认证。编译检查沙箱pycache写权限失败，正常权限compileall通过。

最终覆盖匿名访问已注册受保护路由、body身份冲突、无body身份派生、伪造role、customer/范围外reviewer/自审/同主体reviewer/admin审批拒绝、独立reviewer审核及重复审批、内部Tool/Service绕过拒绝、跨客户Action访问、admin受控访问及Demo production/public-bind/remote-peer/default-disabled拒绝。N01 31例与N03 12例均通过。

跳过live Redis/Chroma Memory和真实Chroma HTTP RAG两项opt-in；未跑收费模型、真实服务E2E、支付、容器、部署和远端CI。生产验证器、凭据过期/撤销/轮换、TLS/反向代理、网络暴露、限流与更细粒度组织/审核范围治理仍需独立设计。本地Demo认证不等于生产认证。

`/eval/run`新增admin gate不代表N10共享业务状态已隔离，本轮没有实施A07/N10；ActionStore仍有N01记录的跨进程/重启边界。历史T01–T12及原审查未改。

独立练习：给tests/test_auth_boundary.py添加reviewer凭据仅授权customer-2、却审批customer-1待审核退款的用例；断言403、Action仍awaiting_approval、reviewed_by为空、backend.calls为空。再用合法reviewer审批两次，检查owner、requested_by、reviewed_by与单次执行。
