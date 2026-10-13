"""Explicit version selection, approval provenance and fail-closed frozen inputs."""
import json
import shutil

import pytest

import evaluation.rag_quality.run_baseline as baseline
from evaluation.rag_quality.prepare_gate import read


def test_v2_official_data_equals_approved_candidates():
    corpus, dataset, lock = baseline.load_frozen('v2')
    assert dataset['cases'] == read(baseline.HERE / 'dataset_v2.candidate.json')['cases']
    dev = read(baseline.HERE / 'dev_dataset_v2.json')
    assert dev['cases'] == read(baseline.HERE / 'dev_dataset_v2.candidate.json')['cases']
    assert len(dataset['cases']) == 30 and sum(c['answerable'] for c in dataset['cases']) == 21
    assert len(dev['cases']) == 16 and sum(c['answerable'] for c in dev['cases']) == 8
    assert lock['review']['status'] == 'user_approved_v2'
    assert lock['review']['approved_date'] == '2026-10-13'
    assert not lock['review']['independent_double_annotation'] and not lock['review']['fully_blind_review']
    assert corpus['as_of'] == lock['as_of'] == '2026-10-12T00:00:00Z'


def test_default_and_explicit_v1_remain_identical():
    assert baseline.load_frozen() == baseline.load_frozen('v1')
    assert baseline.load_frozen('v1')[1]['version'] == 'a05-dataset-v1'
    assert baseline.load_frozen('v2')[1]['version'] == 'a05-dataset-v2'


def test_real_http_v2_two_round_saved_evidence():
    # Audit actual HTTP observations; this test never fabricates scores or reruns a model.
    root = baseline.ROOT / 'evaluation/reports/rag_quality/v2'
    manifests = list(root.glob('*/manifest.json'))
    assert manifests, 'authorized v2 real HTTP baseline evidence is required'
    for path in manifests:
        manifest = read(path)
        assert manifest['outcome'] == 'measured' and manifest['backend'] == 'real Chroma HTTP'
        assert manifest['dataset_version'] == 'a05-dataset-v2' and manifest['repeats'] == 2
        assert manifest['dataset_sha256'] == baseline.digest(path.with_name('dataset_v2.json'))
        assert manifest['freeze_sha256'] == baseline.digest(path.with_name('freeze_v2.json'))
        assert manifest['physical_chunks'] == 11 and len(manifest['eligible_chunk_ids']) == 7
        assert manifest['repeat_retrieval_identical'] and manifest['collection_deleted']
        assert manifest['rewrite'] == manifest['rerank'] == manifest['cache'] == False
        rows = read(path.with_name('observations.json'))
        summary = read(path.with_name('summary.json'))
        assert len(rows) == 60
        for repeat in (1, 2):
            group = [r for r in rows if r['repeat'] == repeat]
            assert len(group) == 30 and summary[str(repeat)] == baseline.aggregate(group)
            assert all(r['retrieval_calls'] == r['vector_queries'] == 1 and r['model_calls'] == 0 for r in group)
            assert all(r['citations'] == [h['citation'] for h in r['hits']] for r in group)
            assert all(h['frozen_chunk_id'] in manifest['eligible_chunk_ids'] for r in group for h in r['candidates'])


@pytest.mark.parametrize('version', ['v3', 'candidate', '../v1', '', None])
def test_unknown_version_rejected_before_service_access(version):
    with pytest.raises(ValueError, match='unsupported'):
        baseline.load_frozen(version)


@pytest.mark.parametrize('fault', ['missing_dataset', 'missing_freeze', 'missing_dev', 'test_hash',
    'dev_hash', 'corpus_hash', 'version_content', 'wrong_lock_version', 'approval', 'counts', 'labels', 'extra_path'])
def test_corrupt_or_missing_frozen_inputs_fail_closed(tmp_path, monkeypatch, fault):
    for file in ['freeze_v2.json', 'corpus_v1.json', 'dataset_v2.json', 'dev_dataset_v2.json',
                 'gold_review_v2.md', 'gold_v1_to_v2_diff.md']:
        shutil.copyfile(baseline.HERE / file, tmp_path / file)
    lock_path = tmp_path / 'freeze_v2.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if fault.startswith('missing_'):
        file = {'missing_dataset': 'dataset_v2.json', 'missing_freeze': 'freeze_v2.json',
                'missing_dev': 'dev_dataset_v2.json'}[fault]
        (tmp_path / file).unlink()
    elif fault.endswith('_hash'):
        file = {'test_hash': 'dataset_v2.json', 'dev_hash': 'dev_dataset_v2.json',
                'corpus_hash': 'corpus_v1.json'}[fault]
        with (tmp_path / file).open('a', encoding='utf-8') as stream:
            stream.write(' ')
    elif fault == 'version_content':
        path = tmp_path / 'dataset_v2.json'
        dataset = json.loads(path.read_text(encoding='utf-8'))
        dataset['version'] = 'a05-dataset-v1'
        path.write_text(json.dumps(dataset), encoding='utf-8')
        lock['files']['dataset_v2.json'] = baseline.digest(path)
    elif fault == 'wrong_lock_version':
        lock['version'] = 'a05-freeze-v1'
    elif fault == 'approval':
        lock['review']['status'] = 'pending'
    elif fault == 'counts':
        lock['test_counts']['answerable'] = 22
    elif fault == 'labels':
        lock['test_gold_labels'][0]['answerable'] = False
    elif fault == 'extra_path':
        lock['files']['../unrelated.json'] = '0' * 64
    if fault != 'missing_freeze':
        lock_path.write_text(json.dumps(lock), encoding='utf-8')
    monkeypatch.setattr(baseline, 'HERE', tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        baseline.load_frozen('v2')
