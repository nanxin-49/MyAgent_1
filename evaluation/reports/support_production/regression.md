# Production Single regression

actual HTTP /chat; real model + Chroma HTTP; demo action backend

One 10-case round; fixed empty Memory adapter, fresh RAG cache per case. No stable performance claim.

| Metric | Experimental Single (30) | Production Single (10) |
|---|---:|---:|
| task_success | 24/30 | 8/10 |
| expected_business_behavior | 24/30 | 8/10 |
| tool_selection | 27/30 | 9/10 |
| argument_correctness | 18/18 | 6/6 |
| escalation_correctness | 0/3 | 0/1 |
| grounding | 3/3 | 1/1 |
| citation | 3/3 | 1/1 |
| dangerous_action_correctness | 12/15 | 4/5 |
| unnecessary_tool_call_scenarios | 5/30 | 3/10 |
| intent_accuracy | N/A | N/A |
| routing_accuracy | N/A | N/A |
| tool_calls | 59 | 21 |
| model_calls | 76 | 25 |
| safety_violations | 0 | 0 |
| errors | 0 | 0 |
| avg latency ms | 3937.1 | 3686.0 |

Known unsupported escalation and ownership strict-action evidence gaps remain follow-ups.
Historical T09/T10 evidence was not rewritten. Raw HTTP responses and guarded tool traces: observations.json.
