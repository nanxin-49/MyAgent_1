# CartCare 项目移交给下一位 Agent

> 快照日期：2026-10-25（Asia/Shanghai）。本文件是接手索引；**当前事实以可执行代码、测试、实际运行结果为准**，任务状态以现有 Workbench 和进度 JSON 为准。接手时先重新核对 HEAD、工作区和服务状态，不把这份快照当作永久有效的运行证明。

## 1. 接收范围与当前快照

- 项目：CartCare，面向电商客服的 Agent 工程简历项目。仓库：`E:\AAA_NEED\Echomind_new\EchoMind`；远端 `https://github.com/nanxin-49/MyAgent_1.git`。
- 本次核对：`main` 与 `origin/main` 同在 `ea8ae67f63fc0fbe510a39c37183cdf3e93710bc`，`git status --short --branch` 仅显示 `## main...origin/main`，工作区干净。此文档写入后会成为新增未提交文件；不要把写入前的“干净”误作写入后的状态。
- 规范：根目录 `AGENTS.md`、`docs/CartCare-Codex-Workbench.html`、`docs/cartcare-workbench-progress.json`、`docs/hardening/README.md`。Python 3.12；`pyproject.toml` 与 `uv.lock` 是依赖事实源。接手一个 V3 任务时只读对应 `docs/hardening/tasks/<Axx>.md` 和审查中相关 C/N 条目。
- 本次仅做文档交接，没有改业务代码、任务状态、Gold、阈值或历史报告，也没有启动服务、调用模型或执行线上动作。

## 2. 实际执行路径与边界

`api/main.py:chat` 通过 `core/auth.py` 获取服务端 `Principal`，读取 Memory，调用 `SupportRuntime.run` / `SingleSupportAgent.handle`，由 Agent 选择共享 Tool Contract 中的工具，再写 Memory 并返回结构化结果和 Trace。RAG 由 Agent 按需调用，不是每次 `/chat` 的固定前置步骤。旧 specialist/multi-Agent 代码用于历史实验，不参与当前 `/chat` 分发。参见 `README.md`、`wiki/重点代码.md`，但以 `api/main.py` 与 `agents/support_agent.py` 的调用为准。

| 事项 | 当前接线和含义 | 不可扩大表述 |
| --- | --- | --- |
| 动态业务事实 | `agents/tools.py:build_business_tools` → Provider；API lifespan 注入 JSON fixture 演示后端 | 没有真实商城、支付或物流系统集成 |
| 退款/取消 | Agent 只能请求；`ActionService` → `PolicyEngine` → 必要时 reviewer 审批 → 模拟 Executor；回执可查询 | `completed` 不等于资金到账；Store/业务状态以进程内实现为主 |
| 人工交接 | `HandoffService` 建立 Principal 范围内的结构化模拟记录；`handoff_id`、状态和查询回执是依据 | 建单不等于真人接手、通知或 SLA |
| 静态知识 | `KnowledgeBase` 通过 `chromadb.HttpClient` 使用外部 Chroma Server；有效发布、引用和 rerank 状态有契约 | `usable`/citation 不证明完整答案正确；0.35 是演示基线 |
| 身份 | 默认拒绝；本地 Demo Bearer 仅在显式 development + loopback 条件下可用；admin/reviewer/customer 权限分开 | Demo adapter 不是生产认证或公网部署许可 |
| 评测 | `/eval/run` 要求 admin，并用独立模拟 runtime/state；T09–T12 报告属于各自历史条件 | Eval 不在每次 `/chat` 中运行；不同证据层不能合并为生产成功率 |

## 3. 任务状态与已知证据

`docs/cartcare-workbench-progress.json` 在本次核对时记录：T01–T12 与 `SINGLE_MIGRATION` 为 `done`；A00-lite、A02、A03-lite、A04、A07 为 `verify`；A05 为 `doing/partial`。V3 的 `outcome=fixed` 与用户验收状态是两个字段，不能因代码已修就自行改为 `done`。

| 任务 | 当前结果 | 接手关注点 |
| --- | --- | --- |
| A03-lite | N03 Provider 错误投影、N02 身份和运维端点权限 `fixed/verify` | 生产验证器、凭据生命周期、网络边界仍未交付；读 `docs/engineering/ADR-auth-and-provider-safety.md` |
| A04 | N01 幂等与身份复用、N05 动作完成后 Memory 写失败、N04 退款读写一致性 `fixed/verify` | 进程崩溃、多 worker、持久恢复和真实支付仍无保证；按对应技术说明核对 |
| A02/C04 | 结构化交接 `fixed/verify` | 进程内模拟记录、无真人服务；看 `docs/engineering/A02-handoff.md` |
| A05 | N06/N07 契约与若干局部修复已实施；整体 `doing/partial` | B0 有冻结实验；B1 尚未完成；真实 `/chat` 的原 10 例为 5 pass、3 partial、2 fail，未触发 RAG，基本 Demo 验收未通过。读 `evaluation/reports/hardening/A05/chat-e2e-20261014/REPORT.md` 与当前 `A05.md` |
| A07 | N10 评测业务状态隔离、CI-REPRO 字节保护 `fixed/verify` | `A07/EVIDENCE` 未完成；10 月 24 日报告证明独立本机检出/locked 环境，**不证明当前远端 CI 已绿**。读 `docs/engineering/A07-ci-repro-20261024.md` 与 `A07.md` |

