# T11: real Memory acceptance

Actual localhost HTTP `/chat` with the T11 MemoryManager, running Redis/Chroma and real model.
A copied demo business fixture uses isolated test customers; their Redis keys and profile records are removed after the run.

| Check | Result |
|---|---|
| real_memory_manager | PASS |
| fresh_context_empty | PASS |
| async_profile_explicit_preference | PASS |
| first_order_lookup | PASS |
| redis_write_read | PASS |
| request_path | PASS |
| second_turn_uses_order_number | PASS |
| two_turns_persisted | PASS |
| dynamic_order_fact_refreshed | PASS |
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
After the copied demo order changed from shipped to delivered, a later turn called `get_order` again and observed the fresh Provider status.
An explicit response-language preference was written by the asynchronous profile update and read back from the real Chroma collection.
The other user saw no order ID from the first conversation. OpenAPI marks old routing fields nullable and deprecated; response and trace return null.
A Redis connection failure returned typed HTTP 503 before Agent execution; restoring Redis recovered the original session.
Compression, long-term retrieval and profile metadata are tested separately with a real Redis/Chroma opt-in test. See the adjacent JSON for check values and tool observations.
