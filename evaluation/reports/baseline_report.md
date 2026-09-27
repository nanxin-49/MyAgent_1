# EchoMind As-Is Baseline Report

> 本报告由 evaluation/run_baseline.py 生成。固定 Case 通过真实 HTTP POST /chat 运行；服务不可用时保留 BLOCKED，不用 Mock 结果替代。

## A. Environment

- 测试时间：2026-09-27T04:36:22.548659+00:00
- Git commit：2592897ee8deb212ba4028d533e399d4b2bc7168
- 运行方式：http://localhost:8000 /chat
- 实际模型：N/A: not exposed by public API
- /health：{"status": "ok", "agents": {"general_0": {"total": 0, "success_rate": 1.0, "avg_ms": 0.0, "monitor_penalty": 0.0, "routing_score": 1.0, "role": "通用客服分诊与首轮接待", "workflow": ["复述诉求", "判断业务范围", "直接回答或补充必要信息", "给出下一步"], "tool_scope": ["search_knowledge_base", "inspect_request_context", "suggest_required_fields"], "available_tools": ["search_knowledge_base", "inspect_request_context", "suggest_required_fields"], "model": "deepseek-flash"}, "technical_0": {"total": 1, "success_rate": 1.0, "avg_ms": 11109.8, "monitor_penalty": 0.4, "routing_score": 0.435, "role": "技术故障诊断与排障", "workflow": ["确认现象", "判断影响范围", "按网络/权限/配置/依赖排查", "给出验证方式", "判断升级条件"], "tool_scope": ["search_knowledge_base", "lookup_error_code", "build_diagnostic_plan"], "available_tools": ["search_knowledge_base", "lookup_error_code", "build_diagnostic_plan"], "model": "deepseek-flash"}, "billing_0": {"total": 0, "success_rate": 1.0, "avg_ms": 0.0, "monitor_penalty": 0.0, "routing_score": 1.0, "role": "账单核验与售后处理", "workflow": ["确认账单场景", "收集必要核验字段", "区分订单/实付/退款金额", "说明处理路径与时效", "判断是否升级"], "tool_scope": ["search_knowledge_base", "check_billing_fields", "compare_amounts"], "available_tools": ["search_knowledge_base", "check_billing_fields", "compare_amounts"], "model": "deepseek-flash"}, "escalation_0": {"total": 0, "success_rate": 1.0, "avg_ms": 0.0, "monitor_penalty": 0.0, "routing_score": 1.0, "role": "人工升级与交接", "workflow": ["确认升级原因", "整理已知信息", "标记优先级", "生成交接摘要"], "tool_scope": ["search_knowledge_base", "create_handoff_summary"], "available_tools": ["search_knowledge_base", "create_handoff_summary"], "model": "deepseek-flash"}}}
- Redis / Chroma：N/A: runtime health endpoint unavailable
- Case 数量：计划 18，可运行 18，阻塞 0

## B. Observability Fix

- 根因：BaseAgent._call_llm 的最终文本分支只写入 _last_tools_used，没有把本轮 tool_traces 写入 _last_tool_traces。
- 修复：最终文本返回前同步保存 _last_tool_traces；没有改变工具白名单、轮数、消息顺序或最终回答生成逻辑。
- 新增测试：成功 tool_use → 工具成功 → 最终文本，以及工具后 provider 失败的固定 Fake Client 测试，检查工具参数、成功状态、延迟和 trace 字段。

## C. Baseline Summary

