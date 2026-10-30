# H1-1 独立练习与知识说明

> 日期：2026-10-25  
> 范围：H0-1 CI 修复、H1-1 三轮真实 `/chat` E2E、确定性 gate。  
> 原则：先自己动手，再看参考答案；所有结论都要能回到代码或原始证据。

## 一、先掌握的几个概念

### 1. 证据层级不能混用

| 层级 | 含义 | 本项目例子 |
| --- | --- | --- |
| unit / Fake SDK | 进程内、无真实模型/服务 | `tests/test_action_service.py`、`gate_checks.py` |
| live Redis / Chroma | 真实外部存储，但不调用模型 | Memory 集成测试、Chroma 检索直查 |
| 真实模型 | 真实调用 `deepseek-flash` | 三轮 E2E 的 `/chat` |
| 真实 HTTP E2E | 真实 uvicorn + HTTP + 模型 + 隔离服务 | `evaluation/reports/H1-1/*/REPORT.md` |

写结论时必须注明层级。“Fake 通过”不能写成“真实模型通过”。

### 2. RAG 与动态业务数据

- 政策、FAQ、流程等相对稳定的知识走 `search_knowledge_base`（Chroma HTTP）。
- 订单、物流、库存、退款状态等动态事实必须走 Provider 工具，不能从检索文本或历史回复推断。
- `usable` 只表示检索片段通过分数、来源、引用和生命周期校验，不证明回答逐句正确。
- 当前 embedding 是 **字符 bigram 词法基线**，阈值 `1 - Chroma distance >= 0.35`；它不是语义模型。

### 3. LLM 与确定性规则的边界

- Agent 负责：理解请求、选工具、收集参数、在 3 轮工具循环内规划、生成回答。
- 确定性代码负责：归属、状态、7×24 窗口、金额上限、重复退款、审批、幂等、执行。
- 本项目当前规则：**≤500 元自动通过；>500 元需要独立 reviewer 审批**。Agent 可以判断条件并决定是否提交，但不能绕过 Policy/HITL。

### 4. 退款状态不是“到账”

```
Agent request_refund
 → ActionService → Provider 事实 → PolicyEngine
 → allow / deny / require_approval
 → reviewer 审批（需要时）
 → 模拟 Executor 执行
 → Action completed
 → 订单 refund_pending
 → 退款记录 pending
```

`completed` 只表示模拟动作完成；`pending` 表示退款申请待处理；两者都不代表资金到账。

### 5. 幂等与归属

- 同键同参重复：复用原 action，不重复执行。
- 同键异参：`idempotency_conflict`，不复用、不执行。
- 跨用户同键：各自作用域，不能取到别人的结果。
- 越权查询：Provider 返回不可访问记录；回答不能泄露订单是否存在、状态、金额或运单号。

### 6. 人工交接不是真人接手

`request_handoff` 只创建进程内模拟记录，记录状态固定为 `created`，没有接单/关闭接口。追问时不能声称真人已接手，也不能重复建单。

## 二、独立练习（含参考答案）

### 练习 1：确认 `setup-uv@v10` 为什么不可用

**目标**：不依赖 Claude，自己验证 CI 失败原因。

**步骤**：

```bash
git ls-remote https://github.com/astral-sh/setup-uv refs/tags/v10
git ls-remote https://github.com/astral-sh/setup-uv refs/tags/v10.3.2
git log --oneline -3
```

**参考答案**：第一条命令没有输出，说明仓库没有 `v10` 这个 Git ref；第二条返回 `v10.3.2` 的 commit。GitHub Actions 的 `uses: owner/repo@ref` 要求 ref 真实存在，不能按语义版本自动匹配 `v10`，所以 `Set up job` 失败。修复是把 workflow 固定到 `v10.3.2`（或 commit SHA），然后开 PR 让远端跑一次。

**证据**：`.github/workflows/tests.yml`、`docs/reports/H0-1.md`。

### 练习 2：LF / CRLF 与冻结 hash

**目标**：理解为什么“内容看起来一样”仍可能让冻结校验失败。

**步骤**：

```bash
# 工作区文件（Windows 可能是 CRLF）
sha256sum some_frozen_file.json
# Git 中的规范字节（通常是 LF）
git show HEAD:some_frozen_file.json | sha256sum
```

