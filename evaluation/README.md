# CartCare As-Is Baseline

本目录保存固定测试集和可重复的真实 HTTP Baseline Runner。Runner 默认调用生产入口 POST /chat，并在每个响应后读取 /trace/tool/{request_id}。

## 运行

在 CartCare 服务和 Redis/Chroma 已启动后，从仓库根目录执行：

    python evaluation/run_baseline.py --base-url http://localhost:8000

可选参数：

    --cases evaluation/baseline_cases.json
    --output-dir evaluation/reports
    --timeout 90

输出：

- evaluation/reports/baseline_raw.json：逐 Case 的机器可读结果；
- evaluation/reports/baseline_report.md：汇总指标、Case Matrix、失败分类和运行限制。

服务不可用时，Runner 会为每条 Case 保存 status=blocked 和原始连接错误，不会用 Mock 结果冒充 E2E 结果。

## 本地测试环境

生产依赖和开发/测试依赖分开声明：

- `requirements.txt`：运行 CartCare API 所需的生产依赖；
- `requirements-dev.txt`：继承生产依赖并增加 pytest。

在仓库根目录创建或激活虚拟环境后执行：

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

Docker 开发镜像包含测试依赖，生产镜像不包含 pytest：

    docker build --target development -t cartcare-dev .
    docker run --rm cartcare-dev python -m pytest -q

## Tool Trace 测试

项目现有测试使用 pytest 风格函数：

    python -m pytest -q

本轮新增的固定 Fake Client 场景是：

    tool_use -> 工具执行 -> 最终文本

验收同时检查最终回答、工具调用次数、tools_used 和完整 tool_traces。
