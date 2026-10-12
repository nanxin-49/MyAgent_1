"""Run only local Fake SDK A02 cases; never opens paid model or live services."""
import json
import platform
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient
from api import main
from agents.support_agent import SupportRuntime
from core.auth import Principal, get_principal
from evaluation.handoff_eval import score


class FakeSDK:
    def __init__(self, reason=None, reply="未创建任何交接"):
        self.messages = self
        self.responses = ([NS(content=[NS(type="tool_use", id="h1", name="request_handoff",
                                        input={"reason_code": reason})])] if reason else [])
        self.responses.append(NS(content=[NS(type="text", text=reply)]))

    async def create(self, **kwargs):
        return self.responses.pop(0)


class EmptyMemory:
    async def get_context(self, *args, **kwargs):
        return NS(recent_messages=[], to_prompt_text=lambda: "")

    async def add_message(self, *args):
        pass

    async def update_profile(self, *args):
        pass


def run():
    from agents.agent_orchestrator import BaseAgent
    catalog = json.loads(Path("evaluation/handoff_cases.json").read_text(encoding="utf-8"))
    principal = Principal("a02-eval-local", "customer-1", frozenset({"customer"}))
    previous = main._orchestrator, main._memory, main._action_service
    overrides = dict(main.app.dependency_overrides)
    rows = []
    try:
        main.app.dependency_overrides[get_principal] = lambda: principal
        for case in catalog["cases"]:
            runtime = SupportRuntime("fake", "fake", client=FakeSDK(case.get("tool"), case.get("reply", "已转接")))
            main._orchestrator, main._memory, main._action_service = runtime, EmptyMemory(), None
            if case.get("service_failure"):
                def fail(*args):
                    raise RuntimeError("synthetic handoff outage")
                runtime.handoff_service._create_record = fail
            http = TestClient(main.app)
            request = {"message": case["message"], "conv_id": "a02:" + case["id"], "handoff_key": "turn-1"}
            response = http.post("/chat", json=request)
            assert response.status_code == 200
            body = response.json()
            first_id = body["handoff"]["handoff_id"]
            if case.get("repeat"):
                body = http.post("/chat", json=request).json()
            trace = runtime.get_tool_trace(body["request_id"])
            record = http.get("/handoffs/" + body["handoff"]["handoff_id"]).json() if body["handoff"]["handoff_id"] else None
            rows.append({"case_id": case["id"], "http_status": response.status_code,
                         "body": body, "trace": trace, "owned_record": record,
                         "score": score(case, body, trace, record, len(runtime.handoff_service._records), first_id)})
    finally:
        main._orchestrator, main._memory, main._action_service = previous
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(overrides)
    return {"dataset_version": catalog["version"], "evidence_type": catalog["evidence_type"],
            "captured_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "legacy_keyword_observations": {
                "negative_response_flag": BaseAgent._needs_escalation(None, "您不需要人工客服，请提供订单号。"),
                "unsupported_refusal_flag": BaseAgent._needs_escalation(None, "电商客服无法处理订票。"),
                "explicit_request_plain_reply_flag": BaseAgent._needs_escalation(None, "好的，我了解了。"),
                "scope": "Unchanged historical BaseAgent keyword function, not production structured state"},
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "python": platform.python_version(), "passed": sum(r["score"]["passed"] for r in rows),
            "total": len(rows), "observations": rows}


if __name__ == "__main__":
    result = run()
    Path("docs/engineering/A02-handoff-observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"A02 Fake HTTP handoff: {result['passed']}/{result['total']}")
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
