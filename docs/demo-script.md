# H5-3 Demo 脚本与录屏素材

目标：2–3 分钟演示 CartCare 的单 Agent 工具链路、复合诉求、审批中断恢复、越权拦截和按步 Trace。用户已选择不录屏；实际证据见 [`docs/demo-evidence/index.html`](demo-evidence/index.html)。本文保留完整复现步骤、预期画面和可一键准备的 fixture。

> 演示环境：真实模型 + 真实 Redis/Chroma + 模拟商城/支付后端。不能把演示结果写成生产 SLA 或真实支付能力。

## 0. 一次性准备

### 0.1 依赖与 fixture

```bash
uv sync --dev

# 启动 Redis / Chroma（若旧 echomind-* 容器仍在，先看 docs/naming.md）
docker compose up -d redis chromadb
# Windows 若 6379/6380 被系统排除，可改用：REDIS_PORT=16379 docker compose up -d redis
# 并把下面的 REDIS_URL 端口同步改为 16379

# 生成 H5-3 专用 fixture（写入 data/eval，Docker 的 data/eval 也会挂载）
uv run python -m demo.prepare_h5_3

# 知识库首次为空时加载获批演示资料
uv run python -m mcp.seed_demo_knowledge --check-assets
uv run python -m mcp.seed_demo_knowledge
```

fixture 包含：

| 订单 | 用户 | 用途 |
| --- | --- | --- |
| `ORD-DEMO-REFUND` | customer-1 | 100 元退款，Policy allow，直接 completed |
| `ORD-DEMO-APPROVAL` | customer-1 | 800 元退款，金额超阈值，进入 awaiting_approval |
| `ORD-DEMO-OWNERSHIP` | customer-1 | customer-2 尝试取消，演示归属拦截 |

### 0.2 本地 API 与 Demo Auth

录屏建议用 **本地 uvicorn**（`API_HOST=127.0.0.1` 才能启用回环 Demo Auth），Redis/Chroma 继续用容器：

```bash
export REDIS_URL='redis://:cartcare123@localhost:6379/0'   # 与容器密码一致
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export PROMETHEUS_PORT=0
export CARTCARE_BUSINESS_FIXTURE="$PWD/data/eval/demo_h5_3_fixture.json"
export CARTCARE_AUTH_MODE=demo
export APP_ENV=development
export API_HOST=127.0.0.1
# 固定 demo 前缀，重启时保持不变；避免历史 pending action 干扰
export CARTCARE_ACTION_PREFIX=h53-demo-actions
export CARTCARE_CHECKPOINT_PREFIX=h53-demo-checkpoints

# 生成一次性 Demo 凭据（只打印到当前终端，不写入仓库）
eval "$(uv run python -m demo.print_credentials)"

# 从 Claude Code 终端启动时，避免继承本地代理：
# env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY -u ANTHROPIC_MODEL uv run python -m uvicorn ...
uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/demo>，在页面输入：

- Customer token：`$CUSTOMER1_TOKEN`
- Reviewer token：`$REVIEWER_TOKEN`
- Admin token：`$ADMIN_TOKEN`

`$CUSTOMER2_TOKEN` 用于越权场景。Token 只放在页面内存；录屏时不要展示完整 token。

检查：

```bash
curl -fsS http://127.0.0.1:8000/ready
uv run python -m demo.preflight_h5_3 --base-url http://127.0.0.1:8000
```

## 0.3 本机最短路径（Windows + 已启动 Redis/Chroma）

本机 Redis 在 **16379**（Windows 排除 6379/6380）。用两个终端，避免 token 丢失：

**终端 A：生成凭据 + 启动 API**

```bash
# 只写到临时文件，录屏后删除；不要提交
uv run python -m demo.print_credentials > "data/eval/h53_env.sh"
source "data/eval/h53_env.sh"

export REDIS_URL='redis://:cartcare123@localhost:16379/0'
export CHROMA_HOST=localhost CHROMA_PORT=8001 PROMETHEUS_PORT=0
export CARTCARE_BUSINESS_FIXTURE="$PWD/data/eval/demo_h5_3_fixture.json"
export CARTCARE_AUTH_MODE=demo APP_ENV=development API_HOST=127.0.0.1
export CARTCARE_ACTION_PREFIX=h53-demo-actions
export CARTCARE_CHECKPOINT_PREFIX=h53-demo-checkpoints

# 从 Claude Code 终端启动时避免继承代理；普通终端可去掉 env -u
env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY -u ANTHROPIC_MODEL \
  uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

PowerShell 等价：

