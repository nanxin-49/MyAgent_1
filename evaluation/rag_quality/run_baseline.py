"""Frozen B0 evaluation through real Chroma HTTP; no LLM or production writes.

Run from repository root: uv run python -m evaluation.rag_quality.run_baseline
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time
from unittest.mock import patch
import uuid

import chromadb
from evaluation.system_eval import rate
from mcp.knowledge_base import KnowledgeBase
from mcp.knowledge_embeddings import EMBEDDING_VERSION, DIMENSIONS
from mcp.rag_contract import KnowledgeDocument, RetrievalHit
from mcp.tool_manager import MCPToolManager, RerankResult, Tool, ToolResult

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chunk_catalog(corpus):
    """Derive frozen IDs using the existing N06 publisher identity rules."""
    kb = KnowledgeBase.__new__(KnowledgeBase)
    chunks = []
    for item in corpus['documents']:
        doc = KnowledgeDocument.model_validate(item)
        key = kb._key(doc)
        revision = hashlib.sha256(doc.model_dump_json().encode()).hexdigest()
        for i, text in enumerate(kb._chunk_text(doc.content, chunk_size=500)):
            chunks.append(dict(
                chunk_id=hashlib.sha256(f'{key}\0{revision}\0{i}'.encode()).hexdigest(),
                document_id=doc.document_id, policy_version=doc.policy_version,
                source=doc.source, chunk_index=i, content=text,
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
            ))
    return chunks


def active_identities(corpus):
    """Corpus-first label audit, independent of retrieval ranking."""
    now = datetime.fromisoformat(corpus['as_of'].replace('Z', '+00:00'))
    docs = [KnowledgeDocument.model_validate(d) for d in corpus['documents']]
    retired = {(d.document_id, v) for d in docs if d.effective_at and d.effective_at <= now
               for v in d.supersedes}
    return {(d.document_id, d.policy_version) for d in docs
            if d.publication_status == 'active'
            and (d.effective_at is None or d.effective_at <= now)
            and (d.expires_at is None or now < d.expires_at)
            and (d.document_id, d.policy_version) not in retired}


def validate_dataset(corpus, dataset):
    if dataset['corpus_version'] != corpus['version']:
        raise ValueError('corpus version mismatch')
    cases = dataset['cases']
    if len(cases) < 30:
        raise ValueError('at least 30 cases required')
    ids = [c['case_id'] for c in cases]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('case IDs must be nonblank and unique')
    docs = [KnowledgeDocument.model_validate(d) for d in corpus['documents']]
    if len({(d.document_id, d.policy_version) for d in docs}) != len(docs):
        raise ValueError('duplicate document/version')
    chunks = {c['chunk_id']: c for c in chunk_catalog(corpus)}
    active = active_identities(corpus)
    for case in cases:
        for field in ('query', 'category', 'annotation_reason', 'evidence_location'):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f'missing {field}')
        if type(case.get('answerable')) is not bool:
            raise ValueError('answerable must be boolean')
        for field in ('gold_document_id', 'gold_chunk_id', 'gold_evidence', 'policy_version', 'gold_chunk_index'):
            if field not in case:
                raise ValueError(f'missing label field {field}')
        if case['answerable']:
            gold = chunks.get(case['gold_chunk_id'])
            if not gold or not isinstance(case['gold_evidence'], str) or not case['gold_evidence'].strip():
                raise ValueError('missing gold evidence')
            if (gold['document_id'] != case['gold_document_id']
                    or gold['policy_version'] != case['policy_version']
                    or gold['chunk_index'] != case['gold_chunk_index']
                    or case['gold_evidence'] not in gold['content']
                    or (gold['document_id'], gold['policy_version']) not in active):
                raise ValueError('gold evidence not in eligible frozen chunk')
        elif any(case[field] is not None for field in
                 ('gold_document_id', 'gold_chunk_id', 'gold_evidence', 'policy_version', 'gold_chunk_index')):
            raise ValueError('no-answer cases must not carry positive gold')
        excluded = case.get('excluded_evidence')
        if excluded:
            matching = [d for d in docs if d.document_id == excluded['document_id']
                        and d.policy_version == excluded['policy_version']]
            if (len(matching) != 1 or matching[0].content != excluded['content']
                    or (excluded['document_id'], excluded['policy_version']) in active):
                raise ValueError('invalid excluded evidence')
    if dict(Counter(c['category'] for c in cases)) != dataset['stratification']:
        raise ValueError('category counts mismatch')
    return chunks


def load_frozen():
    lock = json.loads((HERE / 'freeze_v1.json').read_text(encoding='utf-8'))
    for name, expected in lock['files'].items():
        if digest(HERE / name) != expected:
            raise ValueError('frozen file hash mismatch: ' + name)
    corpus = json.loads((HERE / 'corpus_v1.json').read_text(encoding='utf-8'))
    dataset = json.loads((HERE / 'dataset_v1.json').read_text(encoding='utf-8'))
    validate_dataset(corpus, dataset)
    return corpus, dataset, lock


class NoModel:
    """Fail closed if this B0 runner accidentally takes any model call path."""
    def __init__(self):
        self.calls = 0
        self.messages = self

    async def create(self, **kwargs):
        self.calls += 1
        raise AssertionError('B0 forbids model calls')


class CountingCollection:
    """Count actual vector query invocations, including retries."""
    def __init__(self, collection):
        self.collection = collection
        self.queries = 0

    def __getattr__(self, name):
        return getattr(self.collection, name)

    def query(self, **kwargs):
        self.queries += 1
        return self.collection.query(**kwargs)


def make_manager(kb):
    # Use the real tool executor, with no SDK client / API credentials at all.
    manager = MCPToolManager.__new__(MCPToolManager)
    manager._client, manager._model = NoModel(), 'none-B0'
    manager._tools, manager._cache = {}, {}
    manager.register(Tool(
        name='knowledge_search', description='B0 isolated HTTP knowledge retrieval',
        handler=kb.search_handler, supports_rerank=False,
        schema={'type': 'object', 'properties': {
            'query': {'type': 'string', 'minLength': 1},
            'top_k': {'type': 'integer', 'minimum': 1}},
            'required': ['query', 'top_k'], 'additionalProperties': False},
    ))
    return manager


async def retrieve_b0(manager, query, top_k=5):
    raw = await manager.call('knowledge_search', {'query': query, 'top_k': top_k},
                             use_cache=False, rerank_top_k=0)
    if not raw.success or raw.error_code or not isinstance(raw.data, list):
        return raw, ToolResult(False, [], 'knowledge_search', error_code='degraded',
                               retrieval_status='degraded')
    try:
        hits = [RetrievalHit.model_validate(h).model_dump(mode='json') for h in raw.data]
    except ValueError:
        return raw, ToolResult(False, [], 'knowledge_search', error_code='degraded',
                               retrieval_status='degraded')
    usable = [h for h in hits if h['retrieval_status'] == 'usable' and h['citation']]
    if not usable:
        return raw, ToolResult(True, [], 'knowledge_search',
                               retrieval_status='low_confidence' if hits else 'no_answer')
    # Reuse N07 final evidence validation, without invoking its sorter or rewrite.
    final = await manager._finalize_rag('knowledge_search', usable,
                                       RerankResult(usable, False, 'not_requested'), top_k)
    return raw, final


def identify_hit(hit, chunks):
    matching = [c['chunk_id'] for c in chunks.values() if all(
        c[k] == hit.get(k) for k in
        ('document_id', 'policy_version', 'source', 'chunk_index', 'content', 'content_hash'))]
    return matching[0] if len(matching) == 1 else None


def observe(case, raw, final, chunks, elapsed_ms, repeat, vector_queries):
    candidates = [{**h, 'frozen_chunk_id': identify_hit(h, chunks)} for h in (raw.data or [])]
    hits = [{**h, 'frozen_chunk_id': identify_hit(h, chunks)} for h in (final.data or [])]
    def rank(items):
        return next((i for i, h in enumerate(items, 1)
                     if case['answerable'] and h['frozen_chunk_id'] == case['gold_chunk_id']), None)
    gold_rank, candidate_rank = rank(hits), rank(candidates)
    usable = final.success and final.retrieval_status == 'usable' and bool(hits) and bool(final.citations)
    citation_correct = sum(case['answerable'] and h['frozen_chunk_id'] == case['gold_chunk_id']
                           and case['gold_evidence'] in h['content'] for h in hits)
    reason = ('retrieval_degraded' if not final.success else
              'false_positive_no_answer' if not case['answerable'] and usable else
              'gold_below_threshold' if case['answerable'] and not gold_rank and candidate_rank else
              'gold_not_in_top5_candidates' if case['answerable'] and not gold_rank else
              'gold_not_rank1' if gold_rank and gold_rank > 1 else 'none')
    return dict(case_id=case['case_id'], query=case['query'], category=case['category'],
                answerable=case['answerable'], repeat=repeat,
                gold_chunk_id=case['gold_chunk_id'], gold_rank=gold_rank,
                diagnostic_candidate_gold_rank=candidate_rank,
                success=final.success, retrieval_status=final.retrieval_status,
                candidates=candidates, hits=hits, citations=final.citations,
                citation_correct=citation_correct, citation_count=len(final.citations),
                false_positive=bool(not case['answerable'] and usable),
                failure_reason=reason, error_code=final.error_code,
                retrieval_latency_ms=elapsed_ms, tool_attempts=raw.attempts,
                retrieval_calls=raw.attempts, vector_queries=vector_queries,
                reranked=final.reranked, rerank_status=final.rerank_status,
                model_calls=0, model_tokens=0, model_cost_usd=0)


def percentile(values, q):
    """Linear interpolation at (n-1)*q; empty sample is unmeasured."""
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def aggregate(rows):
    ids = [r['case_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('aggregate one repeat at a time, never pool repeated questions')
    positive = [r for r in rows if r['answerable']]
    negative = [r for r in rows if not r['answerable']]
    def fraction(n, d):
        return dict(value=rate(n, d), numerator=n, denominator=d)
    metrics = {f'Recall@{k}': fraction(sum(r['gold_rank'] is not None and r['gold_rank'] <= k
                                          for r in positive), len(positive)) for k in (1, 3, 5)}
    reciprocal_sum = sum(1 / r['gold_rank'] for r in positive if r['gold_rank'])
    metrics['MRR'] = fraction(reciprocal_sum, len(positive))
    metrics['no_answer_false_positive_rate'] = fraction(sum(r['false_positive'] for r in negative), len(negative))
    metrics['citation_evidence_precision'] = fraction(sum(r['citation_correct'] for r in rows),
                                                       sum(r['citation_count'] for r in rows))
    metrics['diagnostic_candidate_Recall@5'] = fraction(sum(r['diagnostic_candidate_gold_rank'] is not None
                                                          for r in positive), len(positive))
    metrics.update(latency_ms={'p50': percentile([r['retrieval_latency_ms'] for r in rows], .5),
                               'p95': percentile([r['retrieval_latency_ms'] for r in rows], .95),
                               'count': len(rows), 'includes_failed_requests': True},
                   status_counts=dict(Counter(r['retrieval_status'] for r in rows)),
                   failure_counts=dict(Counter(r['failure_reason'] for r in rows)),
                   retrieval_calls=sum(r['retrieval_calls'] for r in rows),
                   model_calls=sum(r['model_calls'] for r in rows),
                   model_tokens=0, model_cost_usd=0)
    return metrics


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def run(args):
    corpus, dataset, lock = load_frozen()
    chunks = validate_dataset(corpus, dataset)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    output = ROOT / 'evaluation/reports/rag_quality' / run_id
    output.mkdir(parents=True, exist_ok=False)
    for name in lock['files']:
        (output / name).write_bytes((HERE / name).read_bytes())
    write_json(output / 'freeze_v1.json', lock)
    write_json(output / 'chunks.json', list(chunks.values()))
    collection = 'cartcare_a05_p1_' + uuid.uuid4().hex
    manifest = dict(run_id=run_id, group='B0', started_at_utc=datetime.now(timezone.utc).isoformat(),
                    head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    dirty_worktree=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
                    python=platform.python_version(), platform=platform.platform(),
                    packages={p: version(p) for p in ('chromadb-client', 'pydantic', 'anthropic', 'httpx', 'pytest')},
                    implementation_sha256={p: digest(ROOT / p) for p in
                        ('mcp/knowledge_embeddings.py', 'mcp/knowledge_base.py', 'mcp/rag_contract.py',
                         'mcp/tool_manager.py', 'evaluation/rag_quality/run_baseline.py', 'uv.lock')},
                    freeze=lock, corpus_version=corpus['version'], dataset_version=dataset['version'],
                    collection=collection, endpoint=f'{args.host}:{args.port}', backend='real Chroma HTTP',
                    embedding_version=EMBEDDING_VERSION, dimensions=DIMENSIONS, title_feature_boost=6,
                    top_k=5, min_score=.35, distance='cosine; score=1-distance (not probability)',
                    as_of=corpus['as_of'], clock='evaluation-process-only KnowledgeBase datetime patch',
                    rewrite=False, rerank=False, cache=False, model='none; fail-closed NoModel sentinel',
                    repeats=args.repeats, B_prod={'status': 'not_executed', 'reason': 'No paid model authorization'},
                    collection_deleted=False, outcome='running')
    write_json(output / 'manifest.json', manifest)
    client, owned = None, False
    observations = []
    try:
        client = chromadb.HttpClient(host=args.host, port=args.port,
                                    settings=chromadb.Settings(anonymized_telemetry=False))
        manifest['chroma_server_version'] = client.get_version()
        # create, rather than get-or-create: an existing collection is never adopted.
        client.create_collection(collection, metadata={
            'dataset_kind': 'demo', 'embedding_version': EMBEDDING_VERSION, 'hnsw:space': 'cosine',
            'evaluation_owner': run_id})
        owned = True
        kb = KnowledgeBase(chroma_host=args.host, chroma_port=args.port,
                           collection_name=collection, seed_defaults=False, min_score=.35)
        kb.add_documents(corpus['documents'])
        first = kb._snapshot()
        kb.add_documents(corpus['documents'])
        if kb._snapshot() != first:
            raise RuntimeError('identical republication changed corpus / chunk IDs')
        manifest['repeat_publication_identical'] = True
        manifest['physical_chunks'] = kb.doc_count
        fixed_time = datetime.fromisoformat(corpus['as_of'].replace('Z', '+00:00'))
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_time.astimezone(tz) if tz else fixed_time.replace(tzinfo=None)
        manager = make_manager(kb)
        kb._collection = CountingCollection(kb._collection)
        with patch('mcp.knowledge_base.datetime', FrozenDatetime):
            eligible_ids = set().union(*kb._eligible(first, fixed_time).values())
            expected_ids = {i for i, c in chunks.items()
                            if (c['document_id'], c['policy_version']) in active_identities(corpus)}
            if eligible_ids != expected_ids:
                raise RuntimeError('N06 eligible snapshot differs from corpus labels')
            manifest['eligible_chunk_ids'] = sorted(eligible_ids)
            for repeat in range(1, args.repeats + 1):
                for case in dataset['cases']:
                    previous_queries = kb._collection.queries
                    start = time.perf_counter()
                    raw, final = await retrieve_b0(manager, case['query'])
                    elapsed = (time.perf_counter() - start) * 1000
                    observations.append(observe(case, raw, final, chunks, elapsed, repeat,
                                                kb._collection.queries - previous_queries))
        if manager._client.calls:
            raise RuntimeError('unexpected model invocation')
        if kb._snapshot() != first:
            raise RuntimeError('retrieval changed frozen corpus')
        summaries = {str(i): aggregate([r for r in observations if r['repeat'] == i])
                     for i in range(1, args.repeats + 1)}
        signatures = [[(r['case_id'], r['gold_rank'], r['retrieval_status'], r['citations'],
                        [(h['frozen_chunk_id'], h['score']) for h in r['candidates']])
                       for r in observations if r['repeat'] == i] for i in range(1, args.repeats + 1)]
        manifest['repeat_retrieval_identical'] = all(s == signatures[0] for s in signatures)
        manifest['outcome'] = 'measured' if all(r['success'] for r in observations) else 'partial_dependency_failure'
        write_json(output / 'summary.json', summaries)
        primary = observations[:len(dataset['cases'])]
        report = ['# A05-P1 B0 lexical retrieval baseline', '',
                  'Real Chroma HTTP; no model calls. Labels frozen before retrieval; human acceptance pending.',
                  'Production call paths/configuration unchanged. B-prod not executed (no paid-model authorization).',
                  '21 answerable / 9 no-answer. One gold chunk per answerable query. Final usable hits determine metrics.', '',
                  '```json', json.dumps(summaries, ensure_ascii=False, indent=2), '```', '',
                  '| Case | Query | Gold rank | Candidate rank (diagnostic) | Status | Failure reason |',
                  '| --- | --- | --- | --- | --- | --- |']
        report.extend(f"| {r['case_id']} | {r['query']} | {r['gold_rank']} | {r['diagnostic_candidate_gold_rank']} | {r['retrieval_status']} | {r['failure_reason']} |"
                      for r in primary)
        report += ['', 'Recall@K: correct frozen gold chunk in final top K / all answerable cases (including failures).',
                   'MRR: sum of 1/final gold rank, missing=0, / all answerable cases; ranks truncated at 5.',
                   'No-answer FPR: usable with nonempty hits/citations on no-answer cases / all no-answer cases.',
                   'Citation precision: emitted citations whose chunk contains the labelled evidence / all emitted citations, including no-answer cases.',
                   'Latency: wall time for tool execution plus final N06/N07 validation, excludes ingest/startup; first repeat includes cold reads; linear interpolated percentiles.',
                   'Repeat groups are scored separately; repeats are not independent questions or populations.',
                   'Candidate Recall is diagnostic, may include low-score chunks, and is never usable-evidence Recall.',
                   'No Agent answers generated; Task Success and answer factual accuracy remain unmeasured.']
        (output / 'report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    except Exception as exc:
        manifest['outcome'] = 'blocked'
        manifest['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        write_json(output / 'observations.json', observations)
        try:
            if owned:
                client.delete_collection(collection)
                manifest['collection_deleted'] = True
        finally:
            manifest['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
            write_json(output / 'manifest.json', manifest)
            print('Report:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be >=1')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