证据层级必须注明：Fake/unit、真实 Redis/Chroma、真实模型、真实 HTTP `/chat` 分开。A05 原始模型 E2E 的失败不能被后续离线回复修复回填成 pass；后续 `A05-ANS24-REPLY` 的 577-pass 结果是离线回归，不是新一轮真实模型 E2E。模型输出提到“转人工”也不是创建记录的证据。

## 4. 本次可复现的本机检查

在上述 HEAD、Windows 工作区运行：

```powershell
git status --short --branch
git rev-parse HEAD
uv lock --check
uv run python -m pytest -q
```

本次结果：锁解析 53 packages；pytest `577 passed, 3 skipped, 1 warning`（约 11.49 秒）。三个 skipped 分别是 1 个需要 live Redis/Chroma 的 Memory 测试和 2 个需要真实 Chroma HTTP 的 RAG 测试；warning 为 Starlette TestClient 引用 AnyIO `BlockingPortal` 的弃用提示。此检查没有覆盖 live 服务、真实模型、浏览器 Demo、远端 CI。10 月 24 日独立 byte-tree 验证另有 Node UI `12 passed`，但本次没有重跑 Node。

## 5. 下一位 Agent 的接手顺序

1. 重新读取 `AGENTS.md`、Workbench、progress JSON 和 `docs/hardening/README.md`；用代码与测试确认当前分支和工作区，不直接继承此文的状态。
2. **先让用户指定单个 `Axx/issue-id`**。若用户只说“继续”，先给出当前 `verify` 待验收项、A05 未完成实验及 A07/EVIDENCE 的简短选项；不要自动横跨多个任务。每轮只实施一个 ID，并停在该 ID 的报告。
3. 对所选 ID 读其任务文件当前小节、相关审查 C/N、代码和测试。已修复则验证并记录 `verified_no_fix`；确有缺陷则先写安全预期红测、最小修复、相关回归。不要用修改冻结 hash/Gold/阈值或跳过测试来换取绿灯。
4. 若接 A05：先核对现有冻结数据、B0/B1 资源与验收约束；真实模型、较大模型下载和外部写入按明确授权边界执行。原始 E2E 报告保留，另存新运行证据。
5. 若接 A07：先核对当前 GitHub Actions 在当前 HEAD 的真实状态；`A07/EVIDENCE` 依任务文件整理已验证案例，不新增功能。旧 CI 失败是历史观察，独立本机成功不能冒充远端成功。
6. 更新**已有** Workbench/progress JSON 中对应 ID 的状态与结果；若调用链变化才同步 README/两份核心 Wiki。保留 T09–T12 和冻结评测原件。报告中给出变更文件、前后调用链、红绿命令与计数、DoD、限制、文档漂移、建议状态、建议提交信息及一项不用 Codex 的练习。

## 6. 明确的未完成事项与文档漂移

- A05/B1 语义 Embedding 对照与完整实验 DoD 未完成；现有字符 bigram 检索基线和真实模型 `/chat` 结果不能拼成已验证的 RAG 生成链路。A05 的历史动态金额未重查、答复质量和能力边界问题应按新 ID/新证据处理。
- Memory N08/N09 已有隔离复现而仍可列 `known_open`；A01 等条件项按 V3 任务文件决定。不要称并发 Memory 可靠，也不要默认引入 LangGraph/MCP。
- `docs/CartCare-Codex-Workbench.html` 的“认证与 ownership”基线段仍写“没有正式认证主体，demo identity 来自请求体”；当前代码已有 `AuthAdapter`/服务端 `Principal` 且默认拒绝。应在**单独获选的文档清理或相关任务**中按现行代码修正该静态段；本次只记录漂移，不重写工作台。
- `docs/engineering/A07-ci-repro-20261024.md` 写作时是“未提交/未推送的拟议字节树”。本次仓库 HEAD 已是后续提交；引用其中测试时应说“该报告当时的验证”，并另查当前 GitHub Actions 状态。

## 可复制给下一位 Agent 的起始指令

> 请先阅读仓库 `AGENTS.md`、`docs/CartCare-Codex-Workbench.html`、`docs/cartcare-workbench-progress.json`、`docs/hardening/README.md` 与 `docs/CartCare-Agent-Handoff-20261025.md`。先只读核对 HEAD、工作区、真实 `/chat` 调用链和测试，不把历史报告当作当前运行结果。向我汇报可选的**单个** Axx/issue-id 与验收边界；待我选定后，仅执行该 ID，保留冻结证据和无关改动，给出红绿验证及一项独立练习。
