CartCare's main branch still uses the older production path. This stage adopts the accepted Single Support Agent, bounds customer memory, and adds a traceable demo with documentation aligned to the executable system.

## Changes

- Preserve T10's controlled topology experiment and original reports; production /chat now uses MemoryManager → SingleSupportAgent → Unified Tool Runtime → RAG / Providers / ActionService → Response / Trace.
- Bound Redis working memory and Chroma topics/preferences, refresh dynamic business facts through Providers, and fail closed on Redis reads.
- Add /demo with ten scenario inputs, citations and retrieval states, tool risk/validated inputs/results, Policy/HITL, and the existing approve/reject/resume APIs.
- Extend existing Trace projections with Memory stage observations, document titles and safe deterministic helper outputs; update README, Workbench and the two core Wiki documents.
- Record the user's T12 acceptance as done. T12 preserves Policy, Provider, ActionService/HITL, RAG threshold and embedding behavior.

## Validation

- Final PR head: uv lock --check passed; pytest: 150 passed, 2 opt-in integration tests skipped.
- Node syntax check passed; JS rendering/API consumer contract: 12 passed; git diff --check passed.
- T12 implementation validation with isolated real Redis/Chroma tests enabled: 152 passed. Real browser FAQ and refund approval smoke, observations and screenshots are checked in under docs/.
- T10: controlled demo workload, 3 × 10 cases per topology, not a production benchmark. Multi/Single task success both 24/30; latency 6633.3/3937.1 ms, tool calls 78/59, model calls 115/76.
- T11 real-memory acceptance: 18/18 in the demo environment, not a production-scale reliability claim.

## Boundaries

Demo user_id is not formal authentication; commerce/actions and PendingAction/Trace storage remain in-memory. External shop/payment APIs, durable action persistence, physical expiry cleanup and improved unsupported escalation remain follow-ups. Character n-gram lexical embeddings and historical evaluation limitations are explicit in README.

All existing stage commits are retained; no force push or rewritten historical reports.
