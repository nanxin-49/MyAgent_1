"""Capture actual CartCare /chat and Tool Trace evidence for T09 scenarios."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _request(base_url: str, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def capture(base_url: str, cases: list[dict[str, Any]], output: Path, *, timeout: float = 90) -> list[dict[str, Any]]:
    run_id = uuid.uuid4().hex[:10]
    records: list[dict[str, Any]] = []
    for case in cases:
        started = time.monotonic()
        record: dict[str, Any] = {
            "case_id": case["id"], "captured_at": datetime.now(timezone.utc).isoformat(),
            "base_url": base_url, "run_id": run_id,
            "user_id": case.get("user_id", "customer-1"),
            "message": case["message"], "mode": "online_chat_demo_backend",
        }
        try:
            chat = _request(base_url, "/chat", {
                "message": case["message"], "user_id": record["user_id"],
                "conv_id": f"t09-{run_id}-{case['id']}",
            }, timeout)
            record["chat"] = chat
            request_id = chat.get("request_id")
            record["request_id"] = request_id
            if not request_id:
                raise RuntimeError("/chat returned no request_id")
            trace_response = _request(base_url, f"/trace/tool/{request_id}", None, min(timeout, 20))
            if not trace_response.get("found"):
                raise RuntimeError(f"Tool Trace missing for request_id={request_id}")
            trace = trace_response["trace"]
            record["trace"] = trace
            record["tool_traces"] = trace.get("tool_calls", [])
            record["routing"] = {key: trace.get(key) for key in (
                "primary_agent", "supporting_agents", "routing_reason", "routing_confidence", "escalated"
            )}
            record["rag"] = {"status": chat.get("retrieval_status"), "citations": chat.get("citations", [])}
            record["policy_action"] = [item["action_result"] for item in record["tool_traces"]
                                        if item.get("action_result") is not None]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            record["error"] = str(exc)
        record["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        records.append(record)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        chat = record.get("chat") or {}
        print(json.dumps({"case_id": case["id"], "request_id": record.get("request_id"),
                          "intent": chat.get("intent"), "tools_used": chat.get("tools_used"),
                          "rag_status": chat.get("retrieval_status"),
                          "policy_action": record.get("policy_action"), "error": record.get("error")},
                         ensure_ascii=False), flush=True)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one real /chat run for T09 cases")
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--cases", type=Path, default=ROOT / "t09_online_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "t09_online_observations.json")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    records = capture(args.base_url, cases, args.output, timeout=args.timeout)
    return 1 if any("error" in record for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