```powershell
uv run python -m demo.print_credentials --powershell > data/eval/h53_env.ps1
. .\data\eval\h53_env.ps1
$env:REDIS_URL = 'redis://:cartcare123@localhost:16379/0'
$env:CHROMA_HOST = 'localhost'; $env:CHROMA_PORT = '8001'; $env:PROMETHEUS_PORT = '0'
$env:CARTCARE_BUSINESS_FIXTURE = (Resolve-Path data/eval/demo_h5_3_fixture.json).Path
$env:CARTCARE_AUTH_MODE = 'demo'; $env:APP_ENV = 'development'; $env:API_HOST = '127.0.0.1'
$env:CARTCARE_ACTION_PREFIX = 'h53-demo-actions'
$env:CARTCARE_CHECKPOINT_PREFIX = 'h53-demo-checkpoints'
# Claude Code 终端可先 Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_API_KEY, Env:ANTHROPIC_MODEL
uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

**终端 B：preflight + 录屏中的 curl**

```bash
source "data/eval/h53_env.sh"
export CARTCARE_AUTH_MODE=demo APP_ENV=development API_HOST=127.0.0.1
uv run python -m demo.preflight_h5_3 --base-url http://127.0.0.1:8000
```

浏览器打开 <http://127.0.0.1:8000/demo>，从终端 A 的凭据输出复制 customer/reviewer/admin token；不要把完整 token 录进画面。录屏结束后删除 `data/eval/h53_env.sh`。

### 0.4 录屏前清场

- 重新生成 fixture 并重启 API，避免前面演示改变内存业务状态。
- 确认 `.env`、终端历史和浏览器地址栏不出现真实 API key/token。
- 关闭无关通知；分辨率建议 1440×900 或 1920×1080。
- 准备两个终端：一个跑 API，一个跑 curl；浏览器打开 `/demo`。

## 1. 分镜（目标 2:30）

### 0:00–0:20 定位

画面：README 首屏或 `/demo` 页面。

口播要点：

- CartCare = 自研 Agent Harness + 电商客服 Agent。
- 模型选工具；Provider 给事实；Policy/HITL 控制危险动作；Trace 展示执行证据。
- 业务后端是明确标注的模拟系统。

### 0:20–0:50 政策问答与引用

操作：选择/粘贴 `退款政策是什么？`，customer-1 发送。

预期画面：

- Agent 回答退款政策。
- RAG 卡片显示 `usable`、citation、source、`policy_version`；文档标题来自 Trace。
- 若返回 `low_confidence`/`no_answer`，如实说明“没有可靠引用”，不要补造引用；检查 `/ready` 和知识库 seed 后重试。

口播：引用证明检索来源，不等于逐句事实核验。

### 0:50–1:40 复合售后 + 待审批

操作：粘贴：

```text
请现在为订单 ORD-DEMO-REFUND 提交 100 元退款；为订单 ORD-DEMO-APPROVAL 提交 800 元退款，需要审批就暂停等待审批。
```

预期画面：

- 回答逐项列出两个动作，不能把整单说成全部完成。
- Action 卡片：
  - `ORD-DEMO-REFUND`：`completed`，refund_id / refund_status=pending。
  - `ORD-DEMO-APPROVAL`：`awaiting_approval`，action_id。
- Tool Trace：`request_refund` 两次（或模型先查订单再提交），Policy 决定分别为 allow / require_approval。
- 记录本轮的 `request_id` 和待审批 `action_id`（画面暂停 1 秒，或复制到终端变量）。

口播：completed 只表示模拟动作完成；退款 pending 不代表到账。

### 1:40–2:20 审批前杀进程 → 重启 → 批准并恢复

操作：

1. 在 API 终端按 `Ctrl+C`（或结束 uvicorn 进程），确认服务停止。
2. 用相同环境变量重启 uvicorn。
3. 在第二个终端执行：

```bash
export REQUEST_ID='<上一步的 request_id>'
export ACTION_ID='<待审批 action_id>'

# reviewer 批准；会执行模拟退款
curl -sS -X POST "http://127.0.0.1:8000/actions/$ACTION_ID/approve" \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"customer-1\",\"request_id\":\"$REQUEST_ID\"}"

# 客户从检查点恢复，把逐动作回执写回原会话
curl -sS -X POST "http://127.0.0.1:8000/checkpoints/$REQUEST_ID/resume" \
  -H "Authorization: Bearer $CUSTOMER1_TOKEN"

