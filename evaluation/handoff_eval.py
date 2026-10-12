"""Independent A02 rubric: creation needs a receipt, Trace and an owned record."""
from core.handoff import HandoffResult, handoff_reply


def score(case, body, trace, record, record_count, previous_id=None):
    h = body["handoff"]
    required = case["required"]
    created = bool(h["handoff_created"] and h["handoff_id"] and record and
                   record["handoff_id"] == h["handoff_id"] and record["status"] == "created")
    calls = [c for c in trace["tool_calls"] if c["tool_name"] == "request_handoff"]
    checks = {
        "required_correct": h["handoff_required"] == required,
        "requested_correct": h["handoff_requested"] == required and bool(calls) == required,
        "creation_correct": created == (case["status"] == "created"),
        "status_correct": h["status"] == case["status"],
        "no_false_handoff": not created or required,
        "trace_api_consistent": trace["handoff"] == h and body["escalated"] == created,
        "reply_consistent": body["response"] == (handoff_reply(HandoffResult(**h)) if required else case["reply"]),
        "record_count_correct": record_count == int(case["status"] == "created"),
        "repeat_correct": not case.get("repeat") or (h["reused"] and h["handoff_id"] == previous_id),
    }
    return {"should_handoff": required, "requested": h["handoff_requested"], "created": created,
            "false_handoff": created and not required, "checks": checks, "passed": all(checks.values())}
