"""Independent A05 evidence runner: preflight by default; --formal runs ONE test pass.
Run from repository root with python -m; no production source/config edits.
An existing observations.json blocks another formal attempt, including after failure.
"""
import argparse
import ast
import asyncio
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time
from unittest.mock import patch
import uuid

import chromadb
import numpy as np
from evaluation.rag_quality import run_baseline as b
from mcp.knowledge_embeddings import embed_document

OUT = Path(__file__).resolve().parent
CAL = b.HERE / 'calibration/20261013T025559Z-ed4a1cb4'
OLD = b.ROOT / 'evaluation/reports/rag_quality/v2/20261012T165114Z-945bd721'
LOCK_SHA = 'c65630d00d33e51d345b2fb94982b24331e7385d05195ec2c34eaf213fc84ad2'
FREEZE_SHA = '7ea0b1c40d430de13fead53ed1f21af082410efc7c0cdf6bb967c22030524f79'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def snap_json(s):
    return {k: list(v) for k, v in s.items()}


def snapshot_info(kb, snapshot, now):
    eligible = set().union(*kb._eligible(snapshot, now).values())
    pubs = kb._publications(snapshot)
    return dict(rows=len(snapshot), publications=[dict(id=k, state=p['state'],
        document_id=d.document_id, policy_version=d.policy_version,
        publication_status=d.publication_status, chunk_ids=p['chunk_ids'],
        eligible_chunk_ids=sorted(eligible.intersection(p['chunk_ids']))) for k, (d, p) in pubs.items()],
        physical_chunks=sum(m.get('record_type') != 'publication' for _, m in snapshot.values()),
        eligible_chunk_ids=sorted(eligible), chunks=[dict(id=k, stored_hash=m.get('content_hash'),
        actual_hash=b.hashlib.sha256(t.encode()).hexdigest(),
        hash_matches=m.get('content_hash') == b.hashlib.sha256(t.encode()).hexdigest(),
        record_type=m.get('record_type')) for k, (t, m) in snapshot.items()
        if m.get('record_type') != 'publication'])