| Metric | Value | Notes |
|---|---:|---|
| Intent Accuracy | 0.8889 | 仅统计实际收到响应的 Case |
| Intent Macro-F1 | 0.7778 | 仅统计实际收到响应的 Case |
| Primary Routing Accuracy | 0.9444 | 按 Case 期望 primary_agent |
| Supporting Precision / Recall / F1 | 1.0 / 0.5 / 0.6667 | 不把最终回答替代路由判断 |
| Multi-Agent Trigger Rate | 0.0556 | 实际 agent_types/supporting_agents |
| Expected Multi-Agent Recall | 0.5 | 仅统计期望 Multi-Agent 的 Case |
| Unexpected Multi-Agent Rate | 0.0 | 期望单 Agent 但实际并行 |
| Required RAG Recall | 1.0 | required Case 是否调用 search_knowledge_base |
| Unnecessary RAG Rate | 0.0 | skip Case 的实际调用率 |
| Tool Expected Hit Rate | 0.5556 | 使用 API tools_used / trace |
| Unexpected Tool Rate | 0.6364 | expected_tools 为空但实际调用工具 |
| Tool Trace Success Rate | 1.0 | 当前公开 trace 中成功调用比例 |
| Escalation Accuracy | 0.8 | 仅统计 required/forbidden |
| Escalation FP / FN | 0.25 / 0.0 | 按 Case policy 统计 |
| Average / Median / P95 Latency | 7414.3 / 7176.4 / 19015.4 ms | 样本量可能很小 |
| Query Rewrite Success Rate | N/A: not exposed by public trace | 公开 API 未暴露 |
| Rerank Success Rate | N/A: not exposed by public trace | 公开 API 未暴露 |

## D. Case Matrix

| ID | Scenario | Intent | Primary | Supporting | Multi-Agent | RAG | Tools | Escalation | Status | Latency ms |
|---|---|---|---|---|---:|---|---|---|---|---:|
| technical_login_01 | single_technical | technical_login | technical | - | False | True | lookup_error_code, search_knowledge_base | True | passed | 10326.8 |
| technical_crash_01 | single_technical | technical_crash | technical | - | False | True | build_diagnostic_plan, search_knowledge_base | False | failed | 8954.2 |
| billing_duplicate_01 | single_billing | payment_issue | billing | - | False | True | check_billing_fields, search_knowledge_base | False | failed | 12482.5 |
| billing_refund_01 | single_billing | refund | billing | - | False | True | check_billing_fields, search_knowledge_base | True | passed | 6239.7 |
| billing_invoice_01 | single_billing | invoice | billing | - | False | True | check_billing_fields, search_knowledge_base | True | failed | 7762.2 |
| general_logistics_01 | general | logistics | general | - | False | True | search_knowledge_base, inspect_request_context | False | failed | 6385.3 |
| general_greeting_01 | general | greeting | general | - | False | False | - | False | passed | 2618.9 |
| compound_technical_billing_01 | compound | technical_login | technical | - | False | True | lookup_error_code, search_knowledge_base, search_knowledge_base, build_diagnostic_plan | True | failed | 15491.0 |
| compound_technical_billing_02 | compound | technical_login | technical | billing | True | True | lookup_error_code, search_knowledge_base, build_diagnostic_plan, check_billing_fields | True | failed | 20791.2 |
| rag_refund_eta_01 | rag_required | refund | billing | - | False | True | search_knowledge_base, check_billing_fields | True | passed | 8540.6 |
| rag_membership_01 | rag_required | query | general | - | False | True | search_knowledge_base, inspect_request_context | False | passed | 5967.5 |
| rag_skip_greeting_01 | rag_skip | greeting | general | - | False | False | - | False | passed | 1836.4 |
| knowledge_gap_01 | knowledge_gap | technical | technical | - | False | True | search_knowledge_base, search_knowledge_base | False | failed | 13316.1 |
| clarification_01 | clarification | other | general | - | False | False | - | False | passed | 1620.1 |
| escalation_human_01 | escalation | human_handoff | escalation | - | False | False | - | True | passed | 1022.3 |
| escalation_refund_01 | escalation | refund | billing | - | False | True | check_billing_fields, search_knowledge_base | True | failed | 10088.3 |
| escalation_false_positive_01 | escalation_false_positive | technical_login | technical | - | False | True | lookup_error_code, search_knowledge_base | True | failed | 11867.2 |
| memory_continuity_01 | memory_multiturn | logistics | general | - | False | True | search_knowledge_base, suggest_required_fields | True | failed | 17857.1 |

