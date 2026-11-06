# A00-lite / INTAKE｜接收现有审查基线，不重新审查项目

**时间上限**：建议 15–30 分钟核对，最长半天；**不改业务代码**。

## 先读

`docs/engineering/project-audit-20261011.md`（审查基准与第 4 节）、`AGENTS.md`、现有 Workbench/progress；检查 `docs/engineering/audit_20261011_probe.py`、`docs/engineering/audit-20261011-observations.json` 是否存在。**不要假定这两份脚本/JSON 在本执行包中**。

## 只执行

1. 记录当前 HEAD 与 `git status --short`，与审查记录 `09efd344` 和“当时未提交工作区”作差异说明。
2. 确认 `/chat → SingleSupportAgent → Tool Contract → Provider/Action/RAG` 主链，**不恢复旧 Intent 或 Multi 路径**。
3. 如果本轮 HEAD 和依赖未变，可直接引用审查日 `uv lock --check`、pytest 150/2、Node 12 的**历史基线**；无需重新大范围取证。若已变，运行必要的轻量检查并明确记录新结果。
4. 审查脚本的 15 项观察是**缺陷成立证据**；其断言不能充当修复成功的测试。
5. 在**同一个 Workbench** 中新增/更新 A00-lite 的审查基线说明，审查文件状态保持 `verify`；Axx 实施仍未完成。

## DoD

一个短的核对结论：`HEAD`、工作区差异、已找到/缺失的证据路径、测试执行/未执行说明、下一轮 `A04/N01` 的测试入口。不要启动收费模型、容器或外部操作；不要自动进入 A04。