async def run(formal):
    phase = 'formal' if formal else 'preflight'
    require(not (OUT / 'observations.json').exists(), 'one-shot test already attempted; do not rerun')
    record = dict(phase=phase, started_at_utc=datetime.now(timezone.utc).isoformat(),
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=b.ROOT, text=True).strip(),
        dirty_worktree=subprocess.check_output(['git', 'status', '--short'], cwd=b.ROOT, text=True),
        script_sha256=b.digest(Path(__file__)), python=platform.python_version(),
        outcome='blocked', formal_test_started=False, collection_deleted=False,
        default_collection=b.KnowledgeBase.COLLECTION_NAME, endpoint='127.0.0.1:8001')
    client, collection, owned = None, None, False
    rows = []
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=b.ROOT, text=True).splitlines()
    protected = {p: b.digest(b.ROOT / p) for p in tracked if (b.ROOT / p).is_file()}
    b.write_json(OUT / 'protected_inputs.json', protected)
    try:
        corpus, dataset, freeze = b.load_frozen('v2')
        require(b.digest(b.HERE / 'freeze_v2.json') == FREEZE_SHA, 'freeze changed since B0-v2')
        require(read(OLD / 'freeze_v2.json') == freeze, 'original B0 freeze differs')
        for name, sha in freeze['files'].items():
            require(b.digest(b.HERE / name) == b.digest(OLD / name) == sha, 'B0 input mismatch: ' + name)
            (OUT / name).write_bytes((b.HERE / name).read_bytes())
        require(dataset['cases'] == read(b.HERE / 'dataset_v2.candidate.json')['cases'], 'approved cases differ')
        for name, sha in freeze['review']['approved_candidate_sha256'].items():
            require(b.digest(b.HERE / name) == sha, 'approved candidate hash changed')
        (OUT / 'freeze_v2.json').write_bytes((b.HERE / 'freeze_v2.json').read_bytes())
        require(freeze['test_counts']['total'] == 30 and freeze['test_counts']['answerable'] == 21
                and freeze['test_counts']['no_answer'] == 9, '30/21/9 denominator mismatch')
        require(freeze['review']['status'] == 'user_approved_v2', 'human review pending')
        record.update(review=freeze['review'], input_sha256={**freeze['files'], 'freeze_v2.json': FREEZE_SHA})
        config_path = CAL / 'b0_lexical_calibration_v2.json'
        require(b.digest(config_path) == LOCK_SHA, 'development lock changed')
        config = read(config_path)
        require(config['status'] == 'locked' and config['split'] == 'dev'
                and config['selected_threshold'] == .20 and config['selected_threshold_hex'] == (.20).hex()
                and config['top_k'] == 5 and config['embedding_version'] == b.EMBEDDING_VERSION
                and config['dimensions'] == b.DIMENSIONS and config['as_of'] == corpus['as_of']
                and config['score_kind'] == 'one_minus_chroma_distance'
                and not config['test_scores_consumed'], 'calibration contract mismatch')
        for name, sha in config['data_binding_sha256'].items():
            require(b.digest(b.HERE / name) == sha, 'calibration data changed')
        for name, key in [('b0_lexical_dev_v2_observations.json', 'raw_observations_sha256'),
                          ('b0_lexical_threshold_sweep_v2.csv', 'curve_csv_sha256'),
                          ('n06_snapshot.json', 'snapshot_sha256')]:
            require(b.digest(CAL / name) == config[key], 'calibration evidence changed: ' + name)
        for name, sha in config['code_sha256'].items():
            require(b.digest(b.ROOT / name) == sha, 'locked code/dependency changed: ' + name)
        require(b.digest(b.HERE / 'p2_experiment_protocol.md') == config['protocol_sha256'], 'protocol changed')
        require(platform.python_version() == config['python'], 'Python changed')
        record['packages'] = {p: version(p) for p in config['packages']}
        require(record['packages'] == config['packages'], 'package versions changed')
        record['code_sha256'] = config['code_sha256']
        (OUT / config_path.name).write_bytes(config_path.read_bytes())
        record['calibration_sha256'] = LOCK_SHA
        original = read(OLD / 'manifest.json')
        for name, sha in original['implementation_sha256'].items():
            actual = (b.HERE / 'history/run_baseline_before_dev_cal.py.txt'
                      if name == 'evaluation/rag_quality/run_baseline.py' else b.ROOT / name)
            require(b.digest(actual) == sha, 'original B0 implementation changed: ' + name)
        def functions(path):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(
                path.read_text(encoding='utf-8')).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        old_funcs = functions(b.HERE / 'history/run_baseline_before_dev_cal.py.txt')
        new_funcs = functions(b.HERE / 'run_baseline.py')
        unchanged = ('chunk_catalog', 'active_identities', 'validate_dataset', 'load_frozen',
                     'make_manager', 'retrieve_b0', 'identify_hit', 'observe', 'percentile', 'aggregate')
        require(all(old_funcs[n] == new_funcs[n] for n in unchanged), 'retrieval/metric semantics changed')
        record['baseline_comparability'] = dict(shared_production_sources_identical=True,
            original_runner_archive_verified=True, identical_function_AST=list(unchanged))
        chunks = b.validate_dataset(corpus, dataset)
        require(list(chunks.values()) == read(OLD / 'chunks.json'), 'original knowledge chunks differ')
        b.write_json(OUT / 'chunks.json', list(chunks.values()))
        now = datetime.fromisoformat(corpus['as_of'].replace('Z', '+00:00'))
        client = chromadb.HttpClient(host='127.0.0.1', port=8001,
                    settings=chromadb.Settings(anonymized_telemetry=False))
        record['chroma_server_version'] = client.get_version()
        require(record['chroma_server_version'] == original['chroma_server_version'], 'server version changed')
        record['existing_collections'] = [c.name for c in client.list_collections()]
        default_kb = b.KnowledgeBase.__new__(b.KnowledgeBase)
        default_kb._collection = client.get_collection(b.KnowledgeBase.COLLECTION_NAME)
        default_kb.min_score = .35
        default_snapshot = default_kb._snapshot()
        b.write_json(OUT / ('default_snapshot_' + phase + '.json'), snap_json(default_snapshot))
        record['default_knowledge'] = snapshot_info(default_kb, default_snapshot, datetime.now(timezone.utc))
        try:
            record['default_probe'] = default_kb.search('退货政策', 5)
        except RuntimeError as exc:
            record['default_probe_error'] = str(exc)
        collection = 'cartcare_a05_calibrated_' + uuid.uuid4().hex
        require(collection != b.KnowledgeBase.COLLECTION_NAME and collection not in record['existing_collections'],
                'evaluation collection not isolated')
        record['collection'] = collection
        col = client.create_collection(collection, metadata={'dataset_kind': 'demo',
                    'evaluation_owner': OUT.name, 'embedding_version': b.EMBEDDING_VERSION, 'hnsw:space': 'cosine'})
        owned = True
        # Use create-only collection directly; do not get-or-create the business collection.
        kb = b.KnowledgeBase.__new__(b.KnowledgeBase)
        kb._client, kb._collection, kb._collection_name, kb.min_score = client, col, collection, .20
        kb.add_documents(corpus['documents'])
        snapshot = kb._snapshot()
        require(snap_json(snapshot) == read(CAL / 'n06_snapshot.json'), 'snapshot differs from calibration')
        kb.add_documents(corpus['documents'])
        require(kb._snapshot() == snapshot, 'republication changed snapshot')
        info = snapshot_info(kb, snapshot, now)
        record['evaluation_knowledge'] = info
        require(info['physical_chunks'] == 11 and len(info['eligible_chunk_ids']) == 7
                and len(info['publications']) == 11 and all(p['state'] == 'ready' for p in info['publications'])
                and all(c['hash_matches'] for c in info['chunks']), 'publication/hash/eligible count invalid')
        require(set(info['eligible_chunk_ids']) == set(original['eligible_chunk_ids']), 'B0 eligible IDs differ')
        b.write_json(OUT / 'n06_snapshot.json', snap_json(snapshot))
        # Preflight probes use chunk vectors, NEVER test queries. Verify actual HTTP
        # retrievability and exact stored float32 vectors, not just collection.count().
        vector_rows = col.get(ids=info['eligible_chunk_ids'], include=['embeddings'])
        for i, vector in zip(vector_rows['ids'], vector_rows['embeddings']):
            text, meta = snapshot[i]
            require(np.array_equal(np.asarray(vector, dtype=np.float32),
                np.asarray(embed_document(meta['title'], text), dtype=np.float32)), 'stored embedding differs')
        probes = []
        for i in info['eligible_chunk_ids']:
            text, meta = snapshot[i]
            result = col.query(query_embeddings=[embed_document(meta['title'], text)], n_results=7,
                where={'chunk_id': {'$in': info['eligible_chunk_ids']}}, include=['documents', 'metadatas', 'distances'])
            rank = result['ids'][0].index(i)
            require(result['documents'][0][rank] == text and result['metadatas'][0][rank] == meta,
                    'probe provenance mismatch')
            probes.append(dict(chunk_id=i, rank=rank+1, distance=result['distances'][0][rank]))
        record['retrievability_probes'] = probes
        require(kb._snapshot() == snapshot, 'preflight changed snapshot')
        record.update(outcome='preflight_passed', gates_passed=True, top_k=5, min_score=.20,
            embedding_version=b.EMBEDDING_VERSION, dimensions=b.DIMENSIONS, as_of=corpus['as_of'],
            rewrite=False, rerank=False, cache=False, model_calls=0)
        b.write_json(OUT / ('preflight_' + phase + '.json'), record)
        if formal:
            require(read(OUT / 'preflight_preflight.json')['gates_passed'], 'separate preflight record missing')
            record['formal_test_started'] = True
            b.write_json(OUT / 'observations.json', [])  # Reserve once-only output before any test query.
            manager = b.make_manager(kb)
            kb._collection = b.CountingCollection(kb._collection)
            class FrozenDatetime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return now.astimezone(tz) if tz else now.replace(tzinfo=None)
            with patch('mcp.knowledge_base.datetime', FrozenDatetime):
                for case in dataset['cases']:
                    previous = kb._collection.queries
                    started = time.perf_counter()
                    raw, final = await b.retrieve_b0(manager, case['query'], 5)
                    row = b.observe(case, raw, final, chunks, (time.perf_counter()-started)*1000,
                                    1, kb._collection.queries-previous)
                    result = kb._collection.last_query_result
                    require(row['success'] and row['vector_queries'] == 1 and result, 'test dependency failed')
                    distances = dict(zip(result['ids'][0], result['distances'][0]))
                    for rank, hit in enumerate(row['candidates'], 1):
                        i = hit['frozen_chunk_id']
                        require(i in info['eligible_chunk_ids'] and hit['score'] == 1-distances[i],
                                'test candidate provenance/score invalid')
                        hit.update(rank=rank, raw_distance=distances[i], metadata=snapshot[i][1],
                                   valid_at_as_of=True, score_kind='one_minus_chroma_distance')
                    rows.append(row)
                    b.write_json(OUT / 'observations.json', rows)
            require(manager._client.calls == 0 and kb._collection.queries == 30, 'unexpected model/query calls')
            require(kb._snapshot() == snapshot, 'test changed snapshot')
            b.write_json(OUT / 'summary.json', b.aggregate(rows))
            record.update(outcome='measured', formal_queries=30, repeats=1)
        require(default_kb._snapshot() == default_snapshot, 'default knowledge changed during evaluation')
        record['default_snapshot_unchanged'] = True
        require(all(b.digest(b.ROOT / p) == sha for p, sha in protected.items()), 'protected workspace changed')
        record['all_tracked_files_unchanged'] = True
    except Exception as exc:
        record.update(outcome='blocked', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        if owned:
            client.delete_collection(collection)
            record['collection_deleted'] = collection not in [c.name for c in client.list_collections()]
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        b.write_json(OUT / ('preflight_' + phase + '.json'), record)
        if formal:
            b.write_json(OUT / 'manifest.json', record)
        print(json.dumps({k: record.get(k) for k in ('phase', 'outcome', 'gates_passed',
                    'formal_test_started', 'collection_deleted', 'error')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--formal', action='store_true')
    asyncio.run(run(parser.parse_args().formal))
