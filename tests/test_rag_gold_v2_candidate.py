"""Validate the explicitly authorized Gold edits; no quality experiment runs."""
import re

from evaluation.rag_quality.run_baseline import (
    HERE, ROOT, active_identities, chunk_catalog, digest, load_frozen, validate_dataset,
)
from evaluation.rag_quality.prepare_gate import read, validate_dev


def candidates():
    return read(HERE / 'dataset_v2.candidate.json'), read(HERE / 'dev_dataset_v2.candidate.json')


def test_counts_structure_ids_and_gold_remain_compatible():
    corpus, old, _ = load_frozen()
    new, dev = candidates()
    validate_dataset(corpus, new)
    validate_dev(corpus, dev, new)
    assert len(new['cases']) == 30 and sum(r['answerable'] for r in new['cases']) == 21
    assert len(dev['cases']) == 16 and sum(r['answerable'] for r in dev['cases']) == 8
    assert new.keys() == old.keys()
    assert new['stratification'] == old['stratification']
    for a, b in zip(old['cases'], new['cases'], strict=True):
        assert a.keys() == b.keys()
        for field in ('case_id', 'category', 'answerable', 'gold_document_id', 'gold_chunk_id',
                      'gold_chunk_index', 'policy_version', 'evidence_location'):
            assert a[field] == b[field]


def test_only_user_authorized_case_fields_changed():
    _, old, _ = load_frozen()
    new, dev = candidates()
    expected = {'A05-03': {'query', 'annotation_reason'},
                'A05-05': {'gold_evidence', 'annotation_reason'},
                'A05-12': {'annotation_reason'}}
    for a, b in zip(old['cases'], new['cases'], strict=True):
        assert {k for k in a if a[k] != b[k]} == expected.get(a['case_id'], set())
    old_dev = read(HERE / 'dev_dataset_v1.json')
    expected_dev = {'DEV-04': {'annotation_reason'}, 'DEV-07': {'query', 'annotation_reason'}}
    for a, b in zip(old_dev['cases'], dev['cases'], strict=True):
        assert a.keys() == b.keys()
        assert {k for k in a if a[k] != b[k]} == expected_dev.get(a['case_id'], set())
    assert {k for k in old if old[k] != new[k]} == {'version', 'annotation_process', 'cases'}
    assert {k for k in old_dev if old_dev[k] != dev[k]} == {'version', 'purpose', 'human_review_status', 'cases'}


def test_shipping_two_facts_in_same_current_actual_chunk():
    corpus, _, _ = load_frozen()
    new, _ = candidates()
    case = new['cases'][4]
    facts = ['加急配送：1-2 个工作日送达，运费 15 元',
             '同城配送：当日达或次日达，运费 10 元']
    chunk = next(c for c in chunk_catalog(corpus) if c['chunk_id'] == case['gold_chunk_id'])
    assert all(fact in case['gold_evidence'] and fact in chunk['content'] for fact in facts)
    assert case['gold_evidence'] in chunk['content']
    actual = read(ROOT / 'evaluation/reports/rag_quality/20261012T073909Z-a7bd452b/chunks.json')
    assert chunk in actual
    assert (chunk['document_id'], chunk['policy_version']) in active_identities(corpus)
    assert '不假设所有用户满足同城条件' in case['annotation_reason']


def test_queries_and_multi_fact_explanations_follow_human_decisions():
    _, old, _ = load_frozen()
    new, dev = candidates()
    assert new['cases'][0] == old['cases'][0]
    assert new['cases'][1] == old['cases'][1]  # Only complete account recovery is Gold.
    assert new['cases'][4]['query'] == old['cases'][4]['query']
    assert new['cases'][2]['query'] == '我想看看买的东西发货了没有、现在是什么状态，应该怎么查？'
    assert dev['cases'][6]['query'] == '如果收货地址比较偏远，包裹可能要多等几天？'
    assert dev['cases'][3]['query'] == read(HERE / 'dev_dataset_v1.json')['cases'][3]['query']
    assert '12×1=12' in dev['cases'][3]['annotation_reason']
    twelve = new['cases'][11]
    assert twelve['query'] == old['cases'][11]['query']
    assert twelve['gold_evidence'] == old['cases'][11]['gold_evidence']
    assert '401表示认证失败' in twelve['annotation_reason']
    assert '500表示服务端问题' in twelve['annotation_reason']
    assert '网络排查和支付描述不是本题要求' in twelve['annotation_reason']


def test_negative_lifecycle_labels_and_dev_test_separation():
    corpus, old, _ = load_frozen()
    new, dev = candidates()
    for i in [18, 19, 26, 27, 28, 29]:
        assert new['cases'][i] == old['cases'][i] and new['cases'][i]['answerable'] is False
    assert [new['cases'][i]['excluded_evidence']['reason'] for i in range(26, 30)] == [
        'superseded', 'not_yet_effective', 'expired', 'revoked']
    eligible = active_identities(corpus)
    assert ('eval-exchange', 'demo-v2') in eligible
    assert all((r['excluded_evidence']['document_id'], r['excluded_evidence']['policy_version']) not in eligible
               for r in new['cases'][26:])
    leak = validate_dev(corpus, dev, new)
    assert leak['exact_duplicates'] == leak['high_similarity_flags'] == []


def test_candidate_reviews_and_all_history_hashes_preserved():
    validation = read(HERE / 'gold_v2_candidate_validation.json')
    for name, expected in validation['protected_sha256'].items():
        path = HERE / 'history/run_baseline_v1.py.txt' if name == 'evaluation/rag_quality/run_baseline.py' else ROOT / name
        assert digest(path) == expected
    for name, expected in validation['candidate_sha256'].items():
        assert digest(HERE / name) == expected
    new, dev = candidates()
    assert new['version'].endswith('-candidate') and dev['version'].endswith('-candidate')
    assert dev['human_review_status'] == 'candidate_pending_final_acceptance'
    # Candidate history stays pending; the user's later approval is in a separate official freeze.
    if (HERE / 'freeze_v2.json').exists():
        _, official, lock = load_frozen('v2')
        assert official['cases'] == new['cases']
        assert lock['review']['status'] == 'user_approved_v2'
    assert validation['status'] == 'candidate_pending_final_acceptance'
    review = (HERE / 'gold_review_v2.md').read_text(encoding='utf-8')
    assert len(re.findall(r'^## A05-\d\d ', review, re.M)) == 30
    assert review.count('最终人工验收/冻结：**待用户确认**') == 30
    diff = (HERE / 'gold_v1_to_v2_diff.md').read_text(encoding='utf-8')
    assert all(r['case_id'] in diff for r in new['cases'] + dev['cases'])
