# 命名迁移（EchoMind → CartCare）

对外品牌统一为 **CartCare**。H5-2 将运行配置迁移到 `CARTCARE_*` / `cartcare-*`，并保留旧名称回退，避免已有 `.env` 和部署脚本立即失效。

## 环境变量

新名称优先；未设置时回退旧名称。

| 新名称 | 旧回退 |
| --- | --- |
| `CARTCARE_SKILLS_DIR` | `ECHOMIND_SKILLS_DIR` |
| `CARTCARE_SKILLS_MAX_PROMPT_CHARS` | `ECHOMIND_SKILLS_MAX_PROMPT_CHARS` |
| `CARTCARE_TOOL_TRACE_MAX` | `ECHOMIND_TOOL_TRACE_MAX` |
| `CARTCARE_COMPOSER_MAX_TOKENS` | `ECHOMIND_COMPOSER_MAX_TOKENS` |
| `CARTCARE_COMPOSER_TEMPERATURE` | `ECHOMIND_COMPOSER_TEMPERATURE` |
| `CARTCARE_<AGENT>_MODEL` | `ECHOMIND_<AGENT>_MODEL` |

`CARTCARE_AUTH_MODE`、`CARTCARE_DEMO_CREDENTIALS`、`CARTCARE_CLI_TOKEN`、`CARTCARE_BUSINESS_FIXTURE` 等原本就是 CartCare 名称，不变。

## 容器、网络与镜像

| 旧 | 新 |
| --- | --- |
| Compose service `echomind` | `cartcare` |
| `echomind-redis` | `cartcare-redis` |
| `echomind-chromadb` | `cartcare-chromadb` |
| `echomind-prometheus` | `cartcare-prometheus` |
| `echomind-app` | `cartcare-app` |
| `echomind-nginx` | `cartcare-nginx` |
| `echomind-network` | `cartcare-network` |
| nginx upstream `echomind_backend` / `echomind:8000` | `cartcare_backend` / `cartcare:8000` |
| Prometheus job/target `echomind-app` / `echomind:8000` | `cartcare-app` / `cartcare:8000` |
| Docker 用户 `echomind` | `cartcare` |
| `run-image.sh` 镜像/容器 `echomind` | `cartcare` / `cartcare-app` |

## 从旧栈迁移

1. **备份**：先执行 `docker-deploy.sh backup` 或手动备份 Redis/Chroma 数据卷；不要直接 `down -v`。
2. **停旧栈**：在旧版本目录执行 `docker compose down`；如果旧容器仍占用 6379/8001，可用 `docker rm -f echomind-redis echomind-chromadb echomind-app echomind-nginx echomind-prometheus`（先确认容器名）。
3. **保留数据**：Compose 项目名不变时，命名卷会复用；不要删除 `redis-data` / `chromadb-data` 卷。
4. **更新 `.env`**：新复制的 `.env.example` 使用 `REDIS_PASSWORD=cartcare123`；已有 `.env` 可保留旧密码，只要 `REDIS_URL` 与容器密码一致。
5. **启动新栈**：`docker compose up -d --build`；检查 `curl http://127.0.0.1:8000/ready` 和 `docker compose ps`。
6. **更新外部脚本/监控**：使用 `cartcare-*` 容器名、`cartcare:8000` 目标和新环境变量；旧 `ECHOMIND_*` 仍可回退一个迁移周期。

## 有意保留的历史名称

以下内容属于历史证据，不改写，避免伪造当时的运行条件：

- `evaluation/answerability/**` 的旧脚本仍检查 `echomind-app`、`echomind-redis`、`echomind-chromadb`；它们对应 2026-10 的旧镜像。
- `evaluation/topology_eval.py` 的旧 Multi 环境变量清单、`agents/agent_orchestrator.py` 的旧 Multi 路径保留旧名回退。
- `docs/CHANGELOG.md` 历史条目、`evaluation/reports/**` 历史报告中的旧名称保持原样。
- `echomind.h3_6.composite_cases` 是版本化评测数据 schema，不随品牌迁移；改动会破坏历史用例兼容性。

## 验证

```bash
uv run python -m pytest -q tests/test_naming_compat.py
docker compose config >/dev/null
```

`tests/test_naming_compat.py` 覆盖新/旧环境变量优先级、Compose 服务/容器/网络、nginx、Prometheus、部署脚本和 `.env.example`。

## 相关文档

- [运行与部署](operations.md)
- [已知限制](limitations.md)
- [架构与边界](architecture.md)
