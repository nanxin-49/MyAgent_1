"""Actual production POST /chat, real model/RAG, isolated demo fixture and empty Memory.

This isolates topology migration; it does not validate Redis or long-term Memory.
uv run python -m evaluation.run_support_regression --output-dir evaluation/reports/support_production
"""
import argparse
import asyncio
import json
import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from dotenv import load_dotenv

from evaluation.capture_online_eval import _request
from evaluation.prepare_online_eval import prepare
from evaluation.run_topology_comparison import collection_snapshot, digest, save
from evaluation.topology_eval import compare

ROOT = Path(__file__).resolve().parents[1]


class FrozenMemory:
    def __init__(self, **kwargs):
        pass

    async def get_context(self, *args, **kwargs):
        return SimpleNamespace(recent_messages=[], to_prompt_text=lambda: "")

    async def add_message(self, *args):
        pass

    async def update_profile(self, *args):
        pass

    async def close(self):
        pass


async def run(args):
    from api import main as api
    from memory import conversation_memory
    from mcp.knowledge_base import KnowledgeBase
    load_dotenv()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "observations.json"
    if raw_path.exists():
        raise FileExistsError("Choose a new output directory; evidence is never overwritten")
    catalog = json.loads((ROOT / "evaluation/t10_cases.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "evaluation/reports/t10_topology_comparison.json").read_text(encoding="utf-8"))
    historical = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in list(ROOT.glob("t09*.json")) + list((ROOT / "evaluation/reports").glob("t10_topology_comparison.*"))}
    kb = KnowledgeBase(chroma_host=args.chroma_host, chroma_port=args.chroma_port, seed_defaults=False)
    snapshot = digest(collection_snapshot(kb))
    assert snapshot == baseline["manifest"]["rag_hash"] and kb.min_score == .35
    assert os.environ["ANTHROPIC_MODEL"] == baseline["manifest"]["model"]
    fixture, _ = prepare(datetime.now(timezone.utc))
    save(output / "fixture.json", fixture)
    save(output / "cases.json", catalog)
    env_changes = {"CHROMA_HOST": args.chroma_host, "CHROMA_PORT": str(args.chroma_port),
        "CARTCARE_BUSINESS_FIXTURE": str(output / "fixture.json"), "ALERT_WEBHOOK_URL": "",
        "PROMETHEUS_PORT": "0"}
    previous_env = {k: os.environ.get(k) for k in env_changes}
    os.environ.update(env_changes)
    previous_memory = conversation_memory.MemoryManager
    conversation_memory.MemoryManager = FrozenMemory
    server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=args.port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    records = []
    try:
        while not server.started:
            if task.done():
                await task
                raise RuntimeError("Isolated HTTP server did not start")
            await asyncio.sleep(.1)
        from agents.support_agent import SupportRuntime
        assert isinstance(api._orchestrator, SupportRuntime)
        base_url = f"http://127.0.0.1:{args.port}"
        for case in catalog:
            # Match the accepted experiment's fresh RAG cache per case.
            api._tool_manager._cache.clear()
            backend = api._action_service._executor._backend
            before = len(backend.calls)
            record = {"case_id": case["id"], "topology": "single_agent", "run": 1,
                "mode": "production_http_real_model_demo_backend_frozen_memory"}
            start = time.monotonic()
            try:
                chat = await asyncio.to_thread(_request, base_url, "/chat", {
                    "message": case["message"], "user_id": case.get("user_id", "customer-1"),
                    "conv_id": f"support-regression-{uuid.uuid4().hex}"}, 120)
                record["chat"] = chat
                trace = await asyncio.to_thread(_request, base_url, f'/trace/tool/{chat["request_id"]}', None, 20)
                assert trace["found"] and chat["topology"] == "single" and chat["agent_type"] == "support"
                record["trace"] = trace["trace"]
                record["tool_traces"] = trace["trace"]["tool_calls"]
                record["model_calls"] = trace["trace"]["model_calls"]
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            record["elapsed_ms"] = round((time.monotonic() - start)*1000, 1)
            record["backend_executions"] = backend.calls[before:]
            records.append(record)
            save(raw_path, records)
            print(json.dumps({"case": case["id"], "tools": record.get("chat", {}).get("tools_used"),
                "latency_ms": record["elapsed_ms"], "error": record.get("error")}, ensure_ascii=False), flush=True)
        report = {"manifest": {"mode": "actual HTTP /chat; real model + Chroma HTTP; demo action backend",
            "memory": "fixed empty adapter; Redis, compression and profile updates not validated",
            "runs": 1, "cases": len(catalog), "cases_hash": digest(catalog), "fixture_hash": digest(fixture),
            "model": os.environ["ANTHROPIC_MODEL"], "rag_hash": snapshot,
            "rag_unchanged": digest(collection_snapshot(kb)) == snapshot,
            "historical_unchanged": all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p, h in historical.items())},
            "experimental_single": baseline["arms"]["single_agent"],
            "production_single": compare(catalog, records, {})["arms"]["single_agent"]}
        # Historical source artifacts are read only; the report uses a separate directory.
        save(output / "regression.json", report)
        lines = ["# Production Single regression", "", report["manifest"]["mode"],
            "", "One 10-case round; fixed empty Memory adapter, fresh RAG cache per case. No stable performance claim.",
            "", "| Metric | Experimental Single (30) | Production Single (10) |", "|---|---:|---:|"]
        for key, metric in report["production_single"]["metrics"].items():
            def display(value):
                return value if isinstance(value, str) else f'{value["numerator"]:g}/{value["denominator"]}'
            lines.append(f'| {key} | {display(report["experimental_single"]["metrics"][key])} | {display(metric)} |')
        for key in ("tool_calls", "model_calls", "safety_violations", "errors"):
            lines.append(f'| {key} | {report["experimental_single"][key]} | {report["production_single"][key]} |')
        lines.append(f'| avg latency ms | {report["experimental_single"]["latency"]["mean_ms"]:.1f} | {report["production_single"]["latency"]["mean_ms"]:.1f} |')
        lines += ["", "Known unsupported escalation and ownership strict-action evidence gaps remain follow-ups.",
                  "Historical T09/T10 evidence was not rewritten. Raw HTTP responses and guarded tool traces: observations.json."]
        (output / "regression.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
        return int(any(r.get("error") for r in records) or report["production_single"]["safety_violations"] > 0
                   or not report["manifest"]["rag_unchanged"] or not report["manifest"]["historical_unchanged"])
    finally:
        server.should_exit = True
        await task
        conversation_memory.MemoryManager = previous_memory
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation/reports/support_production")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--chroma-host", default="127.0.0.1")
    parser.add_argument("--chroma-port", type=int, default=8001)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
