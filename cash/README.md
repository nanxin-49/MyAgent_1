# cash/ — 本机归档与缓存

本目录保存**不再参与当前开发、但需要留档**的材料，以及可再生的本机缓存。它不是运行时依赖，也不进入 Docker 镜像（`.dockerignore` 已排除 `cash/`）。

## 目录结构

| 路径 | 是否跟踪 | 内容 |
| --- | --- | --- |
| `archive-20261025/` | 是 | 2026-10-25 文档整理归档：旧 Workbench、progress JSON、A 系列 hardening、旧工程说明、T12 记录、演示截图、交接文档、一次性脚本、旧演示文档与知识库发布备份。清单见 `archive-20261025/MANIFEST.md` |
| `wiki/` | 是 | 旧 Wiki 与配图历史版本 |
| `cache/` | 否 | uv / pytest 缓存（可删除后重建） |
| `a07-ci-repro/` | 否 | A07 CI 复现用的独立检出与临时运行目录（约 165 MB） |
| `legacy-data/` | 否 | 旧嵌入式 Chroma 数据 |
| `local/` | 否 | 本机 IDE 等个人配置 |
| `a05-chat-e2e-20261014/` | 否 | 真实 E2E 的本地凭据（`credentials.json`），禁止提交 |

## 规则

1. 只把**已确认不再参与运行、但需要留档**的文件移入本目录，并在对应归档目录的 `MANIFEST.md` 记录来源与恢复方法。
2. 不把 `.env`、Bearer token、真实 API key、Redis/Chroma 凭据放入跟踪范围。
3. 缓存和临时检出继续由 `.gitignore` 排除；需要清理时直接删除对应子目录，不影响版本库。
4. 需要恢复单个历史文档时，优先从 Git 历史取回；归档副本只作为参考。

## 恢复示例

```bash
# 从 Git 历史恢复某个归档前的文档
git restore -s main -- docs/engineering/N05-action-memory-consistency.md

# 把整个归档目录临时放回 docs/
cp -r cash/archive-20261025/docs/* docs/
```

归档不等于当前事实。当前调用路径、任务和状态以代码、`CLAUDE.md`、`CARTCARE_PLAN.md` 和 `docs/reports/` 为准。
