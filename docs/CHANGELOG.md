# 变更日志

记录**每轮工作的主要修改、验证结果和提交**。任务定义与状态见 `CARTCARE_PLAN.md`；单任务完整证据见 `docs/reports/<TASK-ID>.md`；稳定协作规则见 `CLAUDE.md`。

写法：每轮追加一节，保留日期、任务 ID、改动文件、验证命令与结果、遗留问题、提交号。历史条目不改写；纠正用新条目说明。

---

## 2026-10-25 — 接手与启动验证（无任务 ID）

- **目的**：按交接文档核对项目能否从当前源码启动。
- **结果**：
  - HEAD `ea8ae67`；`uv lock --check` 53 packages；`pytest` **577 passed / 3 skipped / 1 warning**；Node **12 passed**。
  - 当前源码在 `127.0.0.1:8010` 启动成功，`/health` 为 Single 拓扑 `support_0`，知识库加载 6 个片段；`/demo`、`/docs`、`/openapi.json` 均 200。
  - 鉴权 401 生效；真实模型单次冒烟 200；确定性交接 `请帮我转人工客服` 创建记录且 0 次模型调用。
- **发现（未修改）**：
  - 运行中的 `echomind-app` 是 2026-09-27 旧镜像，仍是多 Agent 拓扑，不能作为当前源码运行证明。
  - `我要人工客服` 未被确定性门识别，模型调用 `request_handoff` 后被策略复核拒绝，返回“未创建记录”。fail-closed，但属明确请求漏创建，关联 `H1-1`。
  - Claude Code 会话 shell 注入 `ANTHROPIC_BASE_URL`，`load_dotenv()` 不覆盖，导致首次启动打到本地代理；用户本机环境不受影响。
- **文件**：未修改受版本控制文件；测试日志在 `logs/`（gitignored）。

## 2026-10-25 — 文档归档与仓库清理

- **改动**：
  - 新增分支 `claude/cartcare-harness`。
  - 47 个历史文件归档到 `cash/archive-20261025/`，清单见其 `MANIFEST.md`。
  - 保留 `docs/engineering/A05-rag-evaluation.md`（被测试 SHA256 锁定）；新建 `docs/reports/`。
  - 更新 `README.md`、两份核心 Wiki、`CLAUDE.md`、`CARTCARE_PLAN.md` 中的失效引用。
- **验证**：`pytest` **577 passed / 3 skipped**；Node **12 passed**；活动文档无死链。

## 2026-10-25 — cash 纳入版本库与变更日志

- **改动**：
  - 新增 `cash/README.md`；`.gitignore` 改为只忽略 `cash/` 下的缓存、CI 临时检出、旧数据、本机配置和凭据，跟踪 `cash/archive-20261025/` 与 `cash/wiki/`。
  - 新增本文件 `docs/CHANGELOG.md`，作为后续每轮修改的统一记录。
- **验证**：`git status` 确认无 `.env`、凭据或缓存进入暂存区；`pytest` 与 Node 结果不变。
- **提交**：见本次提交 `chore: archive superseded docs, track curated cash archive, add changelog`。

## 2026-10-25 — 根目录二次清理

- **改动**：
  - 删除空的 `scripts/`（无代码引用、未被跟踪）。
  - 删除 207 个 `__pycache__` 目录、`data/test-cache/` 和本次启动验证产生的临时日志。
  - 将 `data/default-kb-backups/`、`data/demo_docs/` 归档到 `cash/archive-20261025/data/`。
  - 删除 `docker-deploy.sh` 会自动重建的空挂载点目录 `config/alerts`、`config/grafana/*`、`config/nginx/ssl`。
  - 保留 `data/chroma`（Compose 挂载点）和 `logs/`（运行时目录）。
- **结果**：根目录剩 19 个目录，全部对应源码、运行数据、测试、评测或文档；无空目录（除上述两个运行时目录）。
- **验证**：`pytest` **577 passed / 3 skipped**；Node **12 passed**。
