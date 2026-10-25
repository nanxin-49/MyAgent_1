# 归档清单 2026-10-25

- 仓库：`E:\AAA_NEED\Echomind_new\EchoMind`
- 分支：`claude/cartcare-harness`（基于 `main` / `ea8ae67`）
- 归档目标：本机 `cash/`（`.gitignore` 中已忽略 `/cash/`，不进入版本库、镜像或远端）
- 原因：`CARTCARE_PLAN.md` + `CLAUDE.md` 取代旧的 A 系列 / V3 hardening 协议；旧 Workbench、进度 JSON、工程说明与一次性记录不再参与后续开发。

## docs/ → cash/archive-20261025/docs/

| 原路径 | 说明 |
| --- | --- |
| `CartCare-Codex-Workbench.html` | 旧项目工作台 |
| `cartcare-workbench-progress.json` | 旧进度 JSON |
| `CartCare-vs-EchoMind.md` | 旧品牌演进对照 |
| `project-organization.md` | 旧目录整理说明 |
| `project-file-moves.json` | 旧迁移清单 |
| `t12-trace-demo-validation.md` | T12 验证记录 |
| `t12-demo-observations.json` | T12 观察数据 |
| `demo-screenshots/` | T12 演示截图（4 张） |
| `CartCare-Agent-Handoff-20261025.md` | 本次交接快照 |
| `hardening/` | V3 任务入口、任务文件、路线图、安装说明 |
| `engineering/`（除 `A05-rag-evaluation.md`） | A02–A10、N04–N07、ADR、审计与观察数据 |

`docs/engineering/A05-rag-evaluation.md` **保留原位**：`evaluation/rag_quality/gold_v2_candidate_validation.json` 的 `protected_sha256` 锁定该文件，`tests/test_rag_gold_v2_candidate.py` 会校验。移动它会使测试失败。

## 根目录缓存 → cash/cache/pytest-historical/

`.pytest-cache-a05`、`.pytest-cache-a05-dev`、`.pytest-cache-a05-freeze`、`.pytest-cache-a05-gate`、`.pytest-cache-a05-v2`、`.pytest-cache-n06`、`.pytest-cache-n07`。

## data/ → cash/archive-20261025/data/

`stage-pr-body.md`、`stage_pr_api.py`、`t12-workbench-check.js`（一次性脚本/草稿）；同时删除 `data/.DS_Store`。

## 保留在版本库

- 根目录：`README.md`、`CLAUDE.md`、`CARTCARE_PLAN.md`、`settings.json`、构建/部署/依赖入口。
- `docs/reports/`：新任务证据目录。
- `docs/engineering/A05-rag-evaluation.md`：测试 hash 锁定。
- `evaluation/`：评测代码、数据集与历史报告；其中 `evaluation/reports/` 下 4 个路径被测试直接读取，不能归档。
- `wiki/`：保留两份核心文档（已更新失效链接）。

## 恢复方法

单文件：从 `main` 恢复，例如 `git restore -s main -- docs/engineering/N05-action-memory-consistency.md`。
整目录：`mv cash/archive-20261025/docs/* docs/`，再按需 `git add`。
