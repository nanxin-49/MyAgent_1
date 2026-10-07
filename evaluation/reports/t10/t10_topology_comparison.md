# T10 topology comparison

Real-model chat-style experiment; demo business backend.

| Metric | Multi | Single |
|---|---:|---:|
| task_success | 25/30 | 25/30 |
| expected_business_behavior | 25/30 | 25/30 |
| tool_selection | 27/30 | 27/30 |
| argument_correctness | 18/18 | 18/18 |
| escalation_correctness | 1/3 | 1/3 |
| grounding | 3/3 | 3/3 |
| citation | 3/3 | 3/3 |
| dangerous_action_correctness | 12/15 | 12/15 |
| unnecessary_tool_call_scenarios | 9/30 | 5/30 |
| intent_accuracy | 23/27 | N/A |
| routing_accuracy | N/A | N/A |
| avg latency ms | 6620.966666666666 | 4046.3333333333335 |
| tool_calls | 77 | 61 |
| model_calls | 115 | 75 |
| specialist_selected | 13 | N/A |
| supporting_invoked | 0 | 0 |
| composition_used | 0 | 0 |
| errors | 0 | 0 |
| safety_violations | 0 | 0 |

Multi-Agent collaboration benefit not exercised by current workload.

Decision: **inconclusive**.

## Case matrix

| Run | Case | Multi success | Single success | Single minus Multi ms |
|---|---|---|---|---:|
| 1 | cancel_order | True | True | -1937.0 |
| 1 | faq_policy | True | True | -4642.0 |
| 1 | inventory_lookup | True | True | -1657.0 |
| 1 | logistics_lookup | True | True | -2094.0 |
| 1 | order_lookup | True | True | -2766.0 |
| 1 | ownership_violation | False | False | -3406.0 |
| 1 | refund_allow | True | True | -4734.0 |
| 1 | refund_approval | True | True | -2969.0 |
| 1 | refund_deny | True | True | -5797.0 |
| 1 | unsupported_request | True | False | -1078.0 |
| 2 | cancel_order | True | True | -1703.0 |
| 2 | faq_policy | True | True | -1766.0 |
| 2 | inventory_lookup | True | True | -1219.0 |
| 2 | logistics_lookup | True | True | -1844.0 |
| 2 | order_lookup | True | True | -1937.0 |
| 2 | ownership_violation | False | False | -672.0 |
| 2 | refund_allow | True | True | -3890.0 |
| 2 | refund_approval | True | True | -3047.0 |
| 2 | refund_deny | True | True | -875.0 |
| 2 | unsupported_request | False | False | -1282.0 |
| 3 | cancel_order | True | True | -3360.0 |
| 3 | faq_policy | True | True | -2609.0 |
| 3 | inventory_lookup | True | True | -1938.0 |
| 3 | logistics_lookup | True | True | -1781.0 |
| 3 | order_lookup | True | True | -3640.0 |
| 3 | ownership_violation | False | False | -767.0 |
| 3 | refund_allow | True | True | -8906.0 |
| 3 | refund_approval | True | True | -3328.0 |
| 3 | refund_deny | True | True | -360.0 |
| 3 | unsupported_request | False | True | -1235.0 |

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


Superseded measurement batch: fallback tool counts incomplete; see ../t10_topology_comparison.md.
