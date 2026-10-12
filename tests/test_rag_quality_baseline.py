"""A05-P1 label and metric tests; Fake Chroma only for contract tests, not quality."""
import asyncio
from copy import deepcopy
import json

import pytest

from evaluation.rag_quality.run_baseline import (
    HERE, active_identities, aggregate, chunk_catalog, load_frozen,
    digest, make_manager, observe, percentile, retrieve_b0, validate_dataset,
)
from mcp.tool_manager import ToolResult
from tests.test_rag_contract import knowledge_base, POLICY


def test_frozen_structure_ids_labels_and_stratification():
    corpus, dataset, _ = load_frozen()
    chunks = validate_dataset(corpus, dataset)
    assert len(dataset['cases']) == 30
    assert sum(c['answerable'] for c in dataset['cases']) == 21
    assert len(chunks) == 11
    assert len(active_identities(corpus)) == 7
    assert all(c['annotation_reason'] and c['evidence_location'] for c in dataset['cases'])
    assert all(c['source'].startswith('demo:') for c in chunks.values())


@pytest.mark.parametrize('mutation', ['duplicate', 'missing_reason', 'missing_label',
    'missing_gold', 'wrong_version', 'invented_evidence', 'inactive_gold',
    'negative_gold', 'wrong_bool', 'excluded_active', 'wrong_counts'])
def test_invalid_labels_fail_closed(mutation):
    corpus, dataset, _ = load_frozen()
    case = dataset['cases'][0]
    if mutation == 'duplicate':
        dataset['cases'][1]['case_id'] = case['case_id']
    elif mutation == 'missing_reason':
        case['annotation_reason'] = ''
    elif mutation == 'missing_label':
        del case['gold_chunk_id']
    elif mutation == 'missing_gold':
        case['gold_chunk_id'] = 'invented'
    elif mutation == 'wrong_version':
        case['policy_version'] = 'future'
    elif mutation == 'invented_evidence':
        case['gold_evidence'] = 'This does not exist in corpus'
    elif mutation == 'inactive_gold':
        chunk = chunk_catalog(corpus)[6]
        case.update(gold_document_id=chunk['document_id'], gold_chunk_id=chunk['chunk_id'],
                    policy_version=chunk['policy_version'], gold_evidence=chunk['content'])
    elif mutation == 'negative_gold':
        dataset['cases'][18]['gold_chunk_id'] = case['gold_chunk_id']
    elif mutation == 'wrong_bool':
        case['answerable'] = 1
    elif mutation == 'excluded_active':
        corpus['documents'][8]['effective_at'] = '2026-10-10T00:00:00Z'
    elif mutation == 'wrong_counts':
        dataset['stratification']['paraphrase'] += 1
    with pytest.raises(ValueError):
        validate_dataset(corpus, dataset)


def metric_row(case_id, rank, answerable=True, false_positive=False, citations=0, correct=0):
    return dict(case_id=case_id, answerable=answerable, gold_rank=rank,
                diagnostic_candidate_gold_rank=rank, false_positive=false_positive,
                citation_correct=correct, citation_count=citations,
                retrieval_latency_ms=10., retrieval_calls=1, model_calls=0,
                retrieval_status='usable' if rank else 'no_answer', failure_reason='none')


def test_metric_arithmetic_and_no_answer_denominators():
    rows = [metric_row('a', 1, citations=1, correct=1),
            metric_row('b', 3, citations=3, correct=1), metric_row('c', None),
            metric_row('d', None, False, True, citations=1),
            metric_row('e', None, False)]
    result = aggregate(rows)
    assert result['Recall@1'] == {'value': .3333, 'numerator': 1, 'denominator': 3}
    assert result['Recall@3']['numerator'] == result['Recall@5']['numerator'] == 2
    assert result['MRR']['numerator'] == pytest.approx(1 + 1/3)
    assert result['MRR']['value'] == .4444
    assert result['no_answer_false_positive_rate'] == {'value': .5, 'numerator': 1, 'denominator': 2}
    assert result['citation_evidence_precision'] == {'value': .4, 'numerator': 2, 'denominator': 5}
    assert aggregate([metric_row('neg', None, False)])['MRR']['value'] is None
    assert aggregate([])['citation_evidence_precision']['value'] is None
    with pytest.raises(ValueError, match='one repeat'):
        aggregate(rows + rows)


def test_percentiles_have_explicit_interpolation():
    assert percentile([], .5) is None
    assert percentile([7], .95) == 7
    assert percentile([10, 20, 30, 40], .5) == 25
    assert percentile([10, 20, 30, 40], .95) == pytest.approx(38.5)


