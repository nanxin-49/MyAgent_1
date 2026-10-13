"""Offline-maintenance helpers. Caller must stop every writer before use.

No cross-process transaction/lock is claimed. Backup includes every vector and
collection metadata. This module never connects to Chroma by itself.
"""
import hashlib
import json
import math
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from .default_knowledge_asset import load_approved_defaults, ASSET
from .rag_contract import KnowledgeDocument, RetrievalHit


def target(kb):
    client = getattr(kb, '_client', None)
    settings = client.get_settings() if client is not None and hasattr(client, 'get_settings') else None
    return {'host':getattr(settings,'chroma_server_host',None),
            'port':getattr(settings,'chroma_server_http_port',None),
            'ssl':getattr(settings,'chroma_server_ssl_enabled',None),
            'tenant':getattr(client,'tenant',None),'database':getattr(client,'database',None)}


def snapshot(kb):
    data = kb._collection.get(include=['documents', 'metadatas', 'embeddings'])
    rows = sorted([
        {'id': key, 'document': doc, 'metadata': meta,
         'embedding': [float(v) for v in vector]}
        for key, doc, meta, vector in zip(data['ids'], data['documents'],
                                        data['metadatas'], data['embeddings'])
    ], key=lambda r: r['id'])
    if len(rows) != kb._collection.count():
        raise RuntimeError('snapshot count mismatch; stop writers and retry')
    return {'schema_version':1, 'target':target(kb), 'collection': kb._collection_name,
            'metadata': kb._collection.metadata, 'rows': rows}


def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def assert_owned(kb):
    """Reject unrelated versions, extra documents and malformed legacy identities."""
    docs = load_approved_defaults()
    identities = {(d['document_id'], d['policy_version']): d for d in docs}
    if (kb._collection.metadata or {}).get('dataset_kind') != 'demo':
        raise ValueError('not an explicitly marked demo collection')
    rows = kb._snapshot()
    kb._publications(rows)  # Validate existing manifests, including partial publications.
    for text, meta in rows.values():
        if meta.get('record_type') == 'publication':
            doc = json.loads(text)['document']
            key = (doc.get('document_id'), doc.get('policy_version'))
            approved = identities.get(key)
            if approved is None or KnowledgeDocument.model_validate(doc) != KnowledgeDocument.model_validate(approved):
                raise ValueError('non-approved publication; explicit review required')
        else:
            key = (meta.get('document_id'), meta.get('policy_version'))
            approved = identities.get(key)
            if (approved is None or meta.get('source') != approved['source']
                    or meta.get('doc_type') != approved['doc_type']
                    or meta.get('title') != approved['title']
                    or meta.get('record_type') not in {None, 'chunk'}):
                raise ValueError('unknown record/identity; upgrade refused')
            # Legacy lifecycle must agree with the approved identity, not just its source.
            legacy = dict(approved)
            for field in ('effective_at', 'expires_at', 'publication_status', 'supersedes'):
                if field in meta:
                    legacy[field] = meta[field]
            if KnowledgeDocument.model_validate(legacy) != KnowledgeDocument.model_validate(approved):
                raise ValueError('legacy lifecycle differs from approval')
    return docs


def write_backup(kb, path):
    data = snapshot(kb)
    raw = encoded(data)
    path = Path(path)
    with path.open('xb') as handle:
        handle.write(raw)
    digest = hashlib.sha256(raw).hexdigest()
    with path.with_suffix(path.suffix + '.sha256').open('x', encoding='ascii') as handle:
        handle.write(digest + '\n')
    return digest


def read_backup(kb, path):
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != path.with_suffix(path.suffix + '.sha256').read_text().strip():
        raise ValueError('backup hash mismatch')
    data = json.loads(raw)
    if (data['schema_version'] != 1 or data['target'] != target(kb)
            or data['collection'] != kb._collection_name or data['metadata'] != kb._collection.metadata):
        raise ValueError('backup target/configuration mismatch')
    rows = data['rows']
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate backup IDs')
    if any(len(r['embedding']) != 1024 or not all(math.isfinite(v) for v in r['embedding']) for r in rows):
        raise ValueError('backup vector mismatch')
    return data


