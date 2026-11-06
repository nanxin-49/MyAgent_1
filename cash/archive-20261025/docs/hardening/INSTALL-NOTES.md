# V3 执行包的放置与合并（给仓库操作者）

1. **不要直接覆盖未提交文件**。先在原工作区运行 `git status --short`，备份/比对已有 `docs/hardening/` 和 `docs/engineering/project-audit-20261011.md`。本包仅提供建议替换文件，**没有更改 GitHub 仓库**。
2. 包含与 V2 **相同路径**的 `docs/hardening/README.md` 和 `tasks/A00-lite.md` ... `A07.md`，这是有意设计：沿用 A 系列编号与 Workbench，不新建第二套进度系统。
3. 额外文件：`docs/hardening/ISSUE-MAP.md` 只作为静态映射，`docs/hardening/INSTALL-NOTES.md` 供手动合并，`docs/engineering/project-audit-20261011.md` 为用户提供的审查报告原件副本。
4. 包**不包含** `audit_20261011_probe.py` 和 `audit-20261011-observations.json`（用户本次仅提供 Markdown 报告）。这两项应来自**执行本次审查的 Codex 工作区**；找不到时不要伪造，后续 Codex 可按审查问题复现等价单测。
5. 推荐首先让 Codex 只读检查当前文件差异，确认哪些是用户自己的未提交修改，然后人工决定是否替换此包对应文档。生产逻辑不在包中，不影响 T01–T12。
6. 每轮只向 Codex 指定一个子任务，例如 `A04/N01`，不要发送“执行整个 A04 或 V3 计划”。
