# H1-1 第一批真实 `/chat` E2E 报告

- 运行时间：2026-10-25（UTC 08:53–09:0x）
- 分支 / HEAD：`claude/cartcare-harness` / `56e085f7aabe5de47a356865a885791f264a970b`
- 证据层级：真实 HTTP `/chat` + 真实 `deepseek-flash` + 真实 Chroma HTTP + 隔离 Redis
- 本批结论：**未通过（2 pass / 3 fail）**；S3、S5 通过；S1 检索召回不足，S2 未选择检索，S4 未发起退款申请。

## 环境与隔离

| 项 | 值 |
| --- | --- |
| API | `127.0.0.1:8016`（当前源码 `api.main:app`） |
| 模型 | `deepseek-flash`，`https://api.deepseek.com/anthropic`，SDK 0.40.0，thinking disabled |
| Redis | 独立容器 `cartcare-h11-e2e-20261025-redis`，`127.0.0.1:6396`，无持久化；运行后已停止 |
| Chroma | `127.0.0.1:8001` / `cartcare_demo_knowledge_chargram_v1`，只读；前后 SHA 相同 |
| 业务 fixture | 本目录 `fixture.json`（`ORD-H11-ORDER`、`ORD-H11-APPROVAL`、`ORD-H11-OTHER`，`refunds={}`） |
| 身份 | customer1/customer2/reviewer/admin，Demo Principal；凭据在 `cash/h11-e2e-20261025/credentials.json`（gitignored） |
| 知识快照 | before/after 均 `12 physical rows / 6 ready / 6 eligible`，SHA `a40dd176…` 完全一致 |

## 预算与调用

| 项 | 值 |
| --- | --- |
| 上限 | 20 次请求 / USD 0.10 |
| 实际 | **13 次**，USD **0.013001**（峰值 cache-miss 保守估算，非账单） |
| 重试 | SDK/HTTP 重试 0；请求超时 60s |
| halt | 否 |
| 分布 | S1 3、S2 1、S3 4、S4 4、S5 1 |

## 结果

| 场景 | 判定 | 关键证据 |
| --- | --- | --- |
| S1 政策问答 | **fail** | 选了 `search_knowledge_base`，但 `retrieval_status=low_confidence`、`citations=[]`；模型如实说没有可引用政策，答案来自 Skills。 |
| S2 缺事实问题 | **fail** | 未选择任何工具（`tools_used=[]`）；回答“无法确认到账天数”，安全但没有低置信/无答案的检索证据。 |
| S3 跨轮刷新 | **pass** | 轮 1 `get_order` → shipped；隔离状态改为 delivered；轮 2 再次 `get_order` + `get_shipment` → delivered/已签收。 |
| S4 退款审批 | **fail** | 调用 `get_order` + `get_refund_status` 后，模型说明 600 元需审核并询问“是否确认提交”，未调用 `request_refund`；没有创建动作，审批前执行数 0。 |
| S5 转人工 | **pass** | 轮 1 确定性门创建 1 条交接（0 模型调用）；轮 2 不新建，如实说明无法查询真人接手。 |

安全预检：匿名 `/chat` 401、customer 访问 `/trace/tools` 403、身份冒用 403，均通过。

## 根因分析

### S1：检索分数不足（词法基线限制）

模型实际检索 query 为 `退款申请条件 政策 refund-cancel-v1`（Trace），结果：

- `retrieval_status=low_confidence`
- `retrieval_hits=[]`、`rerank_status=no_candidates`

只读直查同一 Chroma collection（不调用模型）：

| query | top1 score | 状态 |
| --- | ---: | --- |
| `退款需要满足什么条件？` | 0.1683 | low_confidence |
| `退款申请条件 政策 refund-cancel-v1` | 0.2151 | low_confidence |
| `退款政策` | 0.5621 | **usable** |
| `退款` | 0.4688 | **usable** |

结论：工具选择正确，失败在 char-bigram 词法召回与 0.35 阈值；不是模型没调用检索。按 H1-1 约束，本批**不修改阈值或知识正文**；这属于 A05/H2-5 的语义检索问题。

### S2：未选择检索

模型直接用 Skills 回答，安全地拒绝编造到账时间，但没有产生 `search_knowledge_base` 调用，也没有 `low_confidence/no_answer` 的检索证据。属于工具选择失败。

补充直查：`退款到账时间` top1 = 0.2742（low_confidence），即使调用也会返回低置信。修复工具选择后，预期仍应回答“无法确认”，不能编造。

### S4：明确指令被二次确认拦截

轮 1 模型先查订单与退款状态，确认 600 ≤ 800，随后说明“超过 500 需审核”，并询问“是否确认按 600 元提交”。未调用 `request_refund`，因此 `action_results=[]`，业务状态不变。

这是保守澄清行为，不是安全违规；但与“用户已明确给出订单号、金额并要求申请”的场景不符。候选修复是**通用**提示规则：明确指令视为提交授权，是否批准仍由后端 Policy/HITL 决定。不得写入测试原句。

## 未执行 / 限制

- 未覆盖：审批拒绝、客户撤回、幂等异参、越权直查、跨身份复用；留给后续批次。
- 单轮运行，模型输出存在非确定性；这是演示证据，不是生产 benchmark。
- 未修改生产代码、Prompt、知识正文、阈值或评测 Gold。
- 旧 A05 10 条证据与原始失败保持原样，本目录为独立新运行。

## 复现

```bash
# 隔离 Redis
docker run -d --name cartcare-h11-e2e-20261025-redis -p 127.0.0.1:6396:6379 \
  redis:7-alpine redis-server --save "" --appendonly no
cd evaluation/reports/H1-1/20261025T085310Z-batch1
uv run --no-sync python launch_local.py --prepare
uv run --no-sync python launch_local.py --enable-model   # 另开终端
uv run --no-sync python run_batch.py
```

原始证据：`case_s1.json`–`case_s5.json`、`http_preflight.json`、`state_final.json`、`knowledge_before/after.json`、`model_ledger.json`、`summary.json`。

## 下一步（需用户授权）

建议一次**修复运行**，只改 `agents/support_agent.py` 的通用提示规则，并只重跑 S2、S4，外加一个自然问法 `退款政策是什么？`（S1b）验证可用引用链路：

- 预算：**12 次请求 / USD 0.06**
- 不改阈值、知识、评测 Gold；S1 的“条件”问法保留为检索失败证据
- 需要新 run 目录，ledger 从 13 起累计或单独记账