**参考答案**：Git 索引通常存 LF，工作区在 Windows 可能是 CRLF；两者字节不同，SHA256 就不同。冻结校验如果记录的是 Git blob 的 hash，就不能用工作区文件直接比较，也不能在未声明时自动换行归一化。应统一换行策略（`.gitattributes`）或明确记录“规范字节”的来源，并在校验时使用同一来源。`H0-1` 的 CI 修复不涉及这个，但它是本项目所有 frozen evidence 的通用规则。

### 练习 3：画出 `/chat` 主链路并指出安全门

**目标**：能在一分钟内讲清楚请求怎么走。

**参考答案**：

```
POST /chat
 → core/auth.py: Principal（默认拒绝；Demo 仅 development + loopback）
 → MemoryManager.get_context（Redis 工作记忆）
 → SupportRuntime.run → SingleSupportAgent.handle
 → BaseAgent 工具循环（最多 3 轮）
     ├─ search_knowledge_base → 外部 Chroma HTTP
     ├─ Provider 只读工具（订单/物流/库存/退款）
     └─ request_refund / request_cancel_order
          → ActionService → PolicyEngine → reviewer（需要时）→ 模拟 Executor
 → Memory 写回 + Trace
```

安全门：Principal/归属、Policy、HITL、幂等、危险工具 schema、Trace 授权。模型不能直接保证退款成功。

### 练习 4：为什么工具选对了，仍然没有 citation

**目标**：区分“工具选择”和“检索质量”。

**步骤**：

```python
from mcp.knowledge_base import KnowledgeBase
kb = KnowledgeBase(chroma_host='127.0.0.1', chroma_port=8001)
for q in ['退款政策', '退款需要满足什么条件？', '退款政策是什么？']:
    print(q, [(round(h['score'], 4), h['retrieval_status']) for h in kb.search(q, 3)])
```

**参考答案**（本机实测）：

| query | top1 score | 状态 |
| --- | ---: | --- |
| `退款政策` | 0.5621 | usable |
| `退款需要满足什么条件？` | 0.1683 | low_confidence |
| `退款政策是什么？` | 0.4122 | usable |

模型在第一批 S1 确实调用了 `search_knowledge_base`，但查询词被拉长后，字符 bigram 相似度低于 0.35，返回 `low_confidence`，所以没有 citation。结论：**工具选择正确 ≠ 检索可用**；这是词法基线限制，不是模型没调用工具。阈值和知识正文按任务约束未改，语义检索留给 H2-5。

**证据**：`evaluation/reports/H1-1/20261025T085310Z-batch1/case_s1.json`。

### 练习 5：找出 S4 第一次失败停在哪个决策点

**目标**：能按“输入 → 工具 → 参数 → 结果 → 生成 → 后处理 → 终态”归因。

**步骤**：打开 `evaluation/reports/H1-1/20261025T085310Z-batch1/case_s4.json`，看 `apply_turn.api_response.tools_used`、`trace.trace.tool_calls` 和回答。

**参考答案**：模型先调用了 `get_order` 和 `get_refund_status`，确认 600 ≤ 800，然后在生成阶段选择“说明规则 + 询问是否确认”，没有调用 `request_refund`。所以停在**生成/动作选择**，不是身份、参数或 Policy 失败。修复是通用 Prompt 规则，不是改 Policy 或测试。

### 练习 6：审批前后各看什么字段

**目标**：用证据证明“审批前 0 次执行、审批后 1 次执行”。

**步骤**：打开 `evaluation/reports/H1-1/20261025T093832Z-batch2/case_b1_s4r.json`，比较：

- `apply_turn.api_response.action_results[0].action.status`
- `GET /actions/{id}` 返回的 `action.execution_result`
- `state_before` / `state_after` 中的 `executor_calls`
- 审批前后 `status`、`reused`

**参考答案**：

| 时点 | status | execution_result | executor_calls |
| --- | --- | --- | --- |
| 提交后、审批前 | `awaiting_approval` | `null` | 0 |
| reviewer 审批后 | `completed` | 非空（含 `refund_id`/`refund_status=pending`） | 1 |
| 重复审批 | `completed` | 非空 | 1，`reused=true` |

