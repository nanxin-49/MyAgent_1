"""H2-5 B0 / semantic / hybrid retrieval comparison on the frozen v2 set.

The semantic vectors are precomputed in the conda environment; this runner only
uses the project environment and a fail-closed lookup adapter. It reuses the
existing B0 capture, N06/N07 finalization, calibration replay, and metrics.

Run:
  uv run python -m evaluation.h2_5.run_semantic_retrieval --split dev
  uv run python -m evaluation.h2_5.run_semantic_retrieval --split test
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import platform
import subprocess
import time
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import chromadb

from evaluation.h2_5.embedding_adapter import load_vectors, patched_knowledge_module
from evaluation.h2_5.hybrid import BM25, rrf_order
from evaluation.rag_quality.dev_calibration import (
    GRID, curve_point, load_dev_frozen, replay, select_threshold, unique_repeat,
)
from evaluation.rag_quality.run_baseline import (
    ROOT, active_identities, aggregate, chunk_catalog, digest, identify_hit,
    load_frozen, make_manager, observe, retrieve_b0, write_json,
)
from mcp.knowledge_base import KnowledgeBase
from mcp.tool_manager import RerankResult, ToolResult

RAG_DIR = ROOT / "evaluation/rag_quality"
HERE = Path(__file__).resolve().parent
DEFAULT_VECTORS = ROOT / "cash/cache/h2_5/vectors.json"
OUT_ROOT = ROOT / "evaluation/reports/H2-5"
B0_CALIBRATION = (RAG_DIR / "calibration/20261013T025559Z-ed4a1cb4"
                  / "b0_lexical_calibration_v2.json")
LOCKED_B0_THRESHOLD = 0.20
B0_GROUP = "b0"
SEMANTIC_GROUP = "semantic"
HYBRID_GROUP = "hybrid"
GROUPS = (B0_GROUP, SEMANTIC_GROUP, HYBRID_GROUP)
SCORE_KIND = "one_minus_chroma_distance"


class FrozenDatetime(datetime):
    fixed: datetime

    @classmethod
    def now(cls, tz=None):
        return cls.fixed.astimezone(tz) if tz else cls.fixed.replace(tzinfo=None)


class CountingCollection:
    def __init__(self, collection):
        self.collection = collection
        self.queries = 0
        self.last_query_result = None

    def __getattr__(self, name):
        return getattr(self.collection, name)

    def query(self, **kwargs):
        self.queries += 1
        self.last_query_result = self.collection.query(**kwargs)
        return self.last_query_result


def _shas() -> dict:
    return {name: digest(RAG_DIR / name) for name in (
        "corpus_v1.json", "dataset_v2.json", "dev_dataset_v2.json", "freeze_v2.json")}


def _dataset(split: str):
    if split == "dev":
        corpus, dataset, lock = load_dev_frozen("v2", RAG_DIR)
    elif split == "test":
        corpus, dataset, lock = load_frozen("v2")
    else:
        raise ValueError("split must be dev or test")
    titles = {(doc["document_id"], doc.get("policy_version")): doc["title"]
              for doc in corpus["documents"]}
    chunks = chunk_catalog(corpus)
    for chunk in chunks:
        chunk["title"] = titles[(chunk["document_id"], chunk["policy_version"])]
    return corpus, dataset, lock, {chunk["chunk_id"]: chunk for chunk in chunks}


def _collection_metadata(group: str, run_id: str, model: dict | None) -> dict:
    if group == B0_GROUP:
        return {"dataset_kind": "evaluation", "embedding_version": "char-bigram-1024-v1",
                "hnsw:space": "cosine", "evaluation_owner": run_id,
                "group": group, "dimensions": 1024}
    return {"dataset_kind": "evaluation", "embedding_version": model["embedding_version"],
            "hnsw:space": "cosine", "evaluation_owner": run_id,
            "group": group, "dimensions": model["dimensions"],
            "model_id": model["model_id"], "revision": model["revision"],
            "weights_sha256": model["weights_sha256"]}


def _publish(kb: KnowledgeBase, corpus: dict, chunks: dict) -> dict:
    kb.add_documents(corpus["documents"])
    first = kb._snapshot()
    kb.add_documents(corpus["documents"])
    if kb._snapshot() != first:
        raise RuntimeError("identical republication changed corpus / chunk IDs")
    if kb.doc_count != len(chunks):
        raise RuntimeError("physical chunk count differs from frozen corpus")
    return first


def _enrich_dev_candidates(row: dict, snapshot: dict, case: dict) -> None:
    for rank, hit in enumerate(row.get("candidates") or [], 1):
        chunk_id = hit.get("frozen_chunk_id")
        if not chunk_id or chunk_id not in snapshot:
            continue
        _, metadata = snapshot[chunk_id]
        hit.update(chunk_id=chunk_id, rank=rank, metadata=metadata,
                   raw_distance=1.0 - float(hit["score"]),
                   valid_at_as_of=True,
                   gold_match=bool(case.get("answerable") and chunk_id == case.get("gold_chunk_id")))
        if hit.get("score") != 1.0 - hit["raw_distance"]:
            raise RuntimeError("candidate score/distance mismatch")


def _semantic_candidates(kb: KnowledgeBase, query: str, chunks: dict,
                         candidate_k: int = 20) -> list[dict]:
    old = kb.min_score
    kb.min_score = -1.0
    try:
        hits = kb.search(query, top_k=candidate_k)
    finally:
        kb.min_score = old
    # Do not add extra keys: RetrievalHit forbids extras and _finalize_rag
    # re-validates every candidate. observe() adds frozen_chunk_id later.
    return hits


async def _finalize(manager, usable: list[dict], top_k: int = 5) -> ToolResult:
    if not usable:
        return ToolResult(True, [], "knowledge_search",
                          retrieval_status="low_confidence")
    return await manager._finalize_rag(
        "knowledge_search", usable, RerankResult(usable, False, "not_requested"), top_k)


async def _retrieve_semantic(kb, manager, query, chunks, threshold, *, top_k=5):
    candidates = _semantic_candidates(kb, query, chunks)
    usable = [hit for hit in candidates if hit["score"] >= threshold]
    final = (await _finalize(manager, usable, top_k)) if usable else ToolResult(
        True, [], "knowledge_search", retrieval_status="low_confidence")
    return ToolResult(True, candidates, "knowledge_search", attempts=0), final


async def _retrieve_hybrid(kb, manager, query, chunks, threshold, bm25, *, top_k=5):
    candidates = _semantic_candidates(kb, query, chunks)
    passing = [hit for hit in candidates if hit["score"] >= threshold]
    chunk_to_hit = {identify_hit(hit, chunks): hit for hit in passing}
    ranked = rrf_order([{**hit, "frozen_chunk_id": identify_hit(hit, chunks)}
                        for hit in passing], bm25.scores(query)) if passing else []
    ordered = [chunk_to_hit[item["frozen_chunk_id"]] for item in ranked
               if item.get("frozen_chunk_id") in chunk_to_hit]
    final = (await _finalize(manager, ordered, top_k)) if ordered else ToolResult(
        True, [], "knowledge_search",
        retrieval_status="low_confidence" if candidates else "no_answer")
    return ToolResult(True, candidates, "knowledge_search", attempts=0), final


async def _capture(group: str, *, split: str, dataset: dict, corpus: dict, chunks: dict,
                   vectors, model_meta: dict | None, threshold: float, repeats: int,
                   host: str, port: int, run_id: str, output: Path) -> dict:
    collection = f"cartcare_h25_{group}_{uuid.uuid4().hex}"
    client = chromadb.HttpClient(host=host, port=port,
                                settings=chromadb.Settings(anonymized_telemetry=False))
    client.create_collection(collection, metadata=_collection_metadata(group, run_id, model_meta))
    manifest = {
        "run_id": run_id, "group": group, "split": split,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty_worktree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {package: version(package) for package in
                     ("chromadb-client", "pydantic", "numpy", "httpx")},
        "collection": collection, "endpoint": f"{host}:{port}",
        "threshold": threshold, "top_k": 5, "repeats": repeats,
        "score_kind": SCORE_KIND, "distance": "cosine; score=1-distance",
        "as_of": corpus["as_of"], "dataset_version": dataset["version"],
        "corpus_version": corpus["version"], "input_sha256": _shas(),
        "embedding_version": ("char-bigram-1024-v1" if group == B0_GROUP
                              else model_meta["embedding_version"]),
        "dimensions": (1024 if group == B0_GROUP else model_meta["dimensions"]),
        "model": None if group == B0_GROUP else model_meta,
        "rewrite": False, "llm_rerank": False, "cache": False,
        "collection_deleted": False, "outcome": "running",
    }
    observations: list[dict] = []
    snapshot = None
    try:
        context = (nullcontext() if group == B0_GROUP
                   else patched_knowledge_module(vectors))
        with context:
            kb = KnowledgeBase(chroma_host=host, chroma_port=port,
                               collection_name=collection, seed_defaults=False,
                               min_score=threshold)
            snapshot = _publish(kb, corpus, chunks)
            kb._collection = CountingCollection(kb._collection)
            fixed_time = datetime.fromisoformat(corpus["as_of"].replace("Z", "+00:00"))
            FrozenDatetime.fixed = fixed_time
            manager = make_manager(kb)
            bm25 = (None if group != HYBRID_GROUP else BM25({
                chunk_id: chunk["content"] for chunk_id, chunk in chunks.items()
                if (chunk["document_id"], chunk["policy_version"]) in active_identities(corpus)
            }))
            with patch("mcp.knowledge_base.datetime", FrozenDatetime):
                eligible = set().union(*kb._eligible(snapshot, fixed_time).values())
                manifest["eligible_chunk_ids"] = sorted(eligible)
                for repeat in range(1, repeats + 1):
                    for case in dataset["cases"]:
                        previous = kb._collection.queries
                        started = time.perf_counter()
                        if group == B0_GROUP:
                            raw, final = await retrieve_b0(manager, case["query"])
                        elif group == SEMANTIC_GROUP:
                            raw, final = await _retrieve_semantic(
                                kb, manager, case["query"], chunks, threshold)
                        else:
                            raw, final = await _retrieve_hybrid(
                                kb, manager, case["query"], chunks, threshold, bm25)
                        elapsed = (time.perf_counter() - started) * 1000
                        row = observe({**case, "category": case.get("category", "development")},
                                      raw, final, chunks, elapsed, repeat,
                                      kb._collection.queries - previous)
                        row["group"] = group
                        row["threshold"] = threshold
                        row["query_embedding_latency_ms"] = (
                            vectors.query_latency_ms(case["query"])
                            if vectors is not None and group != B0_GROUP else None)
                        if split == "dev":
                            _enrich_dev_candidates(row, snapshot, case)
                        observations.append(row)
                if manager._client.calls:
                    raise RuntimeError("unexpected model invocation")
                if kb._snapshot() != snapshot:
                    raise RuntimeError("retrieval changed frozen corpus")
        manifest["outcome"] = ("measured" if all(row["success"] for row in observations)
                               else "partial_dependency_failure")
        summaries = {str(repeat): aggregate([row for row in observations
                                             if row["repeat"] == repeat])
                     for repeat in range(1, repeats + 1)}
        write_json(output / "observations.json", observations)
        write_json(output / "summary.json", summaries)
        write_json(output / "manifest.json", manifest)
        return {"observations": observations, "summaries": summaries,
                "manifest": manifest, "snapshot": snapshot, "output": output}
    finally:
        try:
            client.delete_collection(collection)
            manifest["collection_deleted"] = True
        finally:
            write_json(output / "manifest.json", manifest)


async def _calibrate_semantic_async(observations, dataset, chunks, snapshot, output,
                                    manifest, model_meta) -> dict:
    cases = dataset["cases"]
    live = KnowledgeBase.__new__(KnowledgeBase)
    live._snapshot = lambda: copy.deepcopy(snapshot)
    replay_manager = make_manager(live)
    fixed_time = datetime.fromisoformat(manifest["as_of"].replace("Z", "+00:00"))
    curves, signatures = {}, []
    for repeat in range(1, manifest["repeats"] + 1):
        group = unique_repeat(observations, cases, repeat)
        by_id = {row["case_id"]: row for row in group}
        signatures.append([(row["case_id"], row["candidates"]) for row in group])
        curve = []
        for threshold in GRID:
            rows = [await replay(case, by_id[case["case_id"]], threshold,
                                 replay_manager, fixed_time, chunks) for case in cases]
            curve.append(curve_point(rows, threshold))
        curves[str(repeat)] = curve
    if any(signature != signatures[0] for signature in signatures) or any(
            curves[key] != curves["1"] for key in curves):
        raise RuntimeError("development candidates/curve are not repeatable")
    chosen = select_threshold(curves["1"])
    record = {
        "schema": "cartcare.h2_5.semantic_calibration", "version": 1,
        "status": "locked" if chosen else "calibration_infeasible",
        "selected_threshold": chosen["threshold"] if chosen else None,
        "selected_dev_metrics": chosen,
        "objective": "max dev Recall@5 subject to no-answer false positives <= 1/8",
        "threshold_grid": list(GRID), "score_kind": SCORE_KIND,
        "model": model_meta, "dataset_version": manifest["dataset_version"],
        "input_sha256": manifest["input_sha256"],
        "repeats": manifest["repeats"], "test_scores_consumed": False,
        "production_configuration_changed": False,
    }
    write_json(output / "semantic_calibration.json", record)
    write_json(output / "semantic_sweep.json", curves)
    return record


def _embedding_summary(rows: list[dict]) -> dict:
    values = [row["query_embedding_latency_ms"] for row in rows
              if row.get("query_embedding_latency_ms") is not None]
    if not values:
        return {"p50": None, "p95": None, "count": 0}
    ordered = sorted(values)
    def percentile(q):
        position = (len(ordered) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)
    return {"p50": percentile(.5), "p95": percentile(.95), "count": len(values)}


def _summary_with_embedding(summary: dict, rows: list[dict]) -> dict:
    output = copy.deepcopy(summary)
    output["query_embedding_latency_ms"] = _embedding_summary(rows)
    return output


def _b0_calibration_reference() -> dict:
    if not B0_CALIBRATION.exists():
        return {}
    return json.loads(B0_CALIBRATION.read_text(encoding="utf-8"))


async def _run_dev(args, vectors, model_meta) -> int:
    corpus, dataset, lock, chunks = _dataset("dev")
    if (OUT_ROOT / "dev" / "calibration.json").exists() and not args.force:
        raise SystemExit("dev calibration already locked; pass --force to redo it")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = OUT_ROOT / "dev" / run_id
    output.mkdir(parents=True, exist_ok=False)
    semantic_output = output / SEMANTIC_GROUP
    semantic_output.mkdir()
    semantic = await _capture(
        SEMANTIC_GROUP, split="dev", dataset=dataset, corpus=corpus, chunks=chunks,
        vectors=vectors, model_meta=model_meta, threshold=0.0,
        repeats=args.repeats, host=args.host, port=args.port,
        run_id=run_id, output=semantic_output)
    calibration = await _calibrate_semantic_async(
        semantic["observations"], dataset, chunks, semantic["snapshot"],
        semantic_output, semantic["manifest"], model_meta)
    threshold = calibration["selected_threshold"]
    hybrid = None
    if threshold is not None:
        hybrid_output = output / HYBRID_GROUP
        hybrid_output.mkdir()
        hybrid = await _capture(
            HYBRID_GROUP, split="dev", dataset=dataset, corpus=corpus, chunks=chunks,
            vectors=vectors, model_meta=model_meta, threshold=threshold,
            repeats=args.repeats, host=args.host, port=args.port,
            run_id=run_id, output=hybrid_output)
    b0_reference = _b0_calibration_reference()
    pointer = {
        "run_id": run_id,
        "status": calibration["status"],
        "selected_threshold": threshold,
        "semantic_calibration_path": str(semantic_output / "semantic_calibration.json"),
        "semantic_output": str(semantic_output),
        "hybrid_output": str(hybrid["output"]) if hybrid else None,
        "b0_threshold": LOCKED_B0_THRESHOLD,
        "b0_calibration_source": str(B0_CALIBRATION),
        "b0_calibration_sha256": digest(B0_CALIBRATION) if B0_CALIBRATION.exists() else None,
        "b0_selected_dev_metrics": (b0_reference.get("selected_dev_metrics")
                                    if b0_reference else None),
    }
    write_json(OUT_ROOT / "dev" / "calibration.json", pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


async def _run_test(args, vectors, model_meta) -> int:
    calibration_path = OUT_ROOT / "dev" / "calibration.json"
    if not calibration_path.exists():
        raise SystemExit("missing dev calibration; run --split dev first")
    pointer = json.loads(calibration_path.read_text(encoding="utf-8"))
    calibration = json.loads(Path(pointer["semantic_calibration_path"]).read_text(
        encoding="utf-8"))
    threshold = calibration.get("selected_threshold")
    if threshold is None:
        raise SystemExit("semantic calibration is infeasible; no test claim")
    if (OUT_ROOT / "test" / "comparison.json").exists() and not args.force:
        raise SystemExit("test comparison already exists; pass --force to rerun (not a protocol default)")
    corpus, dataset, lock, chunks = _dataset("test")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = OUT_ROOT / "test" / run_id
    output.mkdir(parents=True, exist_ok=False)
    groups = [item.strip() for item in args.groups.split(",") if item.strip()]
    results = {}
    thresholds = {B0_GROUP: LOCKED_B0_THRESHOLD, SEMANTIC_GROUP: threshold,
                  HYBRID_GROUP: threshold}
    for group in groups:
        group_output = output / group
        group_output.mkdir()
        capture = await _capture(
            group, split="test", dataset=dataset, corpus=corpus, chunks=chunks,
            vectors=vectors, model_meta=model_meta, threshold=thresholds[group],
            repeats=args.repeats, host=args.host, port=args.port,
            run_id=run_id, output=group_output)
        summary = _summary_with_embedding(capture["summaries"]["1"],
                                          capture["observations"])
        write_json(group_output / "summary.json", summary)
        results[group] = summary
    comparison = {
        "schema": "cartcare.h2_5.comparison", "version": 1,
        "run_id": run_id, "model": model_meta,
        "b0_threshold": LOCKED_B0_THRESHOLD, "semantic_threshold": threshold,
        "hybrid_threshold": threshold, "groups": results,
        "input_sha256": _shas(), "test_scores_consumed_once": True,
        "semantic_calibration": pointer,
    }
    write_json(output / "comparison.json", comparison)
    write_json(OUT_ROOT / "test" / "comparison.json", comparison)
    lines = ["# H2-5 semantic retrieval comparison", "",
             f"- run: {run_id}",
             f"- model: {model_meta['model_id']} @ {model_meta['revision']}" if model_meta else "- model: none (B0 only)",
             f"- B0 threshold: {LOCKED_B0_THRESHOLD}; semantic/hybrid threshold: {threshold}", "",
             "| Group | Recall@1 | Recall@3 | Recall@5 | MRR | No-answer FPR | Citation precision | Retrieval p50/p95 ms | Embedding p50 ms |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
    for group, summary in results.items():
        def value(key):
            return summary[key]["value"]
        lines.append(
            f"| {group} | {value('Recall@1')} | {value('Recall@3')} | "
            f"{value('Recall@5')} | {value('MRR')} | "
            f"{value('no_answer_false_positive_rate')} | "
            f"{value('citation_evidence_precision')} | "
            f"{summary['latency_ms']['p50']} / {summary['latency_ms']['p95']} | "
            f"{summary['query_embedding_latency_ms']['p50']} |")
    lines += ["", "Test was run once per group with thresholds locked on the dev set.",
              "Semantic query embedding is precomputed; retrieval latency excludes it.",
              "Hybrid uses the semantic threshold as the usability gate and BM25 only reranks."]
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_ROOT / "test" / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


async def main_async(args):
    groups = [item.strip() for item in args.groups.split(",") if item.strip()]
    needs_vectors = args.split == "dev" or any(group in groups for group in
                                               (SEMANTIC_GROUP, HYBRID_GROUP))
    vectors = model_meta = None
    if needs_vectors:
        vectors, payload = load_vectors(args.vectors)
        model_meta = {**payload["model"], "embedding_version": payload["embedding_version"],
                      "runtime": payload["runtime"], "meta": payload["meta"]}
    if args.split == "dev":
        return await _run_dev(args, vectors, model_meta)
    return await _run_test(args, vectors, model_meta)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--groups", default="b0,semantic,hybrid")
    parser.add_argument("--vectors", default=str(DEFAULT_VECTORS))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
