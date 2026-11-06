# H1-1 修复运行 1 报告

- 运行时间：2026-10-25（UTC 09:11–09:1x）
- 分支 / HEAD：`claude/cartcare-harness` / `56e085f7aabe5de47a356865a885791f264a970b`（工作区包含 H1-1 未提交改动）
- 目的：验证通用 Prompt 修复能否让 S2 选择检索、S4 直接提交明确退款指令，并用自然问法 S1b 验证可用引用链路。
- 结论：**3/3 通过**（S1B、S2、S4）。

## 改动

仅修改 `agents/support_agent.py` 的 `_build_system_prompt`，新增 `[检索与显式动作]` 通用规则：

1. 静态政策、FAQ、流程和规则类问题，应先调用 `search_knowledge_base`；没有可用引用时只说明无法确认，不凭 Skills/历史/常识补全。
2. 用户明确给出订单号、金额并直接要求申请退款时，视为已授权提交，直接调用 `request_refund`，不再次询问确认；批准/拒绝/执行仍由后端 Policy/HITL 决定。
3. 提交不等于退款通过、完成或到账。

新增红测 `tests/test_support_prompt_contract.py`（修复前 2 failed，修复后通过），用于防止规则被删除；真实行为证据是本报告的真实模型运行。

**未修改**：PolicyEngine（保持 ≤500 自动、>500 审核）、知识正文、0.35 阈值、Gold、业务服务。

## 环境与预算

| 项 | 值 |
| --- | --- |
| API | `127.0.0.1:8017` |
| 模型 | `deepseek-flash`，`https://api.deepseek.com/anthropic` |
| Redis | 独立容器 6396，无持久化；运行后停止 |
| Chroma | 只读；前后 SHA 相同（12 rows / 6 ready） |
| 上限 / 实际 | 12 次 / USD 0.06；**10 次 / USD 0.0103392**（保守估算） |
| halt | 否 |

## 结果

| 场景 | 判定 | 证据 |
| --- | --- | --- |
| S1B `退款政策是什么？` | **pass** | `search_knowledge_base`；`usable`；1 条 citation，`policy_version=refund-cancel-v1`；回答覆盖 7×24、订单状态、金额与审批 |
| S2 `退款审核通过后，钱几天能到我的银行卡？` | **pass** | `search_knowledge_base`；`low_confidence`、0 citation；回答明确“没有可引用依据、无法给出天数”，未编造渠道/时效 |
| S4 `为订单 ORD-H11-APPROVAL 申请退款 600 元` → 审批 → 查询 | **pass** | `request_refund` 直接提交；审批前 action `awaiting_approval`、`execution_result=null`、executor 调用 0；reviewer 审批后 `completed`、executor=1；重复审批 `reused=true` 且仍为 1；查询轮 `get_refund_status`；订单 `refund_pending`、退款记录 `pending` |

S4 实际 action：`act_d2dd01b5fde9424b`；退款记录 `REF-act_d2dd01b5fde9424b`，状态 `pending`。动作完成不代表资金到账。

## 与第一批的关系

- 第一批 S1（`退款需要满足什么条件？`）的检索失败**保留**：词法 top1 0.1683/改写 0.2151 < 0.35；S1B 证明同一知识在自然短问法下可返回 usable citation。这不是阈值修复，属于问法/语义召回差异，仍归 H2-5。
- 第一批 S2/S4 的失败由本轮 Prompt 修复解决；原始失败证据保留在 `../20261025T085310Z-batch1/`。
- 第一批 S3/S5 仍为通过。

## 后续调整（未重跑模型）

用户随后要求：保持 ≤500 元自动通过，但 Agent 必须先判断退款条件。已在 `agents/support_agent.py` 将规则改为：明确退款指令先调用 `get_order` + `get_refund_status` 核对归属、状态、7×24 窗口、已有退款和金额；条件不满足则说明不提交，满足或无法确定才调用 `request_refund`。契约测试已同步。

**本报告 S4 的 3/3 证据对应调整前的 Prompt 版本**；调整后的“先核对再提交”尚未经过真实模型验证，建议在下一批 S4 复验时记录工具顺序。

## 未覆盖 / 限制

- H1-1 的 9 个验收场景尚未全部覆盖：资格咨询与缺参、审批拒绝/客户撤回、幂等异参/跨身份复用、越权直查仍待后续批次。
- PolicyEngine 未改为“所有退款都需审核”；当前仍是 ≤500 自动、>500 审核。用户的“最终都需要人工审核”作为独立规则待办记录，不在本轮擅自修改。
- 单轮运行、模型非确定性；演示证据，不是生产 benchmark。
- 未接真实支付、真人客服或通知。

## 复现

```bash
docker start cartcare-h11-e2e-20261025-redis
cd evaluation/reports/H1-1/20261025T091107Z-repair1
uv run --no-sync python launch_local.py --prepare
uv run --no-sync python launch_local.py --enable-model   # 另开终端
uv run --no-sync python run_batch.py
```

原始证据：`case_s1b.json`、`case_s2.json`、`case_s4.json`、`summary.json`、`state_final.json`、`knowledge_before/after.json`、`model_ledger.json`。
