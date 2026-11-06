# H3-3 Context Budget Comparison

- budget: 4000 estimated tokens
- note: Estimated tokens (ASCII/4 + non-ASCII chars), not tokenizer output. Deterministic scripts do not react to context; success equality only shows the compressed path is intact. Real-model quality is H3-6.

| Case | on success | off success | on tokens | off tokens | on compressed rounds |
| --- | --- | --- | ---: | ---: | ---: |
| single_query | True | True | 5280 | 5280 | 0 |
| long_memory | True | True | 6112 | 29314 | 1 |
| long_memory_two_calls | True | True | 9335 | 32138 | 1 |
| big_result | True | True | 6787 | 9989 | 1 |
| big_then_query | True | True | 10679 | 27482 | 1 |
| rag_long | True | True | 6098 | 23300 | 1 |
| cancel_action | True | True | 6315 | 19517 | 1 |
| three_rounds | True | True | 9347 | 23150 | 1 |
- on: success=1.0, tokens=59953, compressed_rounds=7, over_budget_rounds=0, executor_calls=1
- off: success=1.0, tokens=170170, compressed_rounds=0, over_budget_rounds=17, executor_calls=1