# 查看检查点与动作回执
curl -sS "http://127.0.0.1:8000/checkpoints/$REQUEST_ID" \
  -H "Authorization: Bearer $CUSTOMER1_TOKEN"
```

预期画面：

- 重启后 `POST /checkpoints/.../resume` 返回 `completed`，`memory_write_status=completed`，`already_resumed=false`。
- `GET /checkpoints` 显示 `status=completed`，`resumed_at` 非空。
- 再次 resume 返回 `already_resumed=true`，不重复写 Memory。
- 可补充展示 `GET /actions/$ACTION_ID` 的 `completed` 与 `refund_status=pending`。

口播：PendingAction 和检查点持久化在 Redis；执行已派发但没有回执时按 `execution_unknown` 失败，不自动重放。

### 2:20–2:40 越权拦截

操作：

- 把客户 token 换成 `$CUSTOMER2_TOKEN`，user_id 改为 `customer-2`。
- 粘贴：`请尝试取消订单 ORD-DEMO-OWNERSHIP。`
- 发送。

预期画面：

- 回答不能泄露订单是否存在、状态或金额；不出现“已取消”。
- Tool Trace 没有已执行的写动作；Provider/ActionService 拒绝或返回不可访问。
- Action 卡片若出现，状态为 rejected/failed，不是 completed。

口播：身份只来自服务端 Principal；客户端 user_id/token 不能越权。

### 2:40–3:00 按步 Trace

操作：在复合场景卡片展开“原始 API / Trace JSON”，或打开：

```bash
curl -sS "http://127.0.0.1:8000/trace/tool/$REQUEST_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

展示：

- `steps`：每步 input/output token、latency_ms、tools、stop_reason。
- `tool_calls`：工具名、验证后参数、结果摘要、Policy/action_result。
- `stop_reason`：completed / awaiting_approval 等。
- `context_rounds`：上下文构成（如展示）。

口播：Trace 记录执行证据，不保存隐藏推理或原始 Memory；admin 才能读。

## 2. 常见失败与处理

| 现象 | 处理 |
| --- | --- |
| `/chat` 返回 200 但回答是模型失败，日志 `model not found: deepseek-flash` | 请求被 Claude Code 本地代理接管；启动时 `env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY -u ANTHROPIC_MODEL`，让 `.env` 的模型配置生效 |
| `/chat` 401 | token 与 user_id 不匹配或 token 空；`CUSTOMER1_TOKEN` 配 `customer-1`，`CUSTOMER2_TOKEN` 配 `customer-2` |
| 重启后新请求复用旧 pending action | 使用固定的 `CARTCARE_ACTION_PREFIX` / `CARTCARE_CHECKPOINT_PREFIX`；换一次全新录制时用新后缀，或清理该 demo 前缀的键 |
| 复合请求只出现一个 action，Trace 为 `budget_exhausted` | H3-6 已记录的 3 轮上限问题；重启 fixture 重试或缩短消息，不能补造第二个 action |
| 政策问题没有 citation | 检查 `/ready`、知识库 seed；如实展示 low_confidence/no_answer，不伪造 |
| 模型反复反问，不创建 action | 用上面的命令式消息重试；仍不执行就记录为模型行为，不后期补造 |
| 800 元退款没有 awaiting | 确认 fixture 已重新生成并重启 API；确认金额/订单 |
| 重启后页面空白 | 用 curl 展示检查点/动作；页面状态不持久，Redis 状态持久 |
| 端口 6379/8001 被占 | 旧 `echomind-*` 容器未迁移；按 [命名迁移](naming.md) 停旧栈、保留数据卷 |
| `/ready` 503 | 检查 Redis/Chroma；不要在依赖未就绪时录屏 |
| 审批/恢复 401/403 | customer/reviewer/admin token 用错；reviewer 必须在 `review_customers` 内 |

## 3. 录屏后检查

- [ ] 五个场景都出现，且没有把 awaiting_approval 说成 completed
- [ ] 政策引用来自 Trace，不是凭空生成
- [ ] 杀进程后能从检查点恢复，重复 resume 不重复写
- [ ] 越权场景没有已执行写动作
- [ ] Trace 展示 `steps` 与 `stop_reason`
- [ ] 视频未出现 API key、完整 token、`.env` 内容或真实客户数据
- [ ] 结尾说明：真实模型 + 模拟业务后端，不是生产 SLA

## 4. 产出

- fixture/场景：`uv run python -m demo.prepare_h5_3`
- 一次性凭据：`uv run python -m demo.print_credentials`
- 录屏文件由用户保存；README 的 Demo 视频占位在 H5-3 后替换为真实链接。
