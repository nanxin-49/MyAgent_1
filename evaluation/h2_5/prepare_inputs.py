"""Prepare frozen v2 corpus chunks and dev/test queries for embedding precompute.

Runs in the project environment (Python 3.12) and writes only to the gitignored
``cash/cache/h2_5`` directory. No model is loaded here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.rag_quality.dev_calibration import load_dev_frozen
from evaluation.rag_quality.run_baseline import chunk_catalog, load_frozen
from mcp.knowledge_base import KnowledgeBase
from mcp.rag_contract import KnowledgeDocument

ROOT = Path(__file__).resolve().parents[2]
RAG_DIR = ROOT / "evaluation/rag_quality"
DEFAULT_OUT = ROOT / "cash/cache/h2_5/inputs.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _titles(corpus: dict) -> dict[tuple[str, str | None], str]:
    return {(doc["document_id"], doc.get("policy_version")): doc["title"]
            for doc in corpus["documents"]}


def build_inputs() -> dict:
    corpus, test, lock = load_frozen("v2")
    _, dev, _ = load_dev_frozen("v2", RAG_DIR)
    titles = _titles(corpus)
    chunks = chunk_catalog(corpus)
    for chunk in chunks:
        chunk["title"] = titles[(chunk["document_id"], chunk["policy_version"])]
    queries = []
    for split, dataset in (("test", test), ("dev", dev)):
        for case in dataset["cases"]:
            queries.append({"split": split, "case_id": case["case_id"],
                            "query": case["query"]})
    publications = []
    for raw in corpus["documents"]:
        doc = KnowledgeDocument.model_validate(raw)
        key = KnowledgeBase._key(doc)
        publications.append({"key": key, "title": "publication", "content": key,
                             "content_sha256": hashlib.sha256(key.encode()).hexdigest()})
    return {
        "schema": "cartcare.h2_5.embedding_inputs",
        "version": 1,
        "corpus_version": corpus["version"],
        "as_of": corpus["as_of"],
        "test_dataset_version": test["version"],
        "dev_dataset_version": dev["version"],
        "freeze_sha256": {
            name: _sha256(RAG_DIR / name) for name in (
                "freeze_v2.json", "corpus_v1.json", "dataset_v2.json",
                "dev_dataset_v2.json")
        },
        "chunks": chunks,
        "publications": publications,
        "queries": queries,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    payload = build_inputs()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({"output": str(output), "chunks": len(payload["chunks"]),
                      "queries": len(payload["queries"]),
                      "sha256": _sha256(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
