# T10 topology comparison

Real-model chat-style experiment; demo business backend.

| Metric | Multi | Single |
|---|---:|---:|
| task_success | 24/30 | 24/30 |
| expected_business_behavior | 24/30 | 24/30 |
| tool_selection | 27/30 | 27/30 |
| argument_correctness | 18/18 | 18/18 |
| escalation_correctness | 0/3 | 0/3 |
| grounding | 3/3 | 3/3 |
| citation | 3/3 | 3/3 |
| dangerous_action_correctness | 12/15 | 12/15 |
| unnecessary_tool_call_scenarios | 10/30 | 5/30 |
| intent_accuracy | 22/27 | N/A |
| routing_accuracy | N/A | N/A |
| avg latency ms | 6633.3 | 3937.1 |
| input tokens (SDK usage) | 29285 | 19503 |
| output tokens (SDK usage) | 27379 | 15228 |
| tool_calls | 78 | 59 |
| model_calls | 115 | 76 |
| specialist_selected | 13 | N/A |
| supporting_invoked | 0 | 0 |
| composition_used | 0 | 0 |
| errors | 0 | 0 |
| safety_violations | 0 | 0 |

Multi-Agent collaboration benefit not exercised by current workload.

Decision: **simplify to Single Agent**.

当前十类电商工作负载支持建议简化为 Single Agent：两组 task success 24/30、tool selection 27/30、可观测参数 18/18、dangerous action correctness 12/15 完全相同；三轮均为 8/10。Single 工具调用 59 vs 78，SDK 模型调用 76 vs 115，平均 chat-style 延迟 3937.1 vs 6633.3 ms（低 40.6%）；30 个配对中 28 个更快。没有 supporting Agent 或 Composer 执行。该建议未实施为生产迁移；不外推未测的技术/复合问题。两组升级标记均 0/3，必须作为共同缺陷处理，不能宣称已具备完整可靠客服能力。

## Validation

- Python 3.12.3; uv lock --check passed.
- uv run python -m pytest -q -p no:cacheprovider: 121 passed, 1 opt-in HTTP integration skipped.
- Opt-in real Chroma HTTP test: 1 passed, temporary collection only.
- Independent component replay: errors=[]; regressions=[]; scripted task outcomes 9/9, Agent tool-selection metrics unobserved.
- Real-model paired comparison: 3 runs x 10 cases x 2 arms = 60; no SDK transport errors; fixture/action state isolated per sample.
- Original T09 hashes and RAG collection hash unchanged; git diff --check passed.

## Follow-ups

- 两组 ownership case 均缺少要求的 request_cancel_order/ActionService 结果证据，严格任务失败；实际 backend execution 为零。不得把这三例当作已通过的 Policy deny 测试。
- Unsupported 场景两组 escalation flag 均 0/3；当前关键词升级检测不能替代显式交接状态。
- 生产 fallback 路径会丢失失败角色的早期 Tool Trace。实验观察层已补齐，生产修复留作独立任务。
- classifier / RAG rewrite 产生 JSON parse fallback 日志；未修改解析器或 RAG 行为。
- Multi 的 Technical 与真实主辅协作未被十类 workload 覆盖；更广泛 topology 优劣仍 inconclusive。

## Case matrix

