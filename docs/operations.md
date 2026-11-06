# 运行与部署

## Docker（推荐）

要求：Docker + Docker Compose；Python 3.12 由镜像提供。

```bash
cp .env.example .env
# 编辑 .env：至少填写 ANTHROPIC_API_KEY；按需修改 ANTHROPIC_MODEL / BASE_URL
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/ready
```

打开 <http://localhost:8000/demo>。应用容器 healthcheck 使用 `/ready`（Redis/Chroma 就绪）；nginx 使用 `/health`（进程存活）。

已有旧 `echomind-*` 容器时，先阅读 [命名迁移](naming.md)，停旧栈并保留数据卷，再启动新栈。

## 本地开发

Linux/macOS（bash）：

```bash
uv sync --dev
docker compose up -d redis chromadb

export REDIS_URL='redis://:cartcare123@localhost:6379/0'
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export PROMETHEUS_PORT=0

uv run python -m demo.prepare
export CARTCARE_BUSINESS_FIXTURE="$(pwd)/data/demo_business_fixture.json"
uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell 对应命令：

```powershell
uv sync --dev
docker compose up -d redis chromadb
$env:REDIS_URL = 'redis://:cartcare123@localhost:6379/0'
$env:CHROMA_HOST = 'localhost'
$env:CHROMA_PORT = '8001'
$env:PROMETHEUS_PORT = '0'
uv run python -m demo.prepare
$env:CARTCARE_BUSINESS_FIXTURE = (Resolve-Path data/demo_business_fixture.json).Path
uv run python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

如果 `.env` 里已有旧的 `REDIS_PASSWORD`，本地 `REDIS_URL` 要与实际 Redis 容器一致；不要为了改文档重置已有数据卷。Windows 若 6379/6380 被系统端口排除，可设置 `REDIS_PORT=16379` 启动 Redis，并把 `REDIS_URL` 端口同步改为 16379。

## 环境变量

新部署使用 `CARTCARE_*`；旧 `ECHOMIND_*` 仍作为回退：

| 新名称 | 旧回退 | 用途 |
| --- | --- | --- |
| `CARTCARE_SKILLS_DIR` | `ECHOMIND_SKILLS_DIR` | Skills 目录 |
| `CARTCARE_SKILLS_MAX_PROMPT_CHARS` | `ECHOMIND_SKILLS_MAX_PROMPT_CHARS` | Skills prompt 预算 |
| `CARTCARE_TOOL_TRACE_MAX` | `ECHOMIND_TOOL_TRACE_MAX` | 进程内 Trace 容量 |
| `CARTCARE_COMPOSER_MAX_TOKENS` | `ECHOMIND_COMPOSER_MAX_TOKENS` | 历史 Multi Composer |
| `CARTCARE_COMPOSER_TEMPERATURE` | `ECHOMIND_COMPOSER_TEMPERATURE` | 历史 Multi Composer |
| `CARTCARE_<AGENT>_MODEL` | `ECHOMIND_<AGENT>_MODEL` | 历史 Multi 角色模型 |

其他常用变量：`REDIS_URL`、`CHROMA_HOST`、`CHROMA_PORT`、`CARTCARE_BUSINESS_FIXTURE`、`CARTCARE_AUTH_MODE`、`APP_ENV`、`API_HOST`、`PROMETHEUS_PORT`。

## Demo Auth

受控本地 Demo 需要同时配置：

- `CARTCARE_AUTH_MODE=demo`
- `APP_ENV=development`
- `API_HOST=127.0.0.1`（或 `::1`）
- 回环客户端/Host
- `CARTCARE_DEMO_CREDENTIALS` 服务端 JSON 映射

凭据键是自行生成、至少 32 字符的 Bearer token；值包含 `subject_id`、`customer_id`、`roles`，reviewer 另设 `review_customers`。没有默认凭据。Demo 页面分开输入 customer/reviewer/admin token，不保存到浏览器存储；不要把 Demo 暴露到公网或公共反向代理。真实验证器通过 `app.state.auth_adapter` / FastAPI 依赖安装。

## 健康检查

- `GET /health`：liveness，只判断进程内 orchestrator 已初始化。
- `GET /ready`：readiness，检查 Redis ping + Chroma heartbeat；不调用模型，依赖未就绪返回 503。

## 知识库初始化

首次为空时从 `mcp/knowledge_assets/default_business_v1.json` 加载获批演示资料：

```bash
uv run python -m mcp.seed_demo_knowledge --check-assets
uv run python -m mcp.seed_demo_knowledge
```

Chroma 只通过外部 HTTP Server 访问；不支持嵌入式 fallback。非空集合的 `--reset` 需先停写、完整备份，并通过 `--backup-file` 核对快照。

## 测试

```bash
uv lock --check
uv run python -m pytest -q
node --check demo/static/demo.js
node --test tests/demo_ui.test.cjs
git diff --check
```

真实 Redis/Chroma 测试是 opt-in：`CARTCARE_TEST_LIVE_MEMORY=1` / `CARTCARE_TEST_LIVE_ACTIONS=1`，需要 `REDIS_URL`；真实 Chroma RAG 见 `tests/test_rag_http_integration.py`。

## Docker 常见问题

- **app 镜像构建失败，`python:3.12-slim` 元数据超时**：这是 Docker Hub 网络/代理问题，不是 Dockerfile 错误。可先使用本地 uvicorn 路径；修复 Docker Desktop 代理或预加载基础镜像后再 `docker compose up -d --build`。
- **6379/6380 端口 bind forbidden**：Windows 可能把端口加入排除范围。`netsh interface ipv4 show excludedportrange protocol=tcp` 查看；用 `REDIS_PORT=16379 docker compose up -d redis`，并把 `REDIS_URL` 端口同步改为 16379。
- **network pool overlaps**：旧 Compose 网络可能仍占用 `172.28.0.0/16`。确认旧容器已停止后删除旧网络，再启动新网络；不要删除数据卷。
- **旧 `echomind-app` 不在 Compose 管理内**：它可能单独占用 8000；停止/删除该容器后再启动当前 app。旧 `echomind-*` 容器迁移见 [命名迁移](naming.md)。

## 备份与迁移

- Redis/Chroma 数据卷由 Docker Compose 管理；`docker-deploy.sh backup` / `restore` 使用 `cartcare-redis` / `cartcare-chromadb` 容器名。
- 旧容器迁移见 [命名迁移](naming.md)；不要在没有备份时执行 `docker compose down -v`。
- 缓存目录由 `pyproject.toml` 配置；本机历史归档不属于公共仓库运行时依赖。

## 相关文档

- [架构与边界](architecture.md)
- [评测结果](evaluation.md)
- [已知限制](limitations.md)
- [命名迁移](naming.md)
