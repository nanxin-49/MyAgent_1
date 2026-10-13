"""Seed or explicitly rebuild the isolated CartCare demo knowledge collection.

Run with the API stopped when using --reset. The legacy knowledge_base
collection and any record without known demo provenance are never deleted.
"""

from __future__ import annotations

import argparse
import os
import json

from .knowledge_base import KnowledgeBase
from .knowledge_embeddings import EMBEDDING_VERSION
from .default_knowledge_asset import load_approved_defaults, APPROVED_SHA256
from .default_knowledge_publication import (
    publish_approved, write_backup, restore_backup, assert_owned, read_backup,
    snapshot, encoded, verify_current,
)


class ExistingKnowledgeBase(KnowledgeBase):
    """Read/check/restore must not silently create a missing target collection."""
    def _open_collection(self):
        collection = self._client.get_collection(name=self._collection_name)
        actual = collection.metadata or {}
        if actual.get('embedding_version') != EMBEDDING_VERSION or actual.get('hnsw:space') != 'cosine':
            raise ValueError('existing collection has incompatible embedding configuration')
        return collection


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the versioned CartCare demo RAG collection")
    parser.add_argument("--reset", action="store_true", help="rebuild known demo records only; stop the API first")
    parser.add_argument("--check-assets", action="store_true", help="validate approved files without connecting to Chroma")
    parser.add_argument("--backup", metavar="FILE", help="write a full backup and exit; never overwrite")
    parser.add_argument("--backup-file", metavar="FILE", help="verified unchanged backup required for nonempty publish/reset")
    parser.add_argument("--restore", metavar="FILE", help="restore the same collection from verified backup with API stopped")
    parser.add_argument("--verify", action="store_true", help="read-only release checks and separate business diagnostics")
    args = parser.parse_args()
    docs = load_approved_defaults()
    if sum(bool(v) for v in (args.reset, args.backup, args.restore, args.verify, args.check_assets)) > 1:
        parser.error("choose only one operation")
    if args.check_assets:
        print(f"approved_documents={len(docs)} asset_sha256={APPROVED_SHA256}")
        return 0
    factory = ExistingKnowledgeBase if (args.backup or args.restore or args.verify or args.reset) else KnowledgeBase
    kb = factory(chroma_host=os.getenv("CHROMA_HOST", "localhost"),
                       chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
                       seed_defaults=False)
    if args.verify:
        print(json.dumps(verify_current(kb),ensure_ascii=False,indent=2))
        return 0  # Mechanical pass; inspect business_all_expected_usable separately.
    if args.backup:
        print(f"backup_sha256={write_backup(kb, args.backup)}")
        return 0
    if args.restore:
        count = restore_backup(kb, args.restore)
    elif args.reset:
        assert_owned(kb)
        if not args.backup_file or encoded(read_backup(kb, args.backup_file)) != encoded(snapshot(kb)):
            raise ValueError("reset requires a verified unchanged full backup; prefer in-place publish")
        count = kb.rebuild_demo_collection()
    else:
        count = publish_approved(kb, args.backup_file)
    print(f"collection={kb._collection_name} chunks={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
