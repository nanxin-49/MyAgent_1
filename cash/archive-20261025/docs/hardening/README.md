# CartCare Hardening V3 — Codex 执行入口

> **一次只执行一个 `Axx/问题ID`**。以 `docs/engineering/project-audit-20261011.md`（2026-10-11 未提交工作区审查）为事实基线；沿用 T01–T12、Single Agent、原 Workbench/`docs/cartcare-workbench-progress.json`。**不创建新的进度系统，也不要求每次读完整审查或全部任务文档。**

## 本轮最少读取

1. `AGENTS.md`；2. 本文件；3. `docs/hardening/tasks/<Axx>.md` **当前 ID 小节**；4. `docs/engineering/project-audit-20261011.md` **相关 C/N 条目**；5. 对应代码、测试与复现证据。

**审查证据**：HEAD `09efd344`（审查时）；15 条隔离复现观察成立，**表示缺陷被观察到，不表示已修复**。当时 pytest `150 passed, 2 skipped`，Node `12 passed`；未重跑真实模型/Redis-Chroma E2E。核对当前 `HEAD` 与未提交工作区。复现脚本 `docs/engineering/audit_20261011_probe.py` 和观察 JSON 需从原 Codex 工作区查找；本包只有审查 Markdown，缺失不可伪造。

## 执行顺序（只做本轮指定项）

| 顺序 | 任务 ID → 任务文件 | 结果要求 |
| --- | --- | --- |
| 0 | `A00-lite/INTAKE` → `A00-lite.md` | 直接接收/核对审查，不重做完整基线 |
| **P0** | `A04/N01` → `A04.md` | 幂等异参冲突与跨身份内部 key 越权复用 |
| **P0** | `A03-lite/N03` → `A03-lite.md` | Provider 畸形记录的错误泄露阻断 |
| **P0** | `A03-lite/N02-auth` → `A03-lite.md` | Principal 身份与独立 reviewer 权限 |
| **P0** | `A03-lite/N02-ops` → `A03-lite.md` | Trace / 知识 / Skills / Eval 端点最小授权 |
| P1 | `A04/N05`，`A04/N04` → `A04.md` | 动作成功不被 Memory 失败遮蔽；退款写后可查 |
| P1 | `A07/N10` → `A07.md` | API Eval 与正常聊天业务状态隔离 |
| P1 | `A05/N06`，`A05/N07` → `A05.md` | 旧知识退役；Rerank 空结果不伪装 usable |
| 核心 | `A02/C04` → `A02.md` | 结构化 Handoff，越界拒绝不自动等于转人工 |
| 实验 | `A05/EXPERIMENT` → `A05.md` | 冻结 30+ gold，B0/B1 对照（受资源许可） |
| 交付 | `A07/EVIDENCE` → `A07.md` | 证据、Demo、独立代码讲解；第六周停加功能 |

**条件/待办**：`A01/C03`、`A01/N11`、`A06-lite/N08`、`A06-lite/N09`、`A07/N14`。N08/N09 已有隔离复现，若延期标 **known_open**，不得宣称并发 Memory 可靠。N12/N13/N15 与 MCP/LangGraph 默认不做。详细映射在 `ISSUE-MAP.md`，周计划在 `ROADMAP.md`，**仅需规划时读取**。

## 每轮执行合同

1. 记录 `git status --short`、`git rev-parse HEAD`，保留原有未提交文件。先确认问题是否已在当前 HEAD 修复。
2. 对真实问题先建**预期安全行为**的红测，再最小修复、跑绿测与相关回归。审查脚本“缺陷确实发生”的通过断言不是修复成功证明。
3. 一次只动一问题，沿用既有 Provider/ActionService/Policy/Memory/RAG 契约；不重构全部 Agent，不接真实支付。
4. 必须分别标注 unit/Fake SDK、live Redis-Chroma、真实模型 E2E；历史 T01–T12 报告**只读**；真实模型付费调用和外部动作先获授权。
5. 更新**已有 Workbench** 的对应 Axx 与问题 ID；有接口变化才更新 README/核心 Wiki；文档聚焦技术证据，不逐小项写教程。
6. 完成后汇报：**ID、HEAD、复现证据、变更文件、红绿测试命令和计数、仍未解决风险、一个不靠 Codex 的练习**，并停下等待下轮任务。
7. 本地 Demo Auth 不能代替公网认证；P0 未完成不能宣称公网安全；**`/eval/run` 有了授权仍必须隔离业务状态**。

## 可直接复制的指令

```text
阅读 AGENTS.md、docs/hardening/README.md，
以及 docs/hardening/tasks/A04.md 的 A04/N01 小节。
对照 docs/engineering/project-audit-20261011.md 中的 N01。
本轮只做 A04/N01：核对 HEAD/未提交改动，先写期望安全行为的失败回归，
再做最小修复，跑测试并记录红绿结果；不要自动进入其他任务。
保留历史 T01–T12，不调用真实付费/危险服务，更新现有 Workbench，
最后提供我独立完成的一项 Debug 练习。
```
