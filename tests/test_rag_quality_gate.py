"""Offline P2 gate checks only; no model, service or network dependency."""
import re

import pytest

from evaluation.rag_quality.prepare_gate import (
    P1, choose_threshold, leakage_report, read, render_review, similarity,
    validate_dev, validate_review, verify_p1,
)
from evaluation.rag_quality.run_baseline import HERE, chunk_catalog, digest, load_frozen


def inputs():
    corpus, test, _ = load_frozen()
    return corpus, test, read(HERE / 'dev_dataset_v1.json'), read(HERE / 'gold_review_notes_v1.json')


def test_original_inputs_and_reports_match_gate_entry_snapshot():
    lock = read(HERE / 'p2_gate_freeze_v1.json')
    assert lock['human_review_status'] == 'pending'
    assert lock['formal_experiment_status'] == 'blocked'
    for filename, expected in lock['preserved_original_sha256'].items():
        assert digest(HERE / filename) == expected
    for filename, expected in lock['p1_report_sha256'].items():
        assert digest(P1 / filename) == expected
    for filename, expected in lock['gate_inputs_sha256'].items():
        assert digest(HERE / filename) == expected


def test_review_has_30_complete_records_and_no_human_acceptance():
    corpus, test, _, review = inputs()
    assert validate_review(corpus, test, review) == {'合理': 19, '需人工判断': 10, '疑似错误': 1}
    assert chunk_catalog(corpus) == read(P1 / 'chunks.json')
    rendered = render_review(corpus, test, review)
    assert rendered == (HERE / 'gold_review_v1.md').read_text(encoding='utf-8')
    assert len(re.findall(r'^## A05-\d\d ', rendered, re.M)) == 30
    assert rendered.count('用户审核决定：**待审核**') == 30
    for row in test['cases']:
        assert row['case_id'] in rendered and row['query'] in rendered
        if row['answerable']:
            assert row['gold_chunk_id'] in rendered and row['gold_evidence'] in rendered


@pytest.mark.parametrize('kind', ['missing_case', 'duplicate_case', 'invented_quote', 'approved'])
def test_review_rejects_incomplete_or_fabricated_approval(kind):
    corpus, test, _, review = inputs()
    if kind == 'missing_case':
        review['cases'].pop()
    elif kind == 'duplicate_case':
        review['cases'][-1] = review['cases'][0]
    elif kind == 'invented_quote':
        review['cases'][0]['additional_evidence'] = [{'document_index': 0, 'quote': 'Invented Gold'}]
    elif kind == 'approved':
        review['human_review_status'] = 'approved'
    with pytest.raises(ValueError):
        validate_review(corpus, test, review)


def test_dev_structure_gold_and_leakage_checked():
    corpus, test, dev, _ = inputs()
    leak = validate_dev(corpus, dev, test)
    assert len(dev['cases']) == 16 and sum(r['answerable'] for r in dev['cases']) == 8
    assert leak['exact_duplicates'] == leak['high_similarity_flags'] == []
    assert len(leak['nearest_test_query']) == 16
    assert read(HERE / 'gate_checks_v1.json')['leakage'] == leak


@pytest.mark.parametrize('kind', ['duplicate_id', 'test_query', 'near_copy', 'gold_text', 'time', 'no_answer_gold'])
def test_dev_validation_blocks_bad_labels_and_query_leakage(kind):
    corpus, test, dev, _ = inputs()
    if kind == 'duplicate_id':
        dev['cases'][1]['case_id'] = dev['cases'][0]['case_id']
    elif kind == 'test_query':
        dev['cases'][0]['query'] = test['cases'][0]['query']
    elif kind == 'near_copy':
        dev['cases'][0]['query'] = test['cases'][0]['query'] + ' 请说明'
    elif kind == 'gold_text':
        dev['cases'][0]['gold_evidence'] = 'Absent evidence'
    elif kind == 'time':
        dev['as_of'] = '2026-11-01T00:00:00Z'
    elif kind == 'no_answer_gold':
        dev['cases'][8]['gold_chunk_id'] = dev['cases'][0]['gold_chunk_id']
    with pytest.raises(ValueError):
        validate_dev(corpus, dev, test)


