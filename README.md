# CartCare

E-commerce Support Agent

CartCare 是一个面向电商客服场景的可观测、多 Agent 编排运行时。当前代码已经接通记忆、意图识别、路由、Agent 工具调用、Skills 注入和知识库检索；T02 已建立 Product/Order/Inventory/Logistics/Refund 的只读 Provider 合约与测试 Mock，但尚未接入 /chat、Agent Tool 或真实外部电商系统。Policy Engine、HITL 和退款执行仍是后续任务。

## 当前真实主链路

POST /chat 的实际调用关系如下：

~~~text
请求
  -> MemoryManager.get_context()
  -> AgentOrchestrator.recognize_intent()
  -> 构造 Request（intent / entities / urgency / history / memory context）
  -> AgentOrchestrator.run()
       -> 生成 RoutingDecision
       -> General / Technical / Billing / Escalation Agent
       -> LLM 回复；必要时按 Agent 白名单执行工具调用（最多 3 轮）
            -> search_knowledge_base（Agent 按需触发的 RAG 工具）
  -> 写回用户消息和 Agent 回复
  -> 异步更新用户画像
  -> 返回 ChatResponse（路由、工具、升级和延迟信息）
~~~

RAG 不是 /chat 的 API 前置固定阶段。Agent 是否调用 search_knowledge_base 由模型在角色工具白名单内决定；knowledge_used 只有在该工具实际被调用时才为 true。需要直接调试查询改写、并行召回、去重和重排时使用 POST /search。

Monitor 和 Eval 也不在每次 /chat 内同步运行：Monitor 在应用生命周期中后台采集统计并更新路由惩罚，POST /eval/run 才会显式启动意图和端到端评测。

## 当前能力边界

- **Agent / Intent**：IntentRecognizer 输出 intent、intent_group、confidence、urgency 和 entities；Orchestrator 路由到四类 Agent，复杂请求可主辅并行。
- **Tool**：agents/tools.py 提供确定性的请求分析、字段检查、技术排障、金额比较、人工交接摘要和共享 RAG 工具；没有伪造订单或退款动作。
- **Business Provider**：providers/ 定义 Product、Order、Inventory、Logistics、Refund 的结构化只读 Provider 和 Backend Protocol；当前仅有明确标注的 JSON fixture 内存 Mock，未接入 Agent/API。
- **RAG**：mcp/knowledge_base.py + ChromaDB 提供知识库；mcp/tool_manager.py 是项目自研的本地工具管理器，提供参数校验、缓存、超时、熔断、fallback、查询改写和重排，不是标准 MCP SDK/transport 接入。
- **Memory**：Redis 保存工作记忆，ChromaDB 保存情景摘要和用户画像；每轮 /chat 回写消息，画像更新异步执行。
- **Monitor / Trace**：/monitor、/metrics 和 /trace/* 暴露运行时统计与工具 trace；Monitor 的后台任务会把表现反馈给路由评分。
- **Eval**：/eval/run 独立运行意图准确率、Macro-F1、LLM-as-Judge 和回归检查，不是 /chat 的隐式步骤。
- **未接入的业务闭环**：Provider 目前只提供动态事实读取；真实外部系统、Agent/API Tool、退款资格、Policy Gate、审批、写操作和幂等执行链路仍未接入。

## 你可以先看什么

- [技术亮点](wiki/技术亮点.md)
- [重点代码](wiki/重点代码.md)
- [业务流程说明](wiki/业务流程说明.md)
- [完整使用指南](wiki/完整使用指南.md)
- [Workbench 事实基线](docs/CartCare-Codex-Workbench.html)

## 快速开始

### 1. 准备环境

- Docker
- Docker Compose
- ANTHROPIC_API_KEY

如果使用兼容 Anthropic 协议的第三方模型服务，也可以配置：

~~~env
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro
ANTHROPIC_API_KEY=your_key
~~~

### 2. 配置环境变量

~~~bash
cp .env.example .env
~~~

至少配置：

~~~env
ANTHROPIC_API_KEY=your_api_key
~~~

不要把真实 API key 写入源码或 Git。

### 3. 启动服务

~~~bash
docker compose up -d --build
docker compose ps
docker compose logs -f echomind
~~~

访问：

- API：http://localhost:8000
- Swagger：http://localhost:8000/docs
- Nginx：http://localhost
- Health：http://localhost:8000/health

## API 入口

| 入口 | 作用 |
|---|---|
| POST /chat | 真实客服主链路：记忆、意图、路由、Agent/Tool、回写 |
| POST /search | 独立调试 RAG 查询改写、召回、去重和重排 |
| POST /knowledge/add / POST /knowledge/upload | 写入知识库文档 |
| GET /knowledge/stats | 查看知识库片段数 |
| GET /skills / POST /skills/reload | 查看或热加载 Skills |
| GET /monitor / GET /metrics | 查看运行时统计和 Prometheus 指标 |
| GET /trace/tool/{request_id} / GET /trace/tools | 查看工具调用 trace |
| POST /eval/run | 显式运行意图和端到端评测 |

## 代码结构

~~~text
api/main.py                    FastAPI 入口和生命周期装配
agents/agent_orchestrator.py  意图后的路由、Agent 执行和 tool loop
agents/tools.py               Agent 工具白名单及确定性 handler
providers/                    动态业务事实 Provider、Backend Protocol 和测试 Mock
core/intent_recognizer.py     LLM / Embedding / Pattern 意图融合
core/skill_loader.py          Skills 加载和 prompt 注入
memory/conversation_memory.py Redis + ChromaDB 记忆
mcp/tool_manager.py           自研工具管理器和 RAG 调用治理
mcp/knowledge_base.py         ChromaDB 知识库
monitor/performance_monitor.py 后台统计和路由惩罚
evaluation/evaluator.py       独立评测器
tests/                        pytest 测试与环境 smoke test
~~~

## 测试

开发和测试依赖单独声明在 requirements-dev.txt，其中继承生产依赖并额外安装 pytest：

~~~bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
~~~

容器测试：

~~~bash
docker build --target development -t cartcare-dev .
docker run --rm cartcare-dev python -m pytest -q
~~~

## 项目方向

下一阶段优先把 Provider 接入只读业务 Tool，再补齐读写 Tool 分层、Policy Gate、HITL、幂等和专项 Eval。所有动态订单、物流、库存、支付和退款事实都应来自 Provider/API/DB；RAG 只承载静态或半静态政策知识。
