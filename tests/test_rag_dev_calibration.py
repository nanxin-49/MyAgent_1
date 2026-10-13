"""Deterministic dev calibration contracts; Toy scores are not quality evidence."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil

import pytest

from evaluation.rag_quality.run_baseline import HERE, chunk_catalog, make_manager
from evaluation.rag_quality.dev_calibration import (
    GRID, curve_point, load_dev_frozen, replay, select_threshold, unique_repeat,
)
from tests.test_rag_contract import knowledge_base, POLICY


def test_dev_loader_never_parses_test_contents_or_test_observations(monkeypatch):
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name != 'dataset_v2.json'
        assert not ('reports' in path.parts and path.name == 'observations.json')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    corpus, dev, _ = load_dev_frozen('v2', HERE)
    assert len(dev['cases']) == 16 and sum(r['answerable'] for r in dev['cases']) == 8
    assert corpus['as_of'] == '2026-10-12T00:00:00Z'


@pytest.mark.parametrize('version', ['v1', 'v3', 'candidate', '../v2'])
def test_wrong_dev_version_fails_closed(version):
    with pytest.raises(ValueError, match='formal v2'):
        load_dev_frozen(version, HERE)


@pytest.mark.parametrize('fault', ['hash', 'missing', 'approval', 'denominator', 'gold'])
def test_dev_freeze_fail_closed(tmp_path, fault):
    for name in ['freeze_v2.json', 'corpus_v1.json', 'dataset_v2.json', 'dev_dataset_v2.json',
                 'gold_review_v2.md', 'gold_v1_to_v2_diff.md']:
        shutil.copyfile(HERE / name, tmp_path / name)
    lock_path = tmp_path / 'freeze_v2.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if fault == 'hash':
        (tmp_path / 'dev_dataset_v2.json').write_text('{}', encoding='utf-8')
    elif fault == 'missing':
        (tmp_path / 'dev_dataset_v2.json').unlink()
    elif fault == 'approval':
        lock['review']['status'] = 'pending'
    elif fault == 'denominator':
        lock['dev_counts']['answerable'] = 9
    elif fault == 'gold':
        lock['dev_gold_labels'][0]['answerable'] = False
    lock_path.write_text(json.dumps(lock), encoding='utf-8')
    with pytest.raises((ValueError, FileNotFoundError)):
        load_dev_frozen('v2', tmp_path)


def replay_fixture(distance=.65, answerable=True):
    # Publication/contract fixture uses Fake only; no ranking test or quality claim.
    kb = knowledge_base()
    kb.add_documents([POLICY])
    doc = next((i, row) for i, row in kb._snapshot().items() if row[1].get('record_type') == 'chunk')
    chunk_id, (content, metadata) = doc
    corpus = {'documents': [POLICY]}
    chunks = {c['chunk_id']: c for c in chunk_catalog(corpus)}
    case = dict(case_id='DEV-toy', query='policy', answerable=answerable,
                gold_chunk_id=chunk_id if answerable else None, gold_evidence=content if answerable else None)
    observation = dict(repeat=1, candidates=[dict(content=content, metadata=metadata,
        raw_distance=distance, score=1-distance, score_kind='one_minus_chroma_distance')])
    return kb, case, observation, chunks


def run_replay(kb, case, obs, chunks, threshold):
    return asyncio.run(replay(case, obs, threshold, make_manager(kb),
                             datetime(2026, 10, 12, tzinfo=timezone.utc), chunks))


def test_exact_threshold_boundary_and_next_float():
    kb, case, obs, chunks = replay_fixture()
    score = obs['candidates'][0]['score']
    assert run_replay(kb, case, obs, chunks, score)['gold_rank'] == 1
    assert run_replay(kb, case, obs, chunks, math.nextafter(score, math.inf))['gold_rank'] is None


def test_negative_and_above_one_scores_not_clipped_or_assumed_probability():
    kb, case, obs, chunks = replay_fixture(1.2)
    row = run_replay(kb, case, obs, chunks, 0)
    assert row['candidates'][0]['score'] < 0 and not row['hits']
    kb, case, obs, chunks = replay_fixture(-.001)
    row = run_replay(kb, case, obs, chunks, 1)
    assert row['candidates'][0]['score'] > 1 and row['gold_rank'] == 1


def test_no_gold_is_false_positive_not_positive_recall():
    kb, case, obs, chunks = replay_fixture(.1, answerable=False)
    row = run_replay(kb, case, obs, chunks, .35)
    assert row['gold_rank'] is None and row['false_positive']
    point = curve_point([row], .35)
    assert point['Recall@5']['denominator'] == 0
    assert point['no_answer_false_positive_rate']['numerator'] == 1


def test_replay_retirement_and_hash_checks_reuse_n06_n07():
    kb, case, obs, chunks = replay_fixture(.1)
    kb.add_documents([{**POLICY, 'publication_status': 'revoked'}])
    row = run_replay(kb, case, obs, chunks, .35)
    assert row['retrieval_status'] == 'no_answer' and row['hits'] == row['citations'] == []
    kb, case, obs, chunks = replay_fixture(.1)
    obs['candidates'][0]['content'] += ' modified'
    row = run_replay(kb, case, obs, chunks, .35)
    assert not row['citations']


def point(threshold, recall=2, fp=1, mrr=2., precision=(2, 3)):
    n, d = precision
    return {'threshold': threshold, 'Recall@5': {'numerator': recall, 'denominator': 8},
            'no_answer_false_positive_rate': {'numerator': fp, 'denominator': 8},
            'MRR': {'numerator': mrr},
            'citation_evidence_precision': {'numerator': n, 'denominator': d, 'value': n/d if d else None}}


def test_fpr_constraint_then_highest_recall_then_exact_tie_order():
    curve = [point(.1, recall=8, fp=2), point(.2, recall=4), point(.3, recall=3, fp=0)]
    assert select_threshold(curve)['threshold'] == .2
    assert select_threshold([point(.1), point(.2, fp=0)])['threshold'] == .2
    assert select_threshold([point(.1), point(.2, mrr=3.)])['threshold'] == .2
    assert select_threshold([point(.1), point(.2, precision=(3, 3))])['threshold'] == .2
    assert select_threshold([point(.1), point(.2)])['threshold'] == .2


def test_all_reject_degeneracy_and_infeasible_denominator():
    assert select_threshold([point(1., recall=0, fp=0, mrr=0, precision=(0, 0))])['Recall@5']['numerator'] == 0
    assert select_threshold([point(.2, fp=2)]) is None
    bad = point(.2); bad['Recall@5']['denominator'] = 9
    with pytest.raises(ValueError, match='8 positive'):
        select_threshold([bad])


def test_repeat_groups_do_not_expand_denominator():
    cases = [{'case_id': f'DEV-{i:02d}'} for i in range(16)]
    rows = [{**r, 'repeat': repeat} for repeat in (1, 2) for r in cases]
    assert len(unique_repeat(rows, cases, 1)) == len(unique_repeat(rows, cases, 2)) == 16
    with pytest.raises(ValueError, match='duplicate'):
        unique_repeat(rows + [rows[0]], cases, 1)


def test_grid_includes_original_threshold_and_is_preregistered():
    assert len(GRID) == 101 and .35 in GRID and GRID[0] == 0 and GRID[-1] == 1


def test_actual_dev_only_http_evidence_and_curve_integrity():
    from evaluation.rag_quality.run_baseline import digest
    root = HERE / 'calibration'
    manifests = list(root.glob('*/manifest.json'))
    assert manifests, 'authorized real HTTP dev evidence required'
    for path in manifests:
        m = json.loads(path.read_text(encoding='utf-8'))
        assert m['outcome'] == 'measured' and m['split'] == 'dev'
        assert m['dataset_version'] == 'a05-threshold-dev-v2'
        assert m['repeat_retrieval_identical'] and m['collection_deleted']
        assert not path.with_name('dataset_v2.json').exists()
        config_path = path.with_name('b0_lexical_calibration_v2.json')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        assert digest(config_path) == m['calibration_sha256']
        assert config['raw_observations_sha256'] == digest(path.with_name('b0_lexical_dev_v2_observations.json'))
        assert config['curve_csv_sha256'] == digest(path.with_name('b0_lexical_threshold_sweep_v2.csv'))
        rows = json.loads(path.with_name('b0_lexical_dev_v2_observations.json').read_text(encoding='utf-8'))
        dev = json.loads(path.with_name('dev_dataset_v2.json').read_text(encoding='utf-8'))
        curve = json.loads(path.with_name('b0_lexical_threshold_sweep_v2.json').read_text(encoding='utf-8'))
        assert len(rows) == 32 and all(r['case_id'].startswith('DEV-') for r in rows)
        assert all(r['vector_queries'] == 1 and r['model_calls'] == 0 for r in rows)
        assert curve['1'] == curve['2'] and len(curve['1']) == 101
        assert select_threshold(curve['1']) == config['selected_dev_metrics']
        for repeat in (1, 2):
            group = unique_repeat(rows, dev['cases'], repeat)
            assert len(group) == 16
            assert all(h['score'] == 1-h['raw_distance'] and h['valid_at_as_of'] for r in group for h in r['candidates'])
        assert config['test_scores_consumed'] == config['test_evaluation_executed'] == False
