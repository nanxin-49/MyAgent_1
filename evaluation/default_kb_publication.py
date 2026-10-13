"""Isolated HTTP preparation evidence. Never opens the actual default collection.

Run: uv run python -m evaluation.default_kb_publication
Creates unique owned collections first, then uses KB with seeding disabled.
Legacy fixture comes from the preserved old report, NOT the live default DB.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone

import chromadb
from mcp.knowledge_base import KnowledgeBase
from mcp.default_knowledge_asset import load_approved_defaults, ASSET, APPROVAL, APPROVED_SHA256
from mcp.default_knowledge_publication import snapshot, encoded, write_backup, publish_approved, restore_backup, verify_current
from mcp.knowledge_embeddings import EMBEDDING_VERSION, embed_document
from mcp.rag_contract import KnowledgeDocument, RetrievalHit
from evaluation.rag_quality.run_baseline import make_manager, retrieve_b0

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evaluation/reports/hardening/A05/default-kb-publication-20261013'
LEGACY = ROOT / 'evaluation/reports/hardening/A05/b0-calibrated-20261013/default_snapshot_formal.json'


class Fault:
    """Inject transport-like failure AFTER/BEFORE a real server mutation."""
    def __init__(self, collection, operation, nth, after=False):
        self.collection, self.operation, self.nth, self.after = collection, operation, nth, after
        self.calls = 0
    def __getattr__(self, name):
        original = getattr(self.collection, name)
        if name != self.operation:
            return original
        def invoke(*args, **kwargs):
            self.calls += 1
            if self.calls == self.nth:
                if self.after:
                    original(*args, **kwargs)
                raise RuntimeError('injected HTTP acknowledgement/mutation failure')
            return original(*args, **kwargs)
        return invoke


def verify(kb, approved, result):
    result['release_verifier'] = verify_current(kb)
    rows = kb._snapshot()
    pubs = kb._publications(rows)
    eligible = kb._eligible(rows, datetime.now(timezone.utc))
    assert len(rows) == 12 and len(pubs) == 6 and len(eligible) == 6
    assert sum(len(v) for v in eligible.values()) == 6
    before_effective = kb._eligible(rows, datetime(2026,9,29,tzinfo=timezone.utc))
    assert sum(len(v) for v in before_effective.values()) == 5
    result['refund_not_yet_effective_excluded'] = True
    vectors = snapshot(kb)
    assert all(len(r['embedding']) == 1024 for r in vectors['rows'])
    result['publication_records'] = 6
    result['effective_chunks'] = 6
    result['vector_dimensions'] = 1024
    result['queries'] = []
    manager = make_manager(kb)  # Real executor/N07 finalizer; no model/rewrite/rerank.
    allowed = [i for group in eligible.values() for i in group]
    for item in json.loads(ASSET.read_text(encoding='utf-8'))['documents']:
        doc = item['document']
        pub = pubs[kb._key(KnowledgeDocument.model_validate(doc))][1]
        assert pub['state'] == 'ready' and pub['revision'] == item['publication_revision']
        assert pub['chunk_ids'] == [item['chunk_id']]
        text, meta = rows[item['chunk_id']]
        assert text == doc['content'] and meta['content_hash'] == item['content_sha256']
        # Every actual stored vector is retrievable, rank 1, without publication candidates.
        raw = kb._collection.query(query_embeddings=[embed_document(doc['title'], doc['content'])],
              n_results=5, where={'chunk_id':{'$in':allowed}}, include=['metadatas','distances'])
        assert raw['ids'][0][0] == item['chunk_id']
        assert all(m['record_type'] == 'chunk' for m in raw['metadatas'][0])
        # New title-anchored business acceptance probes; no frozen questions/model/calibration.
        query = f"请提供CartCare当前{doc['title']}能力边界说明"
        raw_result, final_result = asyncio.run(retrieve_b0(manager, query, 5))
        assert raw_result.success and final_result.success
        hits = raw_result.data
        valid = asyncio.run(kb.validate_hits_async(hits))
        assert len(hits) == len(valid)
        matched = [h for h in valid if h['document_id'] == doc['document_id']]
        result['queries'].append({'case_id':f"DEFAULT-KB-{len(result['queries'])+1:02}",
              'query':query,'expected_document':doc['document_id'],
              'found':bool(matched),'hits':hits,'raw_self_vector_rank':1,
              'final_hits':final_result.data,'final_citations':final_result.citations,
              'final_retrieval_status':final_result.retrieval_status})
        assert matched, f"new acceptance retrieval failed: {doc['title']}"
        for hit in valid:
            RetrievalHit.model_validate(hit)  # Usable citations match; low-score hits carry none.
        result['queries'][-1]['usable_expected'] = any(h['retrieval_status'] == 'usable' for h in matched)
        assert all(h['score'] >= .35 and h['citation'] for h in final_result.data)


def main():
    docs = load_approved_defaults()  # Before any network calls.
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ['NO_PROXY'] = '127.0.0.1,localhost'
    client = chromadb.HttpClient(host='127.0.0.1', port=8001, settings=chromadb.Settings(anonymized_telemetry=False))
    client.heartbeat()
    evidence = {'started_at_utc':datetime.now(timezone.utc).isoformat(), 'asset_sha256':APPROVED_SHA256,
       'approval_file_sha256':hashlib.sha256(APPROVAL.read_bytes()).hexdigest(),
       'legacy_fixture_sha256':hashlib.sha256(LEGACY.read_bytes()).hexdigest(),
       'embedding_version':EMBEDDING_VERSION,'threshold':0.35,'top_k':5,
       'model_calls':0,'default_collection_accessed':False,'scenarios':[],'cleanup':[]}
    owned = []
    start = time.perf_counter()
    try:
        for scenario in ('empty', 'legacy', 'partial_chunk', 'partial_delete', 'lost_commit_ack', 'partial_batch', 'reset'):
            name = f'cartcare_kbprep_{uuid.uuid4().hex}'
            client.create_collection(name=name, metadata={'dataset_kind':'demo','embedding_version':EMBEDDING_VERSION,'hnsw:space':'cosine'})
            owned.append(name)
            kb = KnowledgeBase(chroma_host='127.0.0.1',chroma_port=8001,collection_name=name,seed_defaults=False,min_score=0.35)
            result = {'scenario':scenario,'collection':name}
            evidence['scenarios'].append(result)
            if scenario != 'empty':
                legacy = json.loads(LEGACY.read_text(encoding='utf-8'))
                kb._collection.upsert(ids=list(legacy), documents=[r[0] for r in legacy.values()],
                    metadatas=[r[1] for r in legacy.values()],
                    embeddings=[embed_document(r[1]['title'],r[0]) for r in legacy.values()])
                try:
                    kb.search('仅用于旧格式克隆的升级前可用性检查', 5)
                    raise AssertionError('legacy search should fail closed')
                except RuntimeError as exc:
                    assert 'legacy knowledge' in str(exc)
                    result['before_upgrade'] = str(exc)
            backup = OUT / f'{scenario}-{name}-backup.json'
            result['backup_sha256'] = write_backup(kb, backup)
            before = encoded(snapshot(kb))
            real = kb._collection
            if scenario.startswith('partial') or scenario == 'lost_commit_ack':
                op, nth, after = {'partial_chunk':('upsert',2,False),
                    'partial_delete':('delete',1,True), 'lost_commit_ack':('upsert',3,True),
                    'partial_batch':('upsert',5,False)}[scenario]
                kb._collection = Fault(real,op,nth,after)
                try:
                    publish_approved(kb, backup)
                    raise AssertionError('failure was not injected')
                except RuntimeError as exc:
                    assert 'injected' in str(exc)
                    result['injected_failure'] = str(exc)
                finally:
                    kb._collection = real
                state = kb._snapshot()
                eligible = kb._eligible(state,datetime.now(timezone.utc))
                result['partial_eligible_chunks'] = sum(len(v) for v in eligible.values())
                if scenario not in {'lost_commit_ack', 'partial_batch'}:
                    assert not eligible  # First publication was disabled before mutation.
                else:
                    assert sum(len(v) for v in eligible.values()) == 1
                retry_backup = OUT / f'{scenario}-{name}-retry-backup.json'
                result['retry_backup_sha256'] = write_backup(kb,retry_backup)
                assert publish_approved(kb,retry_backup) == 6
            elif scenario == 'reset':
                # Exercise the SAME reset path only on a subclass whose default is owned.
                class OwnedReset(KnowledgeBase):
                    COLLECTION_NAME = name
                kb.__class__ = OwnedReset
                assert kb.rebuild_demo_collection() == 6
            else:
                assert publish_approved(kb,backup) == 6
            verify(kb,docs,result)
            ready_backup = OUT / f'{scenario}-{name}-ready-backup.json'
            write_backup(kb,ready_backup)
            stable = encoded(snapshot(kb))
            assert publish_approved(kb,ready_backup) == 6
            assert stable == encoded(snapshot(kb))
            result['repeat_publication_stable'] = True
            assert restore_backup(kb,backup) in (0,6)
            assert before == encoded(snapshot(kb))
            result['full_restore_byte_equivalent_json'] = True
            if scenario != 'empty':
                try:
                    kb.search('旧数据恢复后的降级检查',5)
                    raise AssertionError('restored legacy must still fail closed')
                except RuntimeError as exc:
                    assert 'legacy knowledge' in str(exc)
            assert publish_approved(kb,backup) == 6
            result['recovery_after_restore'] = True
            result['passed'] = True
        evidence['passed'] = True
    except Exception as exc:
        evidence['passed'] = False
        evidence['error'] = {'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        for name in owned:
            try:
                client.delete_collection(name)
                try:
                    client.get_collection(name)
                except Exception as exc:
                    if not isinstance(exc, chromadb.errors.InvalidCollectionException):
                        raise
                else:
                    raise AssertionError('owned test collection still exists')
                evidence['cleanup'].append({'collection':name,'deleted_and_absent':True})
            except Exception as exc:
                evidence['cleanup'].append({'collection':name,'deleted_and_absent':False,'error':str(exc)})
                evidence['passed'] = False
        evidence['elapsed_seconds'] = time.perf_counter()-start
        (OUT/'http_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':evidence['passed'],'scenarios':len(evidence['scenarios']),'cleanup':evidence['cleanup']},ensure_ascii=False))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
