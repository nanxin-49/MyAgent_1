# Production Single: real Memory acceptance

Actual localhost HTTP `/chat` with the unchanged MemoryManager, running Redis/Chroma and real model.
A copied demo business fixture uses isolated test customers; their Redis keys and profile records are removed after the run.

| Check | Result |
|---|---|
| real_memory_manager | PASS |
| fresh_context_empty | PASS |
| first_order_lookup | PASS |
| redis_write_read | PASS |
| request_path | PASS |
| second_turn_uses_order_number | PASS |
| two_turns_persisted | PASS |
| session_isolation | PASS |
| user_isolation | PASS |
| other_user_no_order_leak | PASS |
| schema_nullable_deprecated | PASS |
| response_trace_null_compatible | PASS |
| trace_tool_consistent | PASS |
| redis_failure_fails_closed | PASS |
| redis_failure_did_not_run_agent | PASS |
| redis_recovery | PASS |

The second turn called `get_shipment` with the order ID from the first turn and returned the matching demo shipment.
The other user saw no order ID from the first conversation. OpenAPI marks old routing fields nullable and deprecated; response and trace return null.
A Redis connection failure returned HTTP 500 before Agent execution; restoring Redis recovered the original session. The existing error is generic HTTP 500, without a typed dependency response.
Compression, long-term episodic retrieval and profile quality were outside this acceptance. See memory_acceptance.json for check values and tool observations.
