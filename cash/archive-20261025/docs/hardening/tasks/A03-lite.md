# A03-lite｜P0：Provider 安全错误 + 最小 Principal 信任边界

> **执行规则**：`N03`、`N02-auth`、`N02-ops` **每轮只选一个**。报告已实测风险；原 V2 中“管理/Trace 接口可暂不处理”的约束**已不适用**。但仍不做 OAuth/OIDC/JWT 账号大工程。

## A03-lite/N03（P0）——Provider 错误路径泄露数据

**依据**：N03 / `PROVIDER_ERROR_LEAK`；`providers/implementations.py:73`、`providers/errors.py:29`、`agents/tools.py:268`。审查复现：**他人订单的畸形字段**先出现在 validation 错误详情，ownership 在之后执行；错误还可能流入 LLM。

**失败回归**：未授权用户读取“有缺字段/合成敏感标记”的订单时，HTTP / Tool / LLM 可见错误**均不得包含原始字段与标记**；合法 owner 的畸形对象也要返回结构化、安全的校验错误；正常合法 owner 查询继续通过。

**最小修复**：先对订单做可确定的 ownership 判定或先使用与具体字段无关的安全错误；对 ProviderError/Tool result 建立明确的外部错误码与脱敏消息。保留必要的内部诊断信息但日志不得泄露敏感原文。避免由错误码泄露“他人订单存在”的信息。

**DoD**：拒绝路径与成功路径都验证；原始输入不会出现在响应、Trace 或交给模型的 tool_result；已有 ownership 不退化。

## A03-lite/N02-auth（P0）——不信任客户端身份 + 独立审批角色

**依据**：N02 / `APPROVAL_CLIENT_IDENTITY`；`api/main.py:252/436`。审查观察：只填写动作所有者 `user_id` 即可批准待审核的**模拟**退款。

**最小链路**：`HTTP → 受控演示 AuthAdapter → Principal(subject_id, customer_id, roles) → /chat/ActionService/Provider → Policy`。使用服务端受控凭据映射或 FastAPI 依赖覆盖进行测试；不能信任任意 body `user_id`、`X-User-Id` 或客户端 `role`；未认证默认拒绝。`customer` 发起 / 查询本人的动作，`reviewer` 可依据明确规则审批；actor 与 action owner 分开记载。兼容旧前端时传入 `user_id` 只能匹配 Principal，不得覆盖。

**失败回归**：未认证；body 伪造身份；伪造 reviewer role；用户 A 查询/执行 B 的 Action；customer 自我审批；真正 reviewer 合法审批；合法本地 Demo 请求。明确 401/403/不泄漏资源信息的行为。

**DoD**：服务层授权不可只靠 HTTP 接口（避免内部 Tool 直接绕过）；不影响合法 ownership；保留演示 adapter 的限制说明。

## A03-lite/N02-ops（P0）——Trace / 管理路由访问控制

**依据**：N02 / `TRACE_NO_AUTH`；`api/main.py:549/562/629/727`。当前无凭据 `recent trace` 返回 200，知识添加/上传、Skills reload、Eval 等没有独立认证依赖。

**最小范围**：沿用上节 AuthAdapter，给 `/trace/*` 和管理/变更路由加入服务端受控 `operator`/`admin` 权限（角色名称可复用现有实现，不能由请求体自报）；默认拒绝。`/eval/run` **还必须单独执行** `A07/N10` 的业务状态隔离，认证不代表隔离。

**测试**：未认证及 customer 查看 Trace 被拒；无权写知识或触发 Eval 被拒；受控操作员允许的范围有明确定义；敏感 trace 参数经过必要脱敏。本地 Demo 仍可通过受控配置使用。

**DoD**：上述外露端点有明确权限；但**不因此宣称可公网部署**：Redis/Chroma/Nginx 端口、资源边界和生产身份验证器另需专门安全验收。

## 文档

仅一份短的 `docs/engineering/ADR-auth-and-provider-safety.md`：受信 Principal、错误脱敏与公开部署限制；不扩成登录教程。更新 Workbench 的 A03-lite 分项结论。