def test_duplicate_detection_normalizes_case_and_punctuation():
    assert similarity('A05退款？', 'a05退款!') == {'sequence_ratio': 1., 'bigram_jaccard': 1.}


def test_p1_failure_classes_verified_from_actual_candidates():
    _, dataset, _, _ = inputs()
    result = verify_p1(read(P1 / 'observations.json'), dataset)
    for group in result.values():
        assert group['counts'] == [18, 6, 3, 12, 4]
        assert group['not_recalled'] == ['A05-01', 'A05-05', 'A05-06']
        assert group['theme_without_requested_fact'] == ['A05-19', 'A05-20', 'A05-21', 'A05-23']
        assert len(group['below_threshold']) == 12


def toy_rows():
    # Explicit synthetic arithmetic fixture, never a model/quality result.
    return [
        {'case_id': 'DEV-toy1', 'answerable': True, 'gold_chunk_id': 'a',
         'candidates': [{'chunk_id': 'a', 'score': .6}]},
        {'case_id': 'DEV-toy2', 'answerable': True, 'gold_chunk_id': 'b',
         'candidates': [{'chunk_id': 'b', 'score': .4}]},
        {'case_id': 'DEV-toy3', 'answerable': False, 'gold_chunk_id': None,
         'candidates': [{'chunk_id': 'wrong', 'score': .5}]},
    ]


def test_threshold_constraint_does_not_just_maximize_recall():
    result = choose_threshold(toy_rows(), [.3, .4, .5, .6, .7], max_false_positive=0)
    assert result['selected']['threshold'] == .6
    assert result['selected']['recall5_count'] == 1
    assert result['selected']['false_positive_count'] == 0
    assert result['table'][0]['recall5_count'] == 2 and result['table'][0]['false_positive_count'] == 1
    assert result['table'][2]['false_positive_count'] == 1  # Boundary >= .5.


def test_calibration_rejects_test_rows_and_marks_infeasible():
    rows = toy_rows()
    rows[0]['case_id'] = 'A05-01'
    with pytest.raises(ValueError, match='DEV-'):
        choose_threshold(rows)
    result = choose_threshold(toy_rows(), [.3], max_false_positive=0)
    assert result['status'] == 'calibration_infeasible' and result['selected'] is None


def test_model_evidence_pins_dimension_pooling_and_actual_file_ids():
    models = read(HERE / 'model_resources_v1.json')
    assert models['weights_downloaded'] is False
    expected = {'BAAI/bge-small-zh-v1.5': (512, True, 96378296),
                'intfloat/multilingual-e5-small': (384, False, 492795290)}
    for m in models['models']:
        dim, cls, size = expected[m['model_id']]
        assert re.fullmatch('[a-f0-9]{40}', m['revision']) and m['license'] == 'mit'
        assert m['configs']['config.json']['content']['hidden_size'] == dim
        assert m['configs']['1_Pooling/config.json']['content']['pooling_mode_cls_token'] == cls
        assert m['proposed_model_download_bytes'] == size
        weights = [f for f in m['proposed_download_files'] if f['rfilename'] == 'model.safetensors']
        assert len(weights) == 1 and re.fullmatch('[a-f0-9]{64}', weights[0]['lfs']['sha256'])
        assert not any(f['rfilename'] == 'pytorch_model.bin' for f in m['proposed_download_files'])
        for config in m['configs'].values():
            assert m['revision'] in config['url']


def test_protocol_covers_groups_denominators_cost_and_blockers():
    protocol = (HERE / 'p2_experiment_protocol.md').read_text(encoding='utf-8')
    for term in ['B0-original', 'B0-calibrated', 'B1-raw', 'B1-calibrated',
                 'Recall@1/3/5', 'MRR', '无答案FPR', 'Citation evidence precision',
                 'P50/P95', 'RSS', 'calibration_infeasible', 'blocked', '512', '384',
                 '21条正向', '9条无答案', '12.5%', 'API调用', '改进', '退化', '无变化']:
        assert term in protocol