def publish_approved(kb, backup_path=None):
    docs = assert_owned(kb)  # Validate everything before the first write.
    if kb._collection.count():
        if backup_path is None:
            raise ValueError('nonempty upgrade requires a verified full backup')
        if encoded(read_backup(kb, backup_path)) != encoded(snapshot(kb)):
            raise ValueError('collection changed since backup; stop and take a new backup')
    return kb.add_documents(docs)


def restore_backup(kb, path):
    """Restore only the same owned collection, after a maintenance-stop decision.

On failure keep service stopped and retry. Restoring legacy data restores the
old fail-closed retrieval state; it is data recovery, not availability recovery.
"""
    docs = assert_owned(kb)
    data = read_backup(kb, path)
    # Check backup identities before deleting current rows.
    identities = {(d['document_id'], d['policy_version'], d['source'], d['doc_type']) for d in docs}
    for row in data['rows']:
        meta = row['metadata']
        doc = json.loads(row['document'])['document'] if meta.get('record_type') == 'publication' else meta
        if (doc.get('document_id'), doc.get('policy_version'), doc.get('source'), doc.get('doc_type')) not in identities:
            raise ValueError('backup contains unrelated records')
    ids = list(kb._snapshot())
    if ids:
        kb._collection.delete(ids=ids)
    rows = data['rows']
    if rows:
        kb._collection.upsert(ids=[r['id'] for r in rows], documents=[r['document'] for r in rows],
                              metadatas=[r['metadata'] for r in rows], embeddings=[r['embedding'] for r in rows])
    if encoded(snapshot(kb)) != encoded(data):
        raise RuntimeError('restore verification failed; keep service stopped')
    return len(rows)


def verify_current(kb):
    """Read-only mechanical release check and separate business diagnostics."""
    assert_owned(kb)
    rows = kb._snapshot()
    publications = kb._publications(rows)
    eligible = kb._eligible(rows,datetime.now(timezone.utc))
    if len(rows) != 12 or len(publications) != 6 or sum(map(len,eligible.values())) != 6:
        raise ValueError('release requires six ready publications and six effective chunks')
    expected = json.loads(ASSET.read_text(encoding='utf-8'))['documents']
    for row in expected:
        doc = KnowledgeDocument.model_validate(row['document'])
        publication = publications[kb._key(doc)][1]
        if (publication['state'] != 'ready' or publication['revision'] != row['publication_revision']
                or publication['chunk_ids'] != [row['chunk_id']]
                or rows[row['chunk_id']][0] != doc.content):
            raise ValueError('release revision/body mismatch')
    if any(len(r['embedding']) != 1024 or not all(math.isfinite(v) for v in r['embedding'])
           for r in snapshot(kb)['rows']):
        raise ValueError('release vector mismatch')
    cases = []
    for row in expected:
        doc = row['document']
        query = f"请提供CartCare当前{doc['title']}能力边界说明"
        hits = kb.search(query,5)
        valid = asyncio.run(kb.validate_hits_async(hits))
        usable = [h for h in valid if RetrievalHit.model_validate(h).retrieval_status.value == 'usable']
        cases.append({'query':query, 'expected_document':doc['document_id'],
            'raw_expected_found':any(h['document_id']==doc['document_id'] for h in hits),
            'usable_expected_found':any(h['document_id']==doc['document_id'] for h in usable),
            'raw_hits':hits,'usable_hits':usable})
    return {'mechanical_passed':True,'publications':6,'effective_chunks':6,'vector_dimensions':1024,
            'min_score':kb.min_score,'business_cases':cases,
            'business_all_expected_usable':all(r['usable_expected_found'] for r in cases)}