def test_n07_empty_and_low_confidence_are_success_without_evidence():
    kb = knowledge_base()
    manager = make_manager(kb)
    raw, final = asyncio.run(retrieve_b0(manager, 'policy'))
    assert final.success and final.retrieval_status == 'no_answer'
    assert final.data == final.citations == []
    kb.add_documents([POLICY])
    kb.min_score = .99  # Fake distance=.1; only exercises score/status contract.
    raw, final = asyncio.run(retrieve_b0(manager, 'policy'))
    assert raw.success and raw.data
    assert final.success and final.retrieval_status == 'low_confidence'
    assert final.data == final.citations == []
    assert not final.reranked and manager._client.calls == 0


def test_b0_uses_final_n06_validation_without_model_or_rewrite():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    manager = make_manager(kb)
    async def retired_during_await(hits):
        return []
    kb.validate_hits_async = retired_during_await
    raw, final = asyncio.run(retrieve_b0(manager, 'policy'))
    assert raw.data[0]['retrieval_status'] == 'usable'
    assert final.success and final.retrieval_status == 'no_answer'
    assert final.data == final.citations == []
    assert manager._client.calls == 0


def test_b0_validation_dependency_failure_is_degraded():
    kb = knowledge_base()
    kb.add_documents([POLICY])
    async def unavailable(hits):
        raise ConnectionError('isolated test')
    kb.validate_hits_async = unavailable
    _, final = asyncio.run(retrieve_b0(make_manager(kb), 'policy'))
    assert not final.success and final.retrieval_status == 'degraded'
    assert not final.citations


def test_corpus_republication_same_ids_no_duplicate_chunks_and_n06_filter():
    from datetime import datetime
    corpus, _, _ = load_frozen()
    kb = knowledge_base()
    kb.add_documents(corpus['documents'])
    first = deepcopy(kb._snapshot())
    kb.add_documents(corpus['documents'])
    assert kb._snapshot() == first
    expected = chunk_catalog(corpus)
    assert {c['chunk_id'] for c in expected} == {
        i for i, (_, m) in first.items() if m.get('record_type') == 'chunk'}
    now = datetime.fromisoformat(corpus['as_of'].replace('Z', '+00:00'))
    eligible = set().union(*kb._eligible(first, now).values())
    assert eligible == {c['chunk_id'] for c in expected
                        if (c['document_id'], c['policy_version']) in active_identities(corpus)}
    # A legacy chunk with seemingly plausible text must not enter eligible evidence.
    kb._collection.upsert(ids=['legacy'], documents=['退款政策：7天'],
                          metadatas=[{'title': '退款政策'}], embeddings=[[0.] * 1024])
    assert 'legacy' not in set().union(*kb._eligible(kb._snapshot(), now).values())


def test_observation_does_not_count_low_score_candidate_as_recall():
    corpus, dataset, _ = load_frozen()
    case = dataset['cases'][0]
    chunks = validate_dataset(corpus, dataset)
    c = chunks[case['gold_chunk_id']]
    hit = {k: c[k] for k in ('document_id', 'policy_version', 'source', 'chunk_index', 'content', 'content_hash')}
    raw = ToolResult(True, [hit], 'knowledge_search', attempts=1)
    final = ToolResult(True, [], 'knowledge_search', retrieval_status='low_confidence')
    row = observe(case, raw, final, chunks, 10, 1, 1)
    assert row['gold_rank'] is None and row['diagnostic_candidate_gold_rank'] == 1
    assert row['failure_reason'] == 'gold_below_threshold'
    assert aggregate([row])['Recall@5']['numerator'] == 0


def test_committed_reports_include_raw_failures_metrics_and_cleanup():
    # Optional before first baseline exists; once evidence exists validate all runs.
    reports = HERE.parents[0] / 'reports/rag_quality'
    for manifest_path in reports.glob('*/manifest.json'):
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['outcome'] == 'blocked':
            continue
        rows = json.loads(manifest_path.with_name('observations.json').read_text(encoding='utf-8'))
        summaries = json.loads(manifest_path.with_name('summary.json').read_text(encoding='utf-8'))
        assert len(rows) == 30 * manifest['repeats']
        assert manifest['collection_deleted'] and manifest['repeat_publication_identical']
        assert manifest['repeat_retrieval_identical']
        for name, expected in manifest['freeze']['files'].items():
            assert digest(manifest_path.with_name(name)) == expected
        eligible = set(manifest['eligible_chunk_ids'])
        assert all(h['frozen_chunk_id'] in eligible for r in rows for h in r['candidates'])
        assert all(r['model_calls'] == 0 and r['vector_queries'] == 1 for r in rows)
        assert all(r['citations'] == [h['citation'] for h in r['hits']] for r in rows)
        assert all(r['retrieval_status'] == 'usable' if r['hits'] else
                   r['retrieval_status'] in {'no_answer', 'low_confidence', 'degraded'} for r in rows)
        assert all('failure_reason' in r and 'candidates' in r and 'citations' in r for r in rows)
        for repeat, summary in summaries.items():
            assert summary == aggregate([r for r in rows if r['repeat'] == int(repeat)])
