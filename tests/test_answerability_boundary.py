"""Deterministic evidence-delivery contract; never claims semantic validation."""
import asyncio
import json

import pytest
from agents.tools import build_shared_rag_tools
from evaluation.answerability.harness import load_dataset, make_kb, manager_for, observe, request
from mcp.default_knowledge_asset import load_approved_defaults


def test_gold_frozen_independently_and_quotes_are_real():
    data = load_dataset()
    assert data['dataset_id']=='a05-answerability-v1'
    assert len(data['cases'])==26
    docs = {d['document_id']:d for d in load_approved_defaults()}
    for case in data['cases']:
        assert case['necessary_facts'] and case['allowed_boundary'] and case['forbidden_promises']
        assert case['human_review']=='pending'
        for evidence in case['available_evidence']:
            assert evidence['quote'] in docs[evidence['document_id']]['content']


def test_usable_never_certifies_fact_sufficiency():
    kb = make_kb()
    # Force a high-scoring relevant hit without granting it missing facts.
    original = kb._collection.query
    def high_score(**kwargs):
        result = original(**kwargs)
        result['distances'] = [[.1]*len(result['ids'][0])]
        return result
    kb._collection.query = high_score
    tool = build_shared_rag_tools(manager_for(kb))['search_knowledge_base']
    payload = asyncio.run(tool.handler(request('退款多久到账？'),{'query':'退款政策'}))
    assert payload['success'] and payload['retrieval_status']=='usable'
    assert payload['results'] and payload['citations']
    assert '事实充分' in payload.get('answer_guidance','')
    assert '原始问题' in payload['answer_guidance']
    assert '逐项' in payload['answer_guidance']


@pytest.mark.parametrize('scenario,expected,success,explanation', [
    ('expired','no_answer',True,'正常知识不足'),
    ('future','no_answer',True,'正常知识不足'),
    ('publishing','no_answer',True,'正常知识不足'),
    ('chroma_failure','degraded',False,'依赖故障'),
])
def test_normal_absence_and_failure_guidance_stay_distinct(scenario,expected,success,explanation):
    tool = build_shared_rag_tools(manager_for(make_kb(scenario)))['search_knowledge_base']
    payload = asyncio.run(tool.handler(request('退款政策'),{'query':'退款政策'}))
    assert payload['retrieval_status']==expected and payload['success'] is success
    assert payload['results']==[] and payload['citations']==[]
    assert explanation in payload['answer_guidance']


@pytest.mark.parametrize('id', ['ANS-03','ANS-08','ANS-09','ANS-12','ANS-25'])
def test_base_boundary_reaches_real_support_sdk_with_or_without_matching_skills(id):
    case = next(c for c in load_dataset()['cases'] if c['id']==id)
    row = asyncio.run(observe(case))
    assert row['boundary_delivered']
    assert row['fake_sdk_calls']==2  # No additional answerability model invocation.
    assert '部分' in row['system_prompt'] and 'Provider' in row['system_prompt']


def test_unmatched_question_gets_same_base_rule():
    from agents.support_agent import SingleSupportAgent
    from evaluation.answerability.harness import AdversarialSDK
    case = load_dataset()['cases'][0]
    agent = SingleSupportAgent(AdversarialSDK(case),'fake')
    prompt = agent._build_system_prompt(request('xyzq'))
    assert '主题相关不等于事实充分' in prompt


def test_capability_denial_remains_usable_when_explicitly_supported():
    kb = make_kb()
    # Natural exact title query above existing .35; no threshold changes.
    tool = build_shared_rag_tools(manager_for(kb))['search_knowledge_base']
    payload = asyncio.run(tool.handler(request('会员与积分'),{'query':'会员与积分'}))
    assert payload['retrieval_status']=='usable'
    assert any('未实现会员账户' in h['content'] for h in payload['results'])
    assert '不支持该功能' in payload.get('answer_guidance','')


def test_provider_not_found_and_failure_do_not_become_knowledge_absence():
    cases = {c['id']:c for c in load_dataset()['cases']}
    missing = asyncio.run(observe(cases['ANS-14']))['provider_payload']
    cross = asyncio.run(observe(cases['ANS-15']))['provider_payload']
    failure = asyncio.run(observe(cases['ANS-21']))['provider_payload']
    assert missing['error']['code']==cross['error']['code']=='not_found'
    assert failure['error']['code']=='dependency_failure'
    assert all(r['data'] is None for r in (missing,cross,failure))


def test_adversarial_sdk_can_still_ignore_rule_not_a_semantic_validator():
    # Required limitation: a passing delivery test must not certify fake prose.
    case = load_dataset()['cases'][4]
    row = asyncio.run(observe(case))
    assert case['forbidden_promises'][0] in row['scripted_adversarial_reply']
    assert row['model_obedience']=='not_measured'
