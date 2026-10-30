# A04/N01 — ActionService 幂等复用与身份边界

2026-10-11，基准 HEAD `09efd3443d2e7b6e03fba7d13fe660c483b30583`，本轮修改未提交。outcome=`fixed`，状态=`verify`，待用户验收；A04/N05、N04 未实施。

执行期间出现外部提交 `e097ca871bcf07373b8bcf34dccd1e7b411c1657`（19:51:18 +08:00，Remove obsolete project documentation），为收尾时当前 HEAD。本助手未执行提交/推送。对两个HEAD比较，actions/api/agents/providers/policies/core/mcp/memory/tests/demo/uv.lock均无差异；pyproject仅纳入此前已有cache-dir配置。既有整理内容已由该提交纳入，最终未提交范围为本轮5个文件；最终专项与完整回归在该提交之后运行。原审查证据哈希保持一致。

## 基线与证据

开始时工作区已有 13 项修改、32 项删除和 26 个未跟踪文件，无暂存变更；其中包含 A00-lite、文件整理、历史报告迁移与配置/文档更新。本轮保留这些内容，业务代码仅修改 `actions/service.py`；测试仅修改 `tests/test_action_service.py`。

审查 N01 与 `audit_20261011_probe.py` 的 `action_probes()` 对应：同外部 key 的 10→20 元请求返回原 10 元动作；另一用户传入响应中的内部 key，取得原用户动作。观察 JSON 的 `IDEMPOTENCY` 记录 `backend_executions=1`，只说明该复现没有重复模拟执行，不能证明参数绑定正确或动作数据没有越权泄露。

原脚本/JSON只读，未重跑覆盖。SHA256：

- probe：`D29C48289C1A608695EDA966C8168A9C1E40057635AEF21B205B85D1DD47A462`
- observations：`67B5ACC58B189CB1A4AD26B5D4891025EBE32AF9531FB819461692EF80ACE1B1`

## 根因与执行顺序

原 `_request()` 在订单归属校验前按原始 supplied key 查 Store 并直接返回，内部 key 因此成为越权读取入口。普通外部 key 的 hash 包含 action/user/supplied key，但不绑定 order/amount，命中后也没有冲突检查。自动 key 直接使用 Decimal 字符串，`10.00` 与 `1E1` 会形成不同 key。

现在 `_request()` 顺序为：输入校验与 key 去空白 → 在原 Store 锁内识别内部 key 或 action/user scoped 外部 key → 检查命中动作的 user → Provider 检查本次订单归属并解析默认金额 → 查派生 key → `_reuse_action()` 比较 user/action/order/有效 Decimal amount → 匹配才返回原动作。未命中才沿原 Policy/HITL/Executor 流程创建或执行。命中动作后 Provider 拒绝或失败，不再保存一个新失败动作覆盖原 key 绑定。

`_reuse_action()` 对身份不匹配返回 `unauthorized`，对参数不匹配返回 `idempotency_conflict`；简单错误不包含旧 Action、action_id 或 execution_result。订单不存在/不属于调用者时优先返回 Provider 错误，不以冲突响应替代归属检查。request_id 不属于业务参数，可以在重试时变化。

`_idempotency_key()` 保留外部 key 的 action/user 作用域。`_canonical_amount()` 对自动 key 使用无指数、去无效尾零的 Decimal 字符串，不使用浮点数或 Decimal normalize 的上下文舍入。有效金额省略时仍取 Provider 订单总额；同 key 后续有效总额变化将发生冲突。内部 key 仍兼容同主体、同参数重试，但只是标识，不能代替归属检查。金额比较的请求指纹直接使用已有 PendingAction 字段，不新增 Store/模型字段。

原 RLock、ActionStore、PolicyEngine、审批/恢复状态机和 Executor 保持不变；API/Agent 工具签名没有变化。外层调用链仍为 SingleSupportAgent → Tool Contract → ActionService。

## 实际验证

环境：Windows，Python 3.12.3，uv canonical 环境，内存 fixture/模拟业务后端；没有调用真实支付或模型。

| 阶段 | 命令 | 实际结果 |
| --- | --- | --- |
| 修复前，新回归10例 | `uv run python -m pytest -q tests/test_action_service.py -k n01` | 7 failed、3 passed、17 deselected |
| 初次修复专项 | `uv run python -m pytest -q tests/test_action_service.py` | 4 failed、23 passed；四处失败均为测试误用不存在的 get_action，已修正为现有 get |
| 最终专项（新增14例） | `uv run python -m pytest -q tests/test_action_service.py` | 31 passed |
| 完整回归 | `uv run python -m pytest -q` | 164 passed、2 skipped、1既有AnyIO弃用警告 |
| 依赖与格式 | `uv lock --check`；`git diff --check` | 53 packages，通过；既有dockerignore换行提示 |

修复前7个失败分别为：派生金额规范化1例、外部/内部 key 异金额/异订单4例、跨用户内部 key 2例。并发重复请求、外部/内部 key 相同有效金额3例修复前已通过。首轮沙箱红测附加 pytest 缓存写权限警告，正常权限重跑仍为7 failed/3 passed，缓存警告消失。最终专项/全量也在正常权限运行。

回归覆盖同参数安全复用、10.00/1E1、外部和内部 key 参数冲突、跨用户传原用户订单/自己的订单均不得泄露、8线程同一Service同时起跑只执行一次、跨动作类型内部 key 冲突、待审批重试不绕过HITL、不存在订单重试不覆盖原绑定、省略金额匹配有效总额。完整回归包括现有审批/拒绝/恢复、Agent工具回执及Single生产接线测试。

2项跳过分别是 live Redis/Chroma Memory 与真实 Chroma HTTP RAG opt-in；没有执行真实模型HTTP E2E、部署或远端CI。这里的单次执行仅为同进程共享同一锁/Store的内存模拟证据。

## 限制与后续边界

- 内存 Store 重启即丢失，跨进程没有共享锁/事务/幂等唯一约束；多个独立Store不保证单次执行。真实外部动作的执行与落库也没有原子事务/恢复协议，不宣称 exactly-once。
- 默认 InMemoryActionStore 的共享实例带 RLock；自定义 Store 若不提供共享锁，多个Service实例各自锁不构成全局保护。本轮8线程验证仅为一个Service实例。
- 调用者仍来自Demo user_id；本轮只阻止不同user_id的内部 key复用，未解决N02可信身份/审批权限，也未修复N03 Provider错误泄露、N04退款读写、N05 Memory失败回执。
- 自动 key 的金额编码改变；当前是内存演示Store，无持久化迁移。已有返回内部 key 在归属/参数匹配下可重试；不承诺热升级旧Store中未传key的派生标识兼容。
- README及两份核心Wiki的架构/API描述未产生需修订漂移；精确新错误语义由本笔记记录。原审查与T09–T12历史报告保持不变。

独立练习：在 `test_n01_pending_retry_does_not_bypass_approval` 基础上，批准原动作后再次用同 key/600.00 重试，断言返回原 action_id、completed、reused=true，且 backend.calls 仍只有1条；再改成599断言冲突。运行该测试并解释为什么参数一致性与执行次数必须同时断言。
