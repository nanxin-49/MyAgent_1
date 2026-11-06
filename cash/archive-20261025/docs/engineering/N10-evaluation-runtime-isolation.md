# N10 — Evaluation Runtime 与业务运行时隔离

2026-10-12；A07/N10，outcome=`fixed`，status=`verify`，等待用户验收。
起始 HEAD `dcab02aa6382130826f37839e3c8d83640ccdac1`，工作区干净。保留 N01/N02/N03/N04/N05；本轮只处理 N10，未提交或推送。

## 根因与红测

审查 `project-audit-20261011.md:N10`、`audit_20261011_probe.py:evaluator_probe` 和 `audit-20261011-observations.json:EVAL_SHARED_STATE` 记录了模拟取消执行一次、正常业务订单变为 cancelled。这些历史文件与 T09–T12 报告只读，未重跑会覆盖观察 JSON 的审查脚本。

当前 lifespan 仍把 `_orchestrator` 直接传给 EndToEndEvaluator；/chat 与评测因此使用同一工具闭包、ActionService、ActionStore、读写 Backend、BusinessState 和 Trace。N04 的共享 state 修复保证同轮读写一致，却不能建立不同 Runtime 之间的隔离。

正式红测：`uv run python -m pytest -q tests/test_evaluation_runtime_isolation.py --tb=short -p no:cacheprovider`，**5 failed / 3 passed**。已认证测试 Principal 经 startup Evaluator 绑定的真实 SupportRuntime 选择取消工具，Action completed，正常订单由 paid 变 cancelled，安全断言失败。另有 Runtime 身份、连续运行和异常隔离断言失败。

必须区分：当前 N02 gate 会拒绝 HTTP Evaluator 原来生成的无 Principal 动作请求，因此 HTTP 用例在“评测内应该成功取消”处失败；这不是隔离成立。红测的共享写复现明确传入测试 Principal，没有放宽权限。准备测试时修正了工具名和超过审批阈值的 fixture；上述最终红测使用真实 `request_cancel_order`、129.90 元 paid 订单。

## 对象关系与实现

```text
之前：/chat ─┐
            ├→ SupportRuntime A → Tools A → ActionService/Store A → State A
      Eval ─┘

之后：/chat → SupportRuntime A → Tools A → ActionService/Store A → State A
      Eval run 1 → SupportRuntime B → Tools B → ActionService/Store B → State B
      Eval run 2 → SupportRuntime C → Tools C → ActionService/Store C → State C
```

- `api/main.py:lifespan` 不再给 API Evaluator 传聊天 Runtime；传入 EvaluationRuntimeFactory 与固定模拟 Principal。聊天构造、生产 Single 拓扑和授权路径不变。
- `evaluation/runtime.py:EvaluationRuntimeFactory` 在 startup 尚未接受聊天时，将配置的 JSON fixture 序列化为不可变字符串。每轮 json.loads 后重新构造 BusinessBackend、ActionBackend、ActionService（默认新 InMemoryActionStore）、SupportRuntime、SkillManager 和 MCPToolManager。它只构造模拟 Backend，不接收正常业务 Backend/Runtime，不在失败时退回聊天对象。
- 同轮 ActionBackend 显式接收 `business_backend.state`，沿用 N04 共享锁及退款 pending 语义。Provider 能看到本轮新增记录，Action completed 仍不表示资金到账。
- `evaluation/evaluator.py:run/_run/_evaluate_dialog_case` 在 async context 内持有本轮 Runtime，以局部参数传递，不将它写回共享 Evaluator 字段。连续、异常、重叠运行均不会复用业务状态。finally 关闭本轮 Support/RAG SDK，包括工具管理器构造失败时已经创建的 Support SDK。
- `/eval/run` 仍先执行 require_admin。内部 Principal 固定为 `evaluation:fixture:customer-1`，仅有 customer 角色；默认身份对应 fixture customer-1，显式其他 user_id 返回 422，不采用 HTTP admin 的客户/审核身份。该模拟身份仅供隔离 fixture，不是生产登录身份，也没有 reviewer/admin 权限。Evaluator 同时保留内部身份校验。

浅拷贝只复制表或顶层字典，订单记录、items 等嵌套对象仍可能共享引用；复制 ActionStore 无法隔离 Backend。这里通过 JSON 快照重新生成整个数据对象树，再在同一轮内显式共享唯一 state。不能给读写 Backend 各自 deepcopy，否则新增退款记录再次不可查询。

## 隔离范围

