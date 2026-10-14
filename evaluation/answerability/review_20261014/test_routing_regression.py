"""Expected-safe red probes only. Production routing remains untouched.

Run explicitly; these are recorded open defects, not fixed-regression claims.
"""
import pytest
from evaluation.answerability.review_20261014.probe import route_probe
from evaluation.answerability.harness import load_dataset


@pytest.fixture(scope='module')
def exact():
    return route_probe(load_dataset()['cases'][23]['query'])


def test_exact_ans24_question_does_not_create_new_handoff(exact):
    assert not exact['matched_explicit_handoff']
    assert exact['sdk_calls']==2
    assert exact['state_diff']['handoff_count_after']==0
    assert not exact['state_diff']['business_changed']
    assert exact['body']['escalated'] is False


def test_rule_question_paraphrase_must_not_mutate_handoff_state():
    row = route_probe('订单查询：模拟人工交接记录创建成功是否说明已转人工客服？')
    assert row['state_diff']['handoff_count_after']==0
    assert row['sdk_calls']>0


def test_grounded_negative_explanation_is_not_deleted(exact):
    assert '不代表真人接单' in exact['body']['response']
