# H1-1 第二批真实 `/chat` E2E 报告

- 运行时间：2026-10-25（UTC 09:38–09:4x）
- 分支 / HEAD：`claude/cartcare-harness` / `5a72b9c`（含资格核对 Prompt 修订，工作区另有未提交证据）
- 结论：**4/4 真实场景通过** + 确定性 gate 全部通过；H1-1 的 9 个验收场景均有成功证据，建议置 `verify`。

## 环境与预算

| 项 | 值 |
| --- | --- |
| API | `127.0.0.1:8018`（当前源码） |
| 模型 | `deepseek-flash`，`https://api.deepseek.com/anthropic` |
| Redis | 独立容器 6396，无持久化；运行后停止 |
| Chroma | 只读；前后 SHA 相同（12 rows / 6 ready） |
| 上限 / 实际 | 20 次 / USD 0.10；**10 次 / USD 0.012921**（保守估算） |
| halt | 否 |

## 真实 HTTP 结果

| 场景 | 判定 | 关键证据 |
| --- | --- | --- |
| B1-S4R `为订单 ORD-H11-APPROVAL 申请退款 600 元` → 审批 → 查询 | **pass** | 工具顺序 **`get_order` → `get_refund_status` → `request_refund`**；审批前 `awaiting_approval`、执行 0；reviewer 审批后 `completed`、执行 1；重复审批 `reused`；查询轮 `get_refund_status`；订单 `refund_pending`、退款记录 `pending` |
| B2-EXPIRED 超 7 天订单申请退款 100 元 | **pass** | `get_order` + `get_refund_status`，**未调用 `request_refund`**；明确说明 7×24 窗口已过、未提交；无动作、无状态写入 |
| B3-MISSING `我要退款`（无订单号） | **pass** | 0 工具、0 动作；要求提供订单号/金额，并说明提交后由系统审核 |
| B4-OWNERSHIP customer-2 查询 customer-1 的 `ORD-H11-ORDER` | **pass** | `get_order` 返回不可访问；回答未出现 `shipped`/`129.90`/`SKU-H11`/运单号；未声称找到，未确认他人订单是否存在 |

B1 实际 action：`act_b02400b7fb9347e5`；订单 `refund_pending`；executor 调用 1 次。

## 确定性 Gate（unit，无 HTTP/模型）

`gate_checks.py` 全部通过：

| 检查 | 结果 |
| --- | --- |
| 客户撤回自己的待审批请求 | `rejected`，执行 0 |
| 同键同参重复 | 复用同一 action，执行仍 1 |
| 同键异参 | `idempotency_conflict`，不执行 |
| 跨用户同键 | 新 action（customer-2），不取旧结果，执行独立 1 次 |
| 过期订单 Policy 拒绝 | `refund_window_expired`，执行 0 |

## H1-1 验收覆盖

| 验收场景 | 证据 | 层级 |
| --- | --- | --- |
| 有依据的政策问答 | S1B `usable` + `refund-cancel-v1` citation | 真实 HTTP + 模型 |
| 缺事实的相近问题 | S2 `low_confidence`、不编造到账时效 | 真实 HTTP + 模型 |
| 订单/物流跨轮刷新 | S3 状态变更后返回 delivered | 真实 HTTP + 模型 |
| 资格咨询与缺参 | B2 过期拒绝提交；B3 缺订单号澄清 | 真实 HTTP + 模型 |
| 退款申请 → 审批 → 查询 | B1 先核对再提交、审批后执行 1、退款 pending | 真实 HTTP + 模型 |
| 审批分支 | B1 reviewer 批准；gate 客户撤回；gate Policy 拒绝 | HTTP + unit |
| 重复请求 | gate 同键复用/异参冲突/跨用户不复用 | unit |
| 越权 | B4 跨客户查询不泄露；preflight 身份冒用 403 | HTTP + unit |
| 转人工 | S5 创建 1 条、追问不重复 | 真实 HTTP + 模型 |

## 限制

- 单轮运行，模型非确定性；演示证据，不是生产 benchmark。
- 审批撤回、幂等和 Policy 拒绝是进程内 unit gate，不是真实 HTTP 审批链路；已单独标注层级。
- 第一批 S1（`退款需要满足什么条件？`）的词法召回失败保留；S1B 使用自然短问法证明引用链路，不是阈值修改。该差异归 H2-5。
- PolicyEngine 未改：≤500 自动通过、>500 reviewer 审批；Agent 负责条件判断与是否提交。
- 未接真实支付、真人客服或通知。

## 复现

```bash
docker start cartcare-h11-e2e-20261025-redis
cd evaluation/reports/H1-1/20261025T093832Z-batch2
uv run --no-sync python gate_checks.py
uv run --no-sync python launch_local.py --prepare
uv run --no-sync python launch_local.py --enable-model   # 另开终端
uv run --no-sync python run_batch.py
```

原始证据：`case_b1_s4r.json`、`case_b2_expired.json`、`case_b3_missing.json`、`case_b4_ownership.json`、`gate_checks.json`、`summary.json`、`state_final.json`、`knowledge_before/after.json`、`model_ledger.json`。
