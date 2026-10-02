"""Seed or explicitly rebuild the isolated CartCare demo knowledge collection.

Run with the API stopped when using --reset. The legacy knowledge_base
collection and any record without known demo provenance are never deleted.
"""

from __future__ import annotations

import argparse
import os

from .knowledge_base import KnowledgeBase


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the versioned CartCare demo RAG collection")
    parser.add_argument("--reset", action="store_true", help="rebuild known demo records only; stop the API first")
    args = parser.parse_args()
    kb = KnowledgeBase(chroma_host=os.getenv("CHROMA_HOST", "localhost"),
                       chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
                       seed_defaults=False)
    if args.reset:
        count = kb.rebuild_demo_collection()
    elif kb.doc_count == 0:
        kb._load_default_docs()
        count = kb.doc_count
    else:
        count = kb.doc_count
    print(f"collection={kb.COLLECTION_NAME} chunks={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