`completed` 只表示模拟动作完成；退款记录仍是 `pending`，不能说到账。

### 练习 7：为什么“先 request_refund、后查订单”也算行为失败

**目标**：理解 Agent 的条件判断责任。

**参考答案**：后端即使会在 Policy 阶段拒绝，Agent 仍应先核对归属、状态、7×24 窗口、已有退款和金额。顺序错误意味着：
1. 把资格判断完全推给后端，用户得到的是一次被拒绝的动作，而不是事前解释；
2. 可能创建无意义的 rejected action，污染 Trace 和用户状态；
3. 与“Agent 判断是否满足退款条件”的产品要求不符。

第二批 B1 的正确顺序是 `get_order` → `get_refund_status` → `request_refund`。B2 过期订单则停在 `get_order`/`get_refund_status`，不提交。

### 练习 8：手算 gate 检查的执行次数

**目标**：不跑模型，验证幂等和归属。

**步骤**：看 `evaluation/reports/H1-1/20261025T093832Z-batch2/gate_checks.json`，或自己运行：

```bash
cd evaluation/reports/H1-1/20261025T093832Z-batch2
uv run --no-sync python gate_checks.py
```

**参考答案**：

| 操作 | 执行次数变化 |
| --- | ---: |
| 首次 100 元退款（ORD-H11-ORDER，≤500） | 1 |
| 同键同参重复 | 仍 1（复用） |
| 同键异参（50 元） | 仍 1（conflict） |
| customer-2 同键 100 元（ORD-H11-OTHER） | 2（新 action，独立执行） |
| 过期订单 100 元 | 2（deny，不执行） |

### 练习 9：越权查询应该怎么回答

**目标**：区分“不存在”和“不属于你”。

**参考答案**：Provider 对不可访问记录返回 `not_found`；回答应说“未找到可访问记录”，并明确**不能确认订单是否存在、也不能确认是否属于其他账号**。不得输出 `shipped`、金额、SKU、运单号等他人数据。B4 的 customer-2 查询通过。

## 三、常见问题速答

**Q：为什么 ≤500 不改 Policy？**  
A：当前业务选择是 ≤500 自动通过、>500 审批；Agent 只负责条件判断和是否提交。若要“所有退款都需人工审核”，应作为独立 Policy 任务修改并回归测试，不能夹在 Prompt 修复里。

**Q：为什么 S1B 用“退款政策是什么？”而 S1 用“退款需要满足什么条件？”？**  
A：两个都是自然问法。S1 用于暴露词法召回失败；S1B 用于验证同一知识在短问法下能返回可用引用。没有改阈值或知识，也没有把测试原句写进 Prompt。

**Q：为什么审批撤回、幂等是 unit gate 而不是真实 HTTP？**  
A：这两类规则是确定性代码，unit gate 能精确控制输入和计数；真实 HTTP 审批链路已由 B1 的 reviewer 批准覆盖。报告中已分层标注，不能把 unit 结果写成真实 E2E。

**Q：Chroma 前后 SHA 一致说明什么？**  
A：说明本轮只读知识库，没有发布、删除或修改；不证明检索质量。

**Q：为什么模型说“无法确认到账时间”也算通过？**  
A：该问题的必要事实不在知识中，正确行为是拒绝编造并说明无法确认；S2 同时要求实际调用检索并得到 `low_confidence`，避免仅凭常识作答。

## 四、证据索引

| 内容 | 文件 |
| --- | --- |
| 第一批（S1–S5） | `evaluation/reports/H1-1/20261025T085310Z-batch1/REPORT.md` |
| 修复运行（S1B/S2/S4） | `evaluation/reports/H1-1/20261025T091107Z-repair1/REPORT.md` |
| 第二批（B1–B4 + gate） | `evaluation/reports/H1-1/20261025T093832Z-batch2/REPORT.md` |
| 任务汇总 | `docs/reports/H1-1.md` |
| Prompt 契约测试 | `tests/test_support_prompt_contract.py` |
| CI 修复 | `docs/reports/H0-1.md`、`.github/workflows/tests.yml` |

> 这些材料是演示与教学证据，不是生产 benchmark。真实模型输出存在非确定性；安全规则以确定性代码和测试为准。
