"""Precompute bge-small-zh-v1.5 vectors for the H2-5 retrieval comparison.

This script intentionally runs in the existing conda environment (Python 3.11,
torch/transformers), not in the project ``.venv``. It downloads/loads a fixed
model revision, writes vectors to a gitignored cache, and never edits project
dependencies or production modules.

Run with:
  CUDA_VISIBLE_DEVICES= "D:/Anaconda/envs/pytorch311_RL/python.exe" \
    -m evaluation.h2_5.precompute_embeddings --inputs cash/cache/h2_5/inputs.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

MODEL_ID = "BAAI/bge-small-zh-v1.5"
REVISION = "7999e1d3359715c523056ef9478215996d62a620"
WEIGHTS_SHA256 = "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
EMBEDDING_VERSION = "bge-small-zh-v1.5-512-v1"
MAX_TOKENS = 512
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "cash/cache/h2_5/hf"
DEFAULT_OUT = ROOT / "cash/cache/h2_5/vectors.json"
DEFAULT_SMOKE = ROOT / "cash/cache/h2_5/smoke.json"
ALLOW_PATTERNS = [
    "config.json", "config_sentence_transformers.json", "modules.json",
    "sentence_bert_config.json", "special_tokens_map.json", "tokenizer.json",
    "tokenizer_config.json", "vocab.txt", "tokenizer.model",
    "sentencepiece.bpe.model", "model.safetensors", "1_Pooling/config.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rss_mb() -> tuple[float, float]:
    import psutil
    info = psutil.Process().memory_info()
    rss = getattr(info, "rss", 0) / (1024 * 1024)
    peak = getattr(info, "peak_wset", getattr(info, "rss", 0)) / (1024 * 1024)
    return round(rss, 1), round(peak, 1)


def _download(cache_dir: Path, *, local_files_only: bool) -> Path:
    from huggingface_hub import snapshot_download
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_download(
        repo_id=MODEL_ID,
        revision=REVISION,
        local_dir=str(cache_dir),
        allow_patterns=ALLOW_PATTERNS,
        local_files_only=local_files_only,
        max_workers=4,
    )
    return Path(path)


def _verify(model_dir: Path) -> dict:
    weights = model_dir / "model.safetensors"
    if not weights.exists():
        raise FileNotFoundError(f"model.safetensors missing in {model_dir}")
    actual = _sha256(weights)
    if actual != WEIGHTS_SHA256:
        raise ValueError(f"model weight hash mismatch: {actual} != {WEIGHTS_SHA256}")
    files = {}
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json",
                 "vocab.txt", "1_Pooling/config.json"):
        path = model_dir / name
        files[name] = _sha256(path) if path.exists() else None
    return {"weights_sha256": actual, "file_sha256": files,
            "weights_bytes": weights.stat().st_size}


def _load(model_dir: Path):
    import torch
    from transformers import AutoModel, AutoTokenizer
    torch.set_num_threads(4)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModel.from_pretrained(str(model_dir), local_files_only=True)
    model.eval()
    return torch, tokenizer, model


def _embed(torch, tokenizer, model, texts: list[str]) -> tuple[list[list[float]], list[float]]:
    vectors, latencies = [], []
    for text in texts:
        inputs = tokenizer(text, return_tensors="pt", truncation=False)
        length = int(inputs["input_ids"].shape[1])
        if length > MAX_TOKENS:
            raise ValueError(f"input exceeds {MAX_TOKENS} tokens ({length})")
        started = time.perf_counter()
        with torch.inference_mode():
            output = model(**inputs)
        vector = output.last_hidden_state[:, 0, :]
        vector = torch.nn.functional.normalize(vector, p=2, dim=1)[0]
        latencies.append(round((time.perf_counter() - started) * 1000, 3))
        vectors.append([float(value) for value in vector.tolist()])
    return vectors, latencies


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args(argv)
    inputs_path = Path(args.inputs)
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    cache_dir = Path(args.cache_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    model_dir = _download(cache_dir, local_files_only=args.local_files_only)
    model_meta = _verify(model_dir)
    rss_after_download, peak_after_download = _rss_mb()
    torch, tokenizer, model = _load(model_dir)
    rss_after_load, peak_after_load = _rss_mb()

    chunks = inputs["chunks"]
    publications = inputs.get("publications") or []
    queries = inputs["queries"]
    if args.smoke:
        chunks = chunks[:2]
        publications = publications[:2]
        queries = queries[:2]
    document_items = chunks + publications
    document_texts = [f"{chunk['title']}\n{chunk['content']}" for chunk in document_items]
    query_texts = [QUERY_PREFIX + item["query"] for item in queries]
    load_started = time.perf_counter()
    document_vectors, document_latencies = _embed(
        torch, tokenizer, model, document_texts)
    chunk_encode_ms = round((time.perf_counter() - load_started) * 1000, 1)
    query_started = time.perf_counter()
    query_vectors, query_latencies = _embed(
        torch, tokenizer, model, query_texts)
    query_encode_ms = round((time.perf_counter() - query_started) * 1000, 1)
    rss_after_encode, peak_after_encode = _rss_mb()
    dimensions = len(document_vectors[0])
    if any(len(vector) != dimensions for vector in document_vectors + query_vectors):
        raise ValueError("inconsistent embedding dimensions")
    if any(not all(value == value and abs(value) != float("inf")
                   for value in vector)
           for vector in document_vectors + query_vectors):
        raise ValueError("non-finite embedding value")
    payload = {
        "schema": "cartcare.h2_5.embedding_vectors",
        "version": 1,
        "embedding_version": EMBEDDING_VERSION,
        "model": {
            "model_id": MODEL_ID, "revision": REVISION,
            "weights_sha256": model_meta["weights_sha256"],
            "weights_bytes": model_meta["weights_bytes"],
            "file_sha256": model_meta["file_sha256"],
            "dimensions": dimensions, "pooling": "cls", "normalization": "l2",
            "query_prefix": QUERY_PREFIX, "document_format": "title\\ncontent",
            "max_tokens": MAX_TOKENS,
        },
        "runtime": {
            "python": __import__("sys").version.split()[0],
            "torch": getattr(__import__("torch"), "__version__", None),
            "transformers": getattr(__import__("transformers"), "__version__", None),
            "device": "cpu", "threads": 4, "dtype": "float32",
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "chunks": {chunk["chunk_id"]: {"vector": vector, "title": chunk["title"],
                                       "content_sha256": chunk["content_hash"]}
                   for chunk, vector in zip(chunks, document_vectors)},
        "publications": {item["key"]: {"vector": vector, "title": item["title"],
                                        "content_sha256": item["content_sha256"]}
                         for item, vector in zip(publications,
                                                 document_vectors[len(chunks):])},
        "queries": {item["query"]: {"vector": vector, "latency_ms": latency,
                                    "split": item["split"], "case_id": item["case_id"]}
                    for item, vector, latency in zip(queries, query_vectors, query_latencies)},
        "meta": {
            "inputs_sha256": _sha256(inputs_path),
            "smoke": bool(args.smoke),
            "dimensions": dimensions,
            "chunk_count": len(chunks), "publication_count": len(publications),
            "query_count": len(queries),
            "chunk_encode_ms": chunk_encode_ms, "query_encode_ms": query_encode_ms,
            "rss_mb_after_download": rss_after_download,
            "peak_rss_mb_after_download": peak_after_download,
            "rss_mb_after_load": rss_after_load,
            "peak_rss_mb_after_load": peak_after_load,
            "rss_mb_after_encode": rss_after_encode,
            "peak_rss_mb_after_encode": peak_after_encode,
            "peak_rss_mb_sampled_note": "psutil peak_wset sampled after phases; may miss short peaks",
            "started_at_utc": started_at,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    output = Path(args.output or (DEFAULT_SMOKE if args.smoke else DEFAULT_OUT))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "smoke": bool(args.smoke),
                      "chunks": len(chunks), "queries": len(queries),
                      "dimensions": dimensions,
                      "peak_rss_mb_after_encode": peak_after_encode,
                      "sha256": _sha256(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