## E. Failure Breakdown

| Failure Type | Count |
|---|---:|
| Tool Selection Error | 8 |
| Intent Error | 2 |
| Routing Error | 2 |
| Escalation Error | 1 |
| Multi-Agent Error | 1 |

## F. Representative Failures

### technical_crash_01

- Expected：{"intent": "technical_crash", "primary_agent": "technical", "supporting_agents": [], "multi_agent": false, "rag": "optional", "expected_tools": [], "escalation": "optional"}
- Actual：{"intent": "technical_crash", "intent_group": "technical", "intent_confidence": 0.736, "intent_source_scores": {"llm": 0.98, "embedding": 0.18549555830406733, "pattern": 0.5}, "entities": {"order_id": [], "product": [], "date": [], "amount": [], "error_code": []}, "urgency": "N/A", "primary_agent": "technical", "supporting_agents": [], "agent_types": ["technical"], "routing_confidence": 0.93, "routing_reason": "intent=technical_crash, group=technical, primary=technical, supporting=none, scores=[technical=0.93, general=0.10, billing=0.00]", "multi_agent": false, "tools_used": ["build_diagnostic_plan", "search_knowledge_base"], "tool_traces": [{"agent_type": "technical", "tool_name": "build_diagnostic_plan", "tool_use_id": "call_00_NPT18TRcCKtN2JoWqlXZ1202", "input": {"environment": "App", "reproduced": true}, "success": true, "result_success": null, "latency_ms": 0.0, "cached": false, "reranked": false, "error": ""}, {"agent_type": "technical", "tool_name": "search_knowledge_base", "tool_use_id": "call_01_w3v1Vuey2wu4jYaRUvx09137", "input": {"query": "App 启动崩溃 闪退 排查 常见原因", "top_k": 5}, "success": true, "result_success": true, "latency_ms": 1875.0, "cached": false, "reranked": true, 
- Checks：{"intent": true, "primary_routing": true, "supporting_routing": true, "multi_agent": true, "rag_trigger": null, "tool_selection": false, "escalation": null}
- Errors：无

### billing_duplicate_01

- Expected：{"intent": "payment_issue", "primary_agent": "billing", "supporting_agents": [], "multi_agent": false, "rag": "optional", "expected_tools": ["compare_amounts"], "escalation": "optional"}
- Actual：{"intent": "payment_issue", "intent_group": "billing", "intent_confidence": 0.8381, "intent_source_scores": {"llm": 0.95, "embedding": 0.6155870112510924, "pattern": 0.5}, "entities": {"order_id": [], "product": [], "date": [], "amount": ["99 元"], "error_code": []}, "urgency": "N/A", "primary_agent": "billing", "supporting_agents": [], "agent_types": ["billing"], "routing_confidence": 1.0, "routing_reason": "intent=payment_issue, group=billing, primary=billing, supporting=none, scores=[billing=1.08, general=0.10, technical=0.00]", "multi_agent": false, "tools_used": ["check_billing_fields", "search_knowledge_base"], "tool_traces": [{"agent_type": "billing", "tool_name": "check_billing_fields", "tool_use_id": "call_00_4KejXF6uUTvBlDZeh7cR8932", "input": {"payment_channel": "未知"}, "success": true, "result_success": null, "latency_ms": 0.0, "cached": false, "reranked": false, "error": ""}, {"agent_type": "billing", "tool_name": "search_knowledge_base", "tool_use_id": "call_01_IiQFneu6dUeCDIbJU2Wl9814", "input": {"query": "重复扣款 核实 处理流程 退款", "top_k": 3}, "success": true, "result_success": true, "latency_ms": 3850.7, "cached": false, "reranked": true, "error": ""}], "knowledge_used": tru
- Checks：{"intent": true, "primary_routing": true, "supporting_routing": true, "multi_agent": true, "rag_trigger": null, "tool_selection": false, "escalation": null}
- Errors：无

### billing_invoice_01

- Expected：{"intent": "invoice", "primary_agent": "billing", "supporting_agents": [], "multi_agent": false, "rag": "optional", "expected_tools": [], "escalation": "optional"}
- Actual：{"intent": "invoice", "intent_group": "billing", "intent_confidence": 0.715, "intent_source_scores": {"llm": 0.95, "embedding": 0.23814483610392007, "pattern": 0.5}, "entities": {"order_id": [], "product": [], "date": [], "amount": [], "error_code": []}, "urgency": "N/A", "primary_agent": "billing", "supporting_agents": [], "agent_types": ["billing"], "routing_confidence": 0.93, "routing_reason": "intent=invoice, group=billing, primary=billing, supporting=none, scores=[billing=0.93, general=0.10, technical=0.00]", "multi_agent": false, "tools_used": ["check_billing_fields", "search_knowledge_base"], "tool_traces": [{"agent_type": "billing", "tool_name": "check_billing_fields", "tool_use_id": "call_00_qUVn2JELdYqKJalyPcyi2423", "input": {}, "success": true, "result_success": null, "latency_ms": 0.0, "cached": false, "reranked": false, "error": ""}, {"agent_type": "billing", "tool_name": "search_knowledge_base", "tool_use_id": "call_01_VCKF4jstfnJFSGniLQdi2309", "input": {"query": "发票开具 开票时间 发票类型 抬头 税号 人工审核 作废重开", "top_k": 5}, "success": true, "result_success": true, "latency_ms": 1760.6, "cached": false, "reranked": true, "error": ""}], "knowledge_used": true, "search_knowledge_base
- Checks：{"intent": true, "primary_routing": true, "supporting_routing": true, "multi_agent": true, "rag_trigger": null, "tool_selection": false, "escalation": null}
- Errors：无

### general_logistics_01

- Expected：{"intent": "logistics", "primary_agent": "general", "supporting_agents": [], "multi_agent": false, "rag": "optional", "expected_tools": [], "escalation": "optional"}
- Actual：{"intent": "logistics", "intent_group": "query", "intent_confidence": 0.665, "intent_source_scores": {"llm": 0.95, "embedding": 0.3142936330963102, "pattern": 0.5}, "entities": {"order_id": [], "product": [], "date": [], "amount": [], "error_code": []}, "urgency": "N/A", "primary_agent": "general", "supporting_agents": [], "agent_types": ["general"], "routing_confidence": 0.77, "routing_reason": "intent=logistics, group=query, primary=general, supporting=none, scores=[general=0.77, technical=0.00, billing=0.00]", "multi_agent": false, "tools_used": ["search_knowledge_base", "inspect_request_context"], "tool_traces": [{"agent_type": "general", "tool_name": "search_knowledge_base", "tool_use_id": "call_00_YtcVwquQOLrGHIObCJyt8408", "input": {"query": "订单发货后 配送时效 多久能收到 物流时间", "top_k": 5}, "success": true, "result_success": true, "latency_ms": 2166.0, "cached": false, "reranked": true, "error": ""}, {"agent_type": "general", "tool_name": "inspect_request_context", "tool_use_id": "call_01_fCG16dGHeNVDmnBWfo4U4292", "input": {"focus": "logistics 物流配送时效"}, "success": true, "result_success": null, "latency_ms": 0.0, "cached": false, "reranked": false, "error": ""}], "knowledge_used": true,
- Checks：{"intent": true, "primary_routing": true, "supporting_routing": true, "multi_agent": true, "rag_trigger": null, "tool_selection": false, "escalation": null}
- Errors：无

### compound_technical_billing_01

- Expected：{"intent": "technical_login", "primary_agent": "technical", "supporting_agents": ["billing"], "multi_agent": true, "rag": "optional", "expected_tools": [], "escalation": "optional"}
- Actual：{"intent": "technical_login", "intent_group": "technical", "intent_confidence": 0.4402, "intent_source_scores": {"llm": 0.0, "embedding": 0.4401970963427134, "pattern": 0.5}, "entities": {"order_id": [], "product": [], "date": [], "amount": ["99 元"], "error_code": ["401"]}, "urgency": "N/A", "primary_agent": "technical", "supporting_agents": [], "agent_types": ["technical"], "routing_confidence": 1.0, "routing_reason": "intent=technical_login, group=technical, primary=technical, supporting=none, scores=[technical=1.13, billing=0.15, general=0.10]", "multi_agent": false, "tools_used": ["lookup_error_code", "search_knowledge_base", "search_knowledge_base", "build_diagnostic_plan"], "tool_traces": [{"agent_type": "technical", "tool_name": "lookup_error_code", "tool_use_id": "call_00_n4QYfC4EmnO8cnlQnZ361378", "input": {"error_code": "401"}, "success": true, "result_success": null, "latency_ms": 0.0, "cached": false, "reranked": false, "error": ""}, {"agent_type": "technical", "tool_name": "search_knowledge_base", "tool_use_id": "call_01_45xFfzY33UIUgfoqO1zX9005", "input": {"query": "登录 401 认证失败 Token 过期 排查", "top_k": 4}, "success": true, "result_success": true, "latency_ms": 3433.7, "
- Checks：{"intent": true, "primary_routing": true, "supporting_routing": false, "multi_agent": false, "rag_trigger": null, "tool_selection": false, "escalation": null}
- Errors：无

## G. Multi-Agent Observation

- 实际 Multi-Agent Trigger Rate：0.0556。
- 实际 Multi-Agent 平均延迟：19015.4 ms；Single-Agent：6731.8 ms。
- 本轮只记录数据，不据此删除或保留 Multi-Agent 架构。

## H. RAG Observation

- Required RAG Recall：1.0；Skip Case 不必要调用率：0.0。
- RAG 平均延迟：9187.1 ms；非 RAG：1209.2 ms。
- Query Rewrite 和 Rerank 的成功率当前无法从公开 trace 可靠读取，记录为 N/A；不能把 search_knowledge_base 被调用解释为 rewrite/rerank 全部成功。

### Docker 日志补充

- 日志来源：docker logs --since 2026-09-27T04:36:00Z echomind-app（窗口包含 Baseline 前紧邻的一次 Tool Trace smoke 请求）
- Trace 中 RAG Tool 调用数：19；Trace 中 reranked=true：19。
- Query Rewrite：日志反复出现“查询改写失败，使用原始查询”并回退到单个原始查询；日志窗口内也有一次成功生成多个子查询，精确逐 Case 比例未自动抽取。
- Rerank：日志反复出现“重排失败，返回原始顺序”；但 tool trace 仍记录 reranked=true，说明当前 reranked 字段不能区分真实重排与 fallback。
- Episodic Memory：日志反复出现 Chroma where exactly one operator 校验失败；本轮未修复。

## I. Priority Problems

1. Tool Selection Error（8 个 Case）
2. Intent Error（2 个 Case）
3. Routing Error（2 个 Case）
4. Escalation Error（1 个 Case）
5. Multi-Agent Error（1 个 Case）

## J. What Was Not Fixed

本轮除 Tool Trace 保存修复和对应测试外，没有修改 Intent、Routing、Multi-Agent、ResponseComposer、RAG trigger、rewrite、rerank、Embedding、Memory、Escalation、Monitor 或 Skills 业务逻辑。

## K. Verification

- py_compile：agents/agent_orchestrator.py、tests/test_agent_orchestrator.py、evaluation/run_baseline.py 通过。
- pytest：当前 Windows 环境未安装 pytest（python -m pytest 返回 No module named pytest）。
- pytest-compatible test body smoke：使用最小 anthropic stub 执行现有 11 个测试函数，11 passed、0 failed；其中包含成功路径和 provider 失败后的 Tool Trace 断言。
- HTTP Baseline：已执行 18 个固定 Case；可运行 18，阻塞 0，通过 8，失败 10。
