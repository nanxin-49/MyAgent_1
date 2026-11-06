# H2-5 semantic retrieval comparison

- run: 20261027T094416Z-5659da57
- model: BAAI/bge-small-zh-v1.5 @ 7999e1d3359715c523056ef9478215996d62a620
- B0 threshold: 0.2; semantic/hybrid threshold: 0.65

| Group | Recall@1 | Recall@3 | Recall@5 | MRR | No-answer FPR | Citation precision | Retrieval p50/p95 ms | Embedding p50 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| b0 | 0.4286 | 0.4286 | 0.4286 | 0.4286 | 0.8889 | 0.5294 | 79.53834999352694 / 99.09590503666548 | n/a (lexical) |
| semantic | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.7 | 66.93050009198487 / 90.53967000218108 | 23.304 |
| hybrid | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.7 | 74.75094997789711 / 103.92388991313054 | 23.304 |

Test was run once per group with thresholds locked on the dev set.
Semantic query embedding is precomputed; retrieval latency excludes it.
Hybrid uses the semantic threshold as the usability gate and BM25 only reranks.
B0 uses the lexical char-bigram embedding; no neural query-embedding latency applies.
