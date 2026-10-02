# CartCare Eval

## Deterministic system suite (T09)

From the repository root with Python 3.12:

```bash
uv sync --dev
uv run python -m evaluation.run_system_eval --output system_eval_report.json
```

To compare with a saved JSON report, add `--baseline previous_report.json`. Keep that baseline in a separate file from `--output`. A nonzero safety rate is an immediate regression; ordinary positive metrics flag drops greater than 5%.

`system_cases.json` holds ten traceable e-commerce support scenarios with structured expectations. The runner invokes the real Tool Contract, read Providers, PolicyEngine, ActionService and RAG ToolManager against **isolated test/demo fixtures**. It does not call a model, Chroma server, payment gateway or external shop. The report records every case, expected/observed values, metric numerator/denominator, timing and a 0.20/0.35/0.50/0.70 threshold sweep. The production RAG threshold remains 0.35.

`null` means unmeasured. The offline replay scripts tool requests; it cannot measure Agent intent accuracy, tool selection, argument selection, unsupported-request escalation, answer grounding or live `/chat` task success. The component replay scenario score measures only explicit checks. The threshold sweep uses a small fixed illustrative distance set, not a production corpus.

Tool metrics distinguish read/write/dangerous risk and report `invocation_success_rate`, `expected_business_outcome_rate`, and `technical_failure_rate` separately. The former 6/8 execution score counted an expected policy denial and ownership denial as failures; both are valid business outcomes. The current component replay reports 8/8 invoked, 8/8 expected business outcomes, and 0/8 technical failures. Policy violation, ownership bypass, missed approval, approval bypass and duplicate action have zero-tolerance regression gates. LLM-as-Judge is limited to relevance, clarity, completeness and helpfulness.

## T09 online `/chat` evidence

The 2026-09-30 run used the current local API on port 8003, a real configured model, Redis and Chroma HTTP, with an isolated **demo** business fixture. It captured all ten scenarios in `t09_online_observations_final.json`, including full ChatResponse, request ID, routing, Tool Trace, RAG status/citations, and policy/action result when present. `t09_online_report.json` is the scored online Agent report. `system_eval_report.json` remains the separate component replay report.

To repeat the run, create the dated demo fixture with `uv run python -m evaluation.prepare_online_eval`, start the current API with `CARTCARE_BUSINESS_FIXTURE` pointing to that fixture and the configured Redis/Chroma services, then run:

```bash
uv run python -m evaluation.capture_online_eval --base-url http://127.0.0.1:8003 --cases t09_online_cases.json --output t09_online_observations_final.json
uv run python -m evaluation.agent_trace_eval --cases t09_online_cases.json --observations t09_online_observations_final.json --output t09_online_report.json
```

The run observed intent 7/10, expected Tool selection 7/10, arguments 6/6 when the target Tool was invoked, unnecessary Tool calls 5/10, and strict end-to-end scenario success 6/10. Unsupported-request escalation was observed in 1/1, although its intent label and Tool use missed the case expectations. The FAQ RAG case returned `degraded`, with citation and grounding both 0/1. Online Agent metrics are a single demo-environment sample, not production quality estimates. The 0.35 runtime threshold was unchanged.

The original 2026-09-30 T09 sample is intentionally unchanged: Chroma's thin HTTP client lacked an embedding function then, and its legacy collection lacked T07 provenance. A separate 2026-10-02 RAG integration fix added explicit versioned vectors and a new demo collection. `rag_faq_online_observation_final.json` and `rag_faq_online_verification.json` hold the later FAQ-only `/chat` evidence; do not recalculate the original ten-case baseline from that single retest. Fallback text still has no citation.

## Online baseline

本目录保存固定测试集和可重复的真实 HTTP Baseline Runner。Runner 默认调用生产入口 POST /chat，并在每个响应后读取 /trace/tool/{request_id}。

## 运行

在 CartCare 服务和 Redis/Chroma 已启动后，从仓库根目录执行：

    uv run python evaluation/run_baseline.py --base-url http://localhost:8000

可选参数：

    --cases evaluation/baseline_cases.json
    --output-dir evaluation/reports
    --timeout 90

输出：

- evaluation/reports/baseline_raw.json：逐 Case 的机器可读结果；
- evaluation/reports/baseline_report.md：汇总指标、Case Matrix、失败分类和运行限制。

服务不可用时，Runner 会为每条 Case 保存 status=blocked 和原始连接错误，不会用 Mock 结果冒充 E2E 结果。

`POST /eval/run` separately runs IntentRecognizer accuracy/Macro-F1 and Agent replies with the subjective LLM judge. This older HTTP baseline includes legacy non-commerce cases; align it with T09 scenarios before comparing online Agent quality with the component replay.

The T09 capture and scoring commands above operate on the ten commerce cases. Missing Policy, execution-count or retrieval-hit evidence remains unmeasured. Capture requests may trigger simulated demo refund/cancel actions, so use an isolated fixture.

## 本地测试环境

生产依赖和开发/测试依赖以 `pyproject.toml` 和 `uv.lock` 为准。`requirements*.txt` 仅作为 Docker/CI/pip 兼容入口。

- `requirements.txt`：运行 CartCare API 所需的生产依赖；
- `requirements-dev.txt`：继承生产依赖并增加 pytest。

在仓库根目录执行：

    uv lock --check
    uv run python -m pytest -q
    git diff --check

Docker 开发镜像包含测试依赖，生产镜像不包含 pytest：

    docker build --target development -t cartcare-dev .
    docker run --rm --entrypoint python cartcare-dev -m pytest -q

## Tool Trace 测试

项目现有测试使用 pytest 风格函数：

    python -m pytest -q

本轮新增的固定 Fake Client 场景是：

    tool_use -> 工具执行 -> 最终文本

验收同时检查最终回答、工具调用次数、tools_used 和完整 tool_traces。
