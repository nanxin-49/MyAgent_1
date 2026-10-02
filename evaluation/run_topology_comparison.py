"""Controlled T10 real-model runner, independent of production /chat dispatch.

uv run python -m evaluation.run_topology_comparison --runs 3 --chroma-port 8001
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from agents.agent_orchestrator import AgentOrchestrator, Request
from api.main import collect_rag_evidence, render_rag_citations
from core.skill_loader import SkillManager
from core.tool_contract import RetryPolicy
from mcp.knowledge_base import KnowledgeBase
from mcp.tool_manager import MCPToolManager, Tool
from .prepare_online_eval import prepare
from .topology_eval import compare, markdown
from .topology_experiment import (AllRoleSkills, SingleSupportAgent, bind_tools,
                                  isolated_business, matched_generation)

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ObservedMessages:
    def __init__(self, client, stage, events):
        self.client, self.stage, self.events = client, stage, events

    async def create(self, **kwargs):
        event = {"stage": self.stage, "model": kwargs["model"],
                 "temperature": kwargs.get("temperature"), "max_tokens": kwargs.get("max_tokens"),
                 "prompt_hash": digest({k: kwargs.get(k) for k in ("system", "messages")}),
                 "tool_names": [t["name"] for t in kwargs.get("tools", [])],
                 "tool_schema_hash": digest(kwargs.get("tools", []))}
        self.events.append(event)
        start = time.monotonic()
        try:
            response = await self.client.messages.create(**kwargs)
            usage = getattr(response, "usage", None)
            for key in ("input_tokens", "output_tokens"):
                event[key] = getattr(usage, key, None)
            event["response_id"] = getattr(response, "id", None)
            return response
        except Exception as exc:
            event["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            event["latency_ms"] = round((time.monotonic()-start)*1000, 1)


def observe(client, stage, events):
    return SimpleNamespace(messages=ObservedMessages(client, stage, events))


def rag_manager(cfg, kb, events):
    manager = MCPToolManager(**cfg)
    client = manager._client
    manager._client = observe(client, "rag_rewrite_or_rerank", events)
    def fallback(params, context, error):
        return [{"title": "知识库降级结果", "content": f'知识库暂时不可用，未能完成对“{params.get("query", "")}”的语义检索。请稍后重试，或转人工客服确认。',
                 "score": 0.0, "fallback": True, "error": error}]
    manager.register(Tool("knowledge_search", "搜索知识库（基于 ChromaDB 向量检索）", kb.search_handler,
        {"type": "object", "properties": {"query": {"type": "string", "minLength": 1},
            "top_k": {"type": "integer"}}, "required": ["query"], "additionalProperties": False},
        cache_ttl=300.0, supports_rerank=True, fallback=fallback, retry_policy=RetryPolicy(max_attempts=2)))
    return manager, client


async def run_case(arm, case, fixture, now, cfg, kb, skills, args, run):
    events, execution, clients = [], {"invoked_agents": [], "agent_attempts": [],
                                     "supporting_invoked": [], "composition_used": False}, []
    business, service, write_backend = isolated_business(fixture, now)
    rag, rag_client = rag_manager(cfg, kb, events)
    clients.append(rag_client)
    req = Request(message=case["message"], user_id=case.get("user_id", "customer-1"),
                  conv_id=f"t10-{uuid.uuid4().hex}", context=case.get("context", ""),
                  history=case.get("history"))
    record = {"case_id": case["id"], "topology": arm, "run": run,
              "mode": "real_model_chat_style_demo_backend", "request_id": req.request_id,
              "context_hash": digest({"context": req.context, "history": req.history}),
              "model_calls": events, "execution": execution}
    start = time.monotonic()
    try:
        if arm == "multi_agent":
            topology = AgentOrchestrator(**cfg, skill_manager=skills)
            matched_generation(topology, cfg["model"], args.temperature, args.max_tokens)
            bind_tools(topology, business, rag)
            agent_client = topology._composer._client
            classifier_client = topology._intent_recognizer.client
            clients += [agent_client, classifier_client]
            topology._composer._client = observe(agent_client, "composer", events)
            topology._intent_recognizer.client = observe(classifier_client, "intent", events)
            for pool in topology._pool.values():
                for agent in pool:
                    agent._client = observe(agent_client, f"agent:{agent.agent_type.value}", events)
                    original = agent.handle
                    async def handle(request, original=original, name=agent.agent_type.value):
                        execution["invoked_agents"].append(name)
                        response = await original(request)
                        # Production result may replace a failed specialist with fallback.
                        # Observe every executed handle without altering its returned value.
                        execution["agent_attempts"].append({"agent": name,
                            "success": response.success, "tool_traces": list(response.tool_traces)})
                        return response
                    agent.handle = handle
            original_compose = topology._composer.compose
            async def compose(request, responses):
                execution["composition_used"] = True
                return await original_compose(request, responses)
            topology._composer.compose = compose
            # Mirror production /chat: recognize first and include extracted entities.
            async def multi():
                intent = await topology.recognize_intent(req.message, history=req.history)
                req.intent, req.intent_group, req.urgency = intent.intent, intent.intent_group, intent.urgency
                req.entities, req.intent_confidence = intent.entities, intent.confidence
                return await topology.run(req)
            result = await asyncio.wait_for(multi(), timeout=args.timeout)
            execution["supporting_invoked"] = [a.value for a in result.supporting_agents
                                               if a.value in execution["invoked_agents"]]
            content = result.response
            record["returned_tool_traces"] = result.tool_traces
            traces = [t for attempt in execution["agent_attempts"] for t in attempt["tool_traces"]]
            intent, primary, supporting, escalated = (result.intent.value if result.intent else None,
                result.primary_agent.value if result.primary_agent else None,
                [a.value for a in result.supporting_agents], result.escalated)
            record["orchestrator_ms"] = result.latency_ms
            record["routing_reason"] = result.routing_reason
        else:
            client = AsyncAnthropic(**{k: v for k, v in cfg.items() if k != "model"})
            clients.append(client)
            topology = SingleSupportAgent(observe(client, "single_support", events), cfg["model"],
                AllRoleSkills(skills), profile=replace(SingleSupportAgent.profile,
                    temperature=args.temperature, max_tokens=args.max_tokens))
            bind_tools(topology, business, rag)
            topology.profile = replace(topology.profile, tool_scope=tuple(topology.get_tools()))
            execution["invoked_agents"].append("single_support")
            result = await asyncio.wait_for(topology.handle(req), timeout=args.timeout)
            content, traces = result.content, result.tool_traces
            execution["agent_attempts"].append({"agent": "single_support", "success": result.success,
                                               "tool_traces": list(traces)})
            intent, primary, supporting, escalated = None, None, [], result.escalate
            record["orchestrator_ms"] = None
        status, citations = collect_rag_evidence(traces)
        record["chat"] = {"response": render_rag_citations(content, citations),
            "intent": intent, "primary_agent": primary, "supporting_agents": supporting,
            "escalated": escalated, "tools_used": result.tools_used,
            "retrieval_status": status, "citations": citations}
        record["tool_traces"] = traces
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["elapsed_ms"] = round((time.monotonic()-start)*1000, 1)
        record["backend_executions"] = list(write_backend.calls)
        record["pending_actions"] = [a.model_dump(mode="json") for a in service._store._actions.values()]
        for client in {id(c): c for c in clients}.values():
            await client.close()
    return record


def collection_snapshot(kb):
    data = kb._collection.get(include=["documents", "metadatas", "embeddings"])
    embeddings = data.get("embeddings")
    return {"metadata": kb._collection.metadata, "rows": sorted([
        {"id": key, "document": data["documents"][i], "metadata": data["metadatas"][i],
         "embedding": embeddings[i].tolist() if hasattr(embeddings[i], "tolist") else embeddings[i]}
        for i, key in enumerate(data["ids"])], key=lambda r: r["id"])}


async def run(args):
    cfg = {"api_key": os.environ["ANTHROPIC_API_KEY"], "model": os.environ["ANTHROPIC_MODEL"]}
    if os.getenv("ANTHROPIC_BASE_URL"):
        cfg["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "t10_topology_observations.json"
    if raw_path.exists():
        raise FileExistsError("Use a new output directory; existing observations are never overwritten")
    catalog = json.loads(args.cases.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    fixture, _ = prepare(now)
    kb = KnowledgeBase(chroma_host=args.chroma_host, chroma_port=args.chroma_port, seed_defaults=False)
    if kb.min_score != .35:
        raise ValueError("Experiment requires unchanged RAG threshold 0.35")
    snapshot = collection_snapshot(kb)
    faq = next(c for c in catalog if c["kind"] == "rag")["expected"]
    if not any(r["metadata"].get("document_id") == faq["document_id"]
               and r["metadata"].get("source") == faq["source"]
               and r["metadata"].get("policy_version") == faq["policy_version"]
               and faq["expected_fact"] in r["document"] for r in snapshot["rows"]):
        raise ValueError("Frozen FAQ provenance/fact not found in current collection")
    skills = SkillManager(ROOT / "skills")
    skills.load()
    historical = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in ROOT.glob("t09*.json")}
    manifest = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "frozen_at": now.isoformat(), "runs": args.runs, "case_count": len(catalog),
        "model": cfg["model"], "base_url": cfg.get("base_url"),
        "agent_temperature": args.temperature, "agent_max_tokens": args.max_tokens,
        "cases_hash": digest(catalog), "fixture_hash": digest(fixture),
        "rag_collection": kb._collection_name, "rag_hash": digest(snapshot), "rag_threshold": kb.min_score,
        "chroma_host": args.chroma_host, "chroma_port": args.chroma_port,
        "historical_hashes": historical, "context": "empty fixed context/history for fresh sessions",
        "cache": "fresh manager per case/arm; original cache/rewrite/rerank semantics",
        "skills_hash": digest([{"name": s.name, "content": s.content, "agents": s.agents,
                               "keywords": s.keywords} for s in skills.skills]),
        "runner_sources": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__), Path(__file__).with_name("topology_experiment.py"),
                                     Path(__file__).with_name("topology_eval.py"))}}
    save(args.output_dir / "t10_manifest.json", manifest)
    save(args.output_dir / "t10_frozen_cases.json", catalog)
    save(args.output_dir / "t10_frozen_fixture.json", fixture)
    records = []
    for repetition in range(1, args.runs+1):
        for index, case in enumerate(catalog):
            arms = ("multi_agent", "single_agent") if (repetition+index) % 2 else ("single_agent", "multi_agent")
            for arm in arms:
                record = await run_case(arm, case, fixture, now, cfg, kb, skills, args, repetition)
                records.append(record)
                save(raw_path, records)
                report = compare(catalog, records, manifest)
                save(args.output_dir / "t10_topology_comparison.json", report)
                (args.output_dir / "t10_topology_comparison.md").write_text(markdown(report), encoding="utf-8")
                row = report["arms"][arm]["cases"][-1]
                print(json.dumps({"run": repetition, "case": case["id"], "arm": arm,
                    "success": row["task_success"], "checks": row["checks"],
                    "tools": [t["tool_name"] for t in record.get("tool_traces", [])],
                    "model_calls": len(record["model_calls"]), "elapsed_ms": record["elapsed_ms"],
                    "error": record.get("error")}, ensure_ascii=False), flush=True)
    manifest["rag_unchanged"] = digest(collection_snapshot(kb)) == manifest["rag_hash"]
    manifest["historical_unchanged"] = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
                                          for p, h in historical.items())
    manifest["complete"] = len(records) == args.runs * len(catalog) * 2
    report = compare(catalog, records, manifest)
    save(args.output_dir / "t10_manifest.json", manifest)
    save(args.output_dir / "t10_topology_comparison.json", report)
    (args.output_dir / "t10_topology_comparison.md").write_text(markdown(report), encoding="utf-8")
    return 1 if any(r.get("error") for r in records) or not manifest["rag_unchanged"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/t10_cases.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation/reports/t10_complete")
    parser.add_argument("--chroma-host", default="127.0.0.1")
    parser.add_argument("--chroma-port", type=int, default=8001)
    parser.add_argument("--temperature", type=float, default=.2)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    load_dotenv(ROOT / ".env")
    logging.getLogger().setLevel(logging.WARNING)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
