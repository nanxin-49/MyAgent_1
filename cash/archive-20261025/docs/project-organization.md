# CartCare 文件组织与归档说明

2026-10-11 整理，基于 HEAD `09efd3443d2e7b6e03fba7d13fe660c483b30583`。当前核心阅读入口为 README、两份核心 Wiki 和 [EchoMind 差异说明](CartCare-vs-EchoMind.md)。Workbench / progress JSON 继续记录协作进度，hardening 是未来任务入口；测试、历史验收材料和运行依赖继续保留。

## 目录职责

| 路径 | 职责 |
|---|---|
| `api/`、`agents/`、`core/` | API、Single runtime、共享基础类与工具契约；部分旧 Multi 仍被历史实验使用 |
| `providers/`、`policies/`、`actions/` | 动态事实、确定性规则、审批及模拟执行 |
| `mcp/`、`memory/`、`monitor/`、`skills/` | 自研 RAG 工具层、记忆、监控、角色文本 |
| `demo/`、`tests/` | 演示 UI / fixture 生成与自动测试 |
| `evaluation/` | 评测代码、冻结数据集、版本化历史报告 |
| `docs/` | 工作台、hardening、验收记录、截图、差异和整理说明 |
| `wiki/` | 仅保留 CartCare定位与技术亮点、重点代码 |
| `config/`、`data/`、`logs/` | 部署配置、本地生成数据、日志；不整体移动活动数据 |
| `cash/` | 本机归档和可再生成缓存，全目录 Git / Docker 忽略 |

## 为什么这些入口留在根目录

`pyproject.toml` / `uv.lock` 是 uv 项目发现与依赖锁定入口，`.venv` 是已安装环境，移动它可能破坏可执行文件中的路径。`requirements*.txt` 被 Docker/CI 引用；Dockerfile、Compose、pytest.ini、.env / .env.example、AGENTS.md、.github 保持工具惯例和原调用位置。三个根目录 Shell 部署脚本仍有用途，继续保留原入口；本轮未执行它们的部署、删除或备份操作。

uv 缓存改由 `[tool.uv].cache-dir = "cash/cache/uv"` 配置；pytest 缓存由 `pytest.ini` 定位到 `cash/cache/pytest`。显式 UV_CACHE_DIR 会覆盖项目配置；旧本机环境变量需同步新路径。`.venv` 不移动，常用 `uv sync --dev` / `uv run ...` 命令不变。

## 归档和历史证据

旧学习文档、NexusOps、旧架构/技术亮点、使用指南、简历材料、文档中心、业务流程及其配图移至 `cash/wiki/`，避免旧 Multi 或企业运营定位与当前 Single 电商客服混淆。个人 `.idea` / `.DS_Store` 进入 `cash/local/`。旧 uv/pytest 缓存进入 `cash/cache/`。

旧 `data/chroma` 进入 `cash/legacy-data/chroma/`：当前两个 Chroma 构造器明确不使用 chroma_path，只使用 HttpClient；Compose 的 Chroma 服务持久化在 `chromadb-data` named volume。保留空 `data/chroma` 兼容原挂载；没有移动或清理外部数据卷。

根目录 5 份 T09 JSON 移至 `evaluation/reports/t09/`，3 份 FAQ 复验 JSON 移至 `evaluation/reports/rag_http/`，文件字节不变。T10/T11/T12 报告、快照和截图保留原位置，不把历史证据视为垃圾。历史 manifest 中旧文件名作为当时来源记录保留；新的路径映射见 [逐项清单及 SHA256](project-file-moves.json)。

新 fixture / online capture 默认写入 `data/evaluation/`，不再散落根目录，也不覆盖历史验收文件。具体复跑命令见 [evaluation README](../evaluation/README.md)。

## 版本控制与恢复

忽略配置的正确文件名是 `.gitignore`。`/cash/` 全部忽略，本地 `cash/README.md` 说明移动原因；本说明与清单继续版本化，便于新克隆理解清理结果。忽略规则不自动取消已跟踪文件，因此旧路径的删除也是本轮变更的一部分；提交时应包含删除、报告新位置和文档更新。尚未提交或推送。

新克隆不会获得本地归档；旧已跟踪材料可从整理前提交恢复，未跟踪材料只存在本机 cash。恢复时按清单复制单个文件，避免覆盖当前版本。缓存可重新生成，旧数据库不作为 PersistentClient fallback 恢复。

本轮保留用户已有 AGENTS.md 修改、progress JSON 的 A00-lite 记录与未跟踪 docs/hardening/。未开始任何 A 系列实现。主业务调用链未变；仅评测 CLI 默认文件路径改变。

## 验证

迁移时逐文件核对历史 JSON SHA256；清单记录非 uv 缓存文件哈希。验收命令为 `uv cache dir`、`uv lock --check`、`uv run python -m pytest -q`、`node --test tests/demo_ui.test.cjs`、`git diff --check`，并检查文档链接及 cash 忽略规则。实际结果记录在现有 progress JSON 的 verifyNotes 中。