| 状态 | 本轮处理 |
| --- | --- |
| 订单、退款、库存等模拟业务表和锁 | 每轮新对象，与聊天及其他轮隔离 |
| ActionStore、幂等映射、执行计数、Policy 实例 | 每轮新对象，既有 ownership/Policy/HITL/idempotency gates 保留 |
| SupportRuntime Trace、请求统计、Agent | 每轮独立；评测 Trace 不进入正常 /trace，运行结束后不作为持久审计存储 |
| Memory / profile / Redis / 用户 Chroma | 评测不接入；多轮历史只在 Evaluator 本地列表中传递，不调用正常会话读写或画像调度 |
| RAG cache、Tool stats/breaker/schema、模型客户端 | 每轮独立，不复用正常工具管理器 |
| 知识 Chroma collection | 仅复用现有只读 search_handler/fallback；不构造会 seed/upsert 的 KnowledgeBase，不注册知识写工具；语料和外部查询负载并未物理隔离 |
| Intent diagnostic cache、Judge、报告 history/baseline | 仍属应用级 Evaluator；不用于聊天业务写。指标、baseline 语义留待后续任务 |

## 验证与验收

Windows、Python 3.12.3、uv 0.12.19；使用 tests fixture、固定 Policy clock 2026-09-25、Fake SDK/Judge/Memory/RAG/Monitor。执行真实 FastAPI lifespan、/chat、/eval/run、Evaluator、SupportRuntime、Tool、Provider、Policy 和 ActionService；没有收费模型、真实支付或 live Redis/Chroma 验收。

| 命令（pytest 另加 `-o cache_dir=data/test-cache/n10`） | 结果 |
| --- | --- |
| `uv run python -m pytest -q tests/test_evaluation_runtime_isolation.py` | 14 passed |
| `uv run python -m pytest -q tests/test_system_eval.py tests/test_topology_comparison.py tests/test_refund_read_write_consistency.py tests/test_action_service.py tests/test_auth_boundary.py tests/test_provider_safety.py tests/test_action_memory_consistency.py` | 142 passed：既有 Eval 22、N04 18、N01/N02/N03/N05 102 |
| `uv run python -m pytest -q` | 267 passed / 2 skipped，1 既有 AnyIO 弃用警告 |
| `uv lock --check` | 通过，53 packages |
| `git diff --check` | 通过 |

专项证明：/chat 查询前后 paid 不变、评测内部 cancelled；同轮退款写入→查询 pending→同 key 复用且只执行一次；连续两轮同 key 各执行一次、Action IDs 不继承；Judge 在写后抛异常、隔离构造失败均不污染聊天及下一轮；两个重叠评测独立；401/403、非 fixture 身份 422、ownership 拒绝、超额拒绝、600 元 HITL 待审批和模拟 customer 自批失败。生产 N04 的 HTTP 写后读测试仍通过。

两个 skip 为 opt-in live Redis/Chroma Memory 与真实 Chroma HTTP 测试。使用缓存 override 的测试只有既有 AnyIO 警告。随后额外执行原样 canonical `uv run python -m pytest -q`：267 passed / 2 skipped / 2 warnings（既有 AnyIO 与 cash/cache/pytest 写权限警告）；结果不受影响。测试缓存 override 指向忽略的 data 目录；未修改 pytest 配置。

## 限制与后续任务

业务、ActionStore、Trace 和锁只保证本进程对象隔离，不提供持久化、崩溃恢复、多 worker 一致性、跨进程事务或真实支付隔离。任何后续接入外部可写 Backend 必须先提供隔离测试租户/资源；不能把正常 Backend 塞入工厂或静默 fallback。共享只读知识查询仍会使用外部服务资源，语料可能被管理员并发更新，模型调用仍可收费。

评测沿用配置 fixture 的初始状态和真实 Policy 时间：默认旧日期/已有退款 fixture 可能导致拒绝，不为通过评测改退款规则。本轮未修数据集定义或指标计算。应用级 baseline 仍会自动保存本轮报告，缺少数据集版本校验，并发报告写入也未协调；需要独立后续任务。默认 baseline 路径不指向历史报告；不要将 EVAL_BASELINE_PATH 配置成冻结 T09–T12 文件。本轮这些历史文件没有变更。

README、核心《重点代码》同步评测调用链；Workbench/progress 仅新增 A07/N10=fixed/verify，不把 A07/EVIDENCE 当作完成。定位 Wiki 无架构定位变化，不需要改；其他 Wiki 不维护。

独立练习：运行专项测试；复制连续两轮用例，在第一轮修改订单的嵌套 items.quantity，断言聊天订单及第二轮仍为原始值。随后把工厂的 JSON 初始化临时替换成浅拷贝，观察新断言变红，恢复后转绿，并解释“跨 Runtime 分离、同 Runtime 读写共享”。只用本机模拟 fixture，不调用模型或外部服务。

建议提交：`fix: isolate evaluation runtime from chat business state`。