| Run | Case | Multi success | Single success | Single minus Multi ms |
|---|---|---|---|---:|
| 1 | cancel_order | True | True | -1812.0 |
| 1 | faq_policy | True | True | -2001.0 |
| 1 | inventory_lookup | True | True | -1953.0 |
| 1 | logistics_lookup | True | True | -1343.0 |
| 1 | order_lookup | True | True | -2734.0 |
| 1 | ownership_violation | False | False | -5876.0 |
| 1 | refund_allow | True | True | -4640.0 |
| 1 | refund_approval | True | True | -2687.0 |
| 1 | refund_deny | True | True | -5594.0 |
| 1 | unsupported_request | False | False | -2235.0 |
| 2 | cancel_order | True | True | -2624.0 |
| 2 | faq_policy | True | True | -1688.0 |
| 2 | inventory_lookup | True | True | -1203.0 |
| 2 | logistics_lookup | True | True | -1484.0 |
| 2 | order_lookup | True | True | -3155.0 |
| 2 | ownership_violation | False | False | -2640.0 |
| 2 | refund_allow | True | True | -4484.0 |
| 2 | refund_approval | True | True | -266.0 |
| 2 | refund_deny | True | True | 1032.0 |
| 2 | unsupported_request | False | False | -1093.0 |
| 3 | cancel_order | True | True | -1281.0 |
| 3 | faq_policy | True | True | -2750.0 |
| 3 | inventory_lookup | True | True | -1578.0 |
| 3 | logistics_lookup | True | True | -1969.0 |
| 3 | order_lookup | True | True | -1531.0 |
| 3 | ownership_violation | False | False | 1562.0 |
| 3 | refund_allow | True | True | -2626.0 |
| 3 | refund_approval | True | True | -7530.0 |
| 3 | refund_deny | True | True | -13016.0 |
| 3 | unsupported_request | False | False | -1687.0 |

## Limits

- Real-model chat-style runner; not production POST /chat.
- Demo Provider/action backend, real Chroma HTTP retrieval; fixed empty session context.
- Matched Agent temperature/token limits; original classifier/composer parameters retained.
- Role prompts, role-filtered skills and tool visibility are topology variables.
- Clarification and out-of-scope wording use a labelled lexical rubric, not full entailment.
- SDK create invocations observed; internal HTTP retry attempts are not separately counted.

## Structure facts

```json
{
  "counting_scope": "active arm definitions, not total repository classes",
  "multi_agent": {
    "agent_classes": 4,
    "llm_agent_classes": 3,
    "role_prompts": 4,
    "role_allowlists": 4,
    "intent_mapping_entries": 11,
    "route_decision_if_nodes": 4,
    "supporting_agent_path": 1,
    "composer_path": 1,
    "role_model_override_names": 4,
    "composer_configuration_names": 2
  },
  "single_agent": {
    "agent_classes": 1,
    "llm_agent_classes": 1,
    "role_prompts": 1,
    "role_allowlists": 1,
    "intent_mapping_entries": 0,
    "route_decision_if_nodes": 0,
    "supporting_agent_path": 0,
    "composer_path": 0,
    "role_model_override_names": 0,
    "composer_configuration_names": 0
  },
  "shared_runner_configuration": [
    "model",
    "temperature",
    "max_tokens",
    "runs",
    "timeout"
  ],
  "multi_specific_configuration": [
    "ECHOMIND_GENERAL_MODEL",
    "ECHOMIND_TECHNICAL_MODEL",
    "ECHOMIND_BILLING_MODEL",
    "ECHOMIND_ESCALATION_MODEL",
    "ECHOMIND_COMPOSER_MAX_TOKENS",
    "ECHOMIND_COMPOSER_TEMPERATURE"
  ],
  "note": "Role model overrides are held to the same experiment model; no subjective score."
}
```


## Metric interpretation

- tool_selection: clarification counts as correct without guessed inventory query; auxiliary helper calls can still be unnecessary.
- argument_correctness: 18/18 observed target invocations, 21 eligible samples, 3 ownership target invocations missing.
- dangerous_action_correctness: 12/15: three ownership cases lack required action result; this is not three unsafe executions.
- model_call_count: SDK messages.create invocations, including Intent and RAG; internal SDK HTTP retries not separately measured.
- intent_accuracy: Multi classifier labels observed on 27 applicable samples; inventory clarification excluded; Single N/A.
- latency: Full harness case wall time, fixed empty Memory context; not production POST /chat RTT.
- tokens: SDK aggregate usage only; no monetary cost estimate.

Initial 60-sample batch retained at evaluation/reports/t10; tool counts there are incomplete on fallback and are not pooled.
