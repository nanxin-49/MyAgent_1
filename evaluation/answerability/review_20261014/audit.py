"""Read-only validation and additive derived statistics; never approve Gold."""
import hashlib
import json
import subprocess
from collections import Counter

from mcp.default_knowledge_asset import ASSET, APPROVAL, load_approved_defaults
from evaluation.answerability.harness import ROOT
from evaluation.answerability.review_20261014.probe import OUT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def differences(a,b,path=''):
    if type(a)!=type(b):
        return [{'path':path,'before':a,'after':b}]
    if isinstance(a,dict):
        result = []
        for key in sorted(set(a)|set(b)):
            if key not in a or key not in b:
                result.append({'path':path+'/'+key,'before':a.get(key),'after':b.get(key)})
            else:
                result += differences(a[key],b[key],path+'/'+key)
        return result
    if isinstance(a,list):
        if len(a)!=len(b):
            return [{'path':path,'before':a,'after':b}]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'/'+str(i))]
    return [] if a==b else [{'path':path,'before':a,'after':b}]


def main():
    # Capture all old tracked artifacts before any Workbench-only updates.
    files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
    if not (OUT/'protected_before.json').exists():
        (OUT/'protected_before.json').write_text(json.dumps({f:sha(ROOT/f) for f in files if f and (ROOT/f).is_file()},
            ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    base = ROOT/'evaluation/answerability'
    previous = ROOT/'evaluation/reports/hardening/A05/answerability-20261013'
    paths = [base/n for n in ('dataset_v1.json','dataset_v1.review_candidate.json','freeze_v1.json',
        'review_addendum.json','gold_review_v1.md')]+[previous/n for n in ('corpus_snapshot.json','before.json',
        'after_final.json','per_case.md','REPORT.md','final_inputs_sha256.json')]+[ASSET,APPROVAL]
    original,candidate,freeze,addendum = [read(base/n) for n in ('dataset_v1.json','dataset_v1.review_candidate.json',
        'freeze_v1.json','review_addendum.json')]
    assert sha(base/'dataset_v1.json')==freeze['dataset_sha256']==addendum['original_frozen_sha256']
    assert sha(base/'dataset_v1.review_candidate.json')==addendum['review_candidate_sha256']
    assert sha(ASSET)==freeze['asset_sha256']
    delta = differences(original,candidate)
    assert len(delta)==1 and delta[0]['path']=='/cases/17/allowed_boundary'
    assert delta[0]['before']==addendum['change']['before'] and delta[0]['after']==addendum['change']['after']
    corpus = load_approved_defaults()
    assert read(previous/'corpus_snapshot.json')==corpus
    docs = {d['document_id']:d for d in corpus}
    histories = {n:read(previous/n) for n in ('before.json','after_final.json')}
    fixture = read(ROOT/'tests/fixtures/business_provider_data.json')
    from providers.models import Order,Shipment
    from agents.tools import build_business_tools
    from providers.mock_backend import InMemoryBusinessBackend
    tools = build_business_tools(InMemoryBusinessBackend(fixture))
    complete = []
    required = ('id','query','necessary_facts','available_evidence','gold_behavior','allowed_boundary',
                'forbidden_promises','scenario','dynamic_tool','dynamic_args','human_review')
    for c in candidate['cases']:
        assert all(k in c for k in required)
        assert c['query'] and c['necessary_facts'] and c['gold_behavior'] and c['allowed_boundary'] and c['forbidden_promises']
        assert c['human_review']=='pending'
        for evidence in c['available_evidence']:
            doc = docs[evidence['document_id']]
            assert evidence['quote'] in doc['content']
            assert evidence['source']==doc['source']
            assert evidence['content_sha256']==hashlib.sha256(doc['content'].encode()).hexdigest()
        if c['dynamic_tool']:
            assert c['dynamic_tool'] in tools
            assert c['dynamic_args'] and 'order_id' in c['dynamic_args']
        for h in histories.values():
            r = next(r for r in h['rows'] if r['id']==c['id'])
            assert r['query']==c['query'] and r['gold_behavior']==c['gold_behavior']
            for hit in r['raw_hits']+r['rag_payload']['results']:
                doc = docs[hit['document_id']]
                assert hit['content']==doc['content']
                assert hit['source']==doc['source']
                if hit.get('citation'):
                    assert hit['citation']['content_hash']==hashlib.sha256(doc['content'].encode()).hexdigest()
                    assert hit['citation']['document_id']==doc['document_id']
                    assert hit['citation']['source']==doc['source']
                    assert hit['citation']['policy_version']==doc['policy_version']
        complete.append({'id':c['id'],'complete':True,'evidence_quote_and_hash_valid':True,
            'dynamic_tool':c['dynamic_tool'],'isolation_scenario':c['scenario']})
    assert len(complete)==26 and len({c['id'] for c in candidate['cases']})==26
    historical_manifest = read(previous/'final_inputs_sha256.json')
    checked = {}
    for rel,expected in historical_manifest.items():
        actual = sha(ROOT/rel)
        checked[rel]={'expected':expected,'actual':actual,'match':expected==actual}
    assert all(r['match'] for r in checked.values())
    integrity = {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'original_candidate_freeze_addendum_hashes_valid':True,'candidate_differences':delta,
        'input_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
        'historical_final_inputs_manifest_check':checked,'cases':complete,
        'requested_corpus_path_exists':(base/'corpus_snapshot.json').exists(),
        'actual_corpus_path':(previous/'corpus_snapshot.json').relative_to(ROOT).as_posix(),
        'Order_fields':list(Order.model_fields),'Shipment_fields':list(Shipment.model_fields),
        'provider_fixture_sha256':sha(ROOT/'tests/fixtures/business_provider_data.json'),
        'no_Gold_approval':True,'no_freeze_created':True}
    (OUT/'gold_integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    current = read(OUT/'sdk_delivery_actual.json')['rows']
    metrics = {'historical_formula':'BASE_RULES substrings in first captured support system AND 事实充分 in final rag answer_guidance',
        'historical_before_boundary_delivered':sum(r['boundary_delivered'] for r in histories['before.json']['rows']),
        'historical_after_boundary_delivered':sum(r['boundary_delivered'] for r in histories['after_final.json']['rows']),
        'historical_payload_guidance_presence_before':sum(bool(r['rag_payload'].get('answer_guidance')) for r in histories['before.json']['rows']),
        'historical_payload_guidance_presence_after':sum(bool(r['rag_payload'].get('answer_guidance')) for r in histories['after_final.json']['rows']),
        'current_cases':26,'current_constructed_prompt_has_rules':sum(r['constructed_prompt_has_rules'] for r in current),
        'current_model_invoked_case_denominator':sum(r['sdk_invoked'] for r in current),
        'current_deterministic_gate_case_count':sum(r['explicit_gate'] for r in current),
        'current_support_sdk_request_count':sum(r['support_sdk_calls'] for r in current),
        'current_all_sdk_requests_received_rules_case_count':sum(r['every_sdk_system_has_rules'] for r in current),
        'current_final_sdk_base_rules_received':sum(r['final_sdk_contains_base_rules'] for r in current),
        'current_payload_guidance_present':sum(r['rag_payload_answer_guidance_present'] for r in current),
        'current_final_sdk_guidance_received':sum(r['guidance_in_final_sdk_tool_message'] for r in current),
        'ANS24_exact':{k:v for k,v in current[23].items() if k not in ('sdk_requests','trace','rag_payload')},
        'statuses':dict(Counter(r['rag_payload']['retrieval_status'] for r in histories['after_final.json']['rows'])),
        'forced_tool_selection':'scripted fake, not model tool-routing quality',
        'not_model_accuracy':True}
    (OUT/'delivery_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'integrity':'passed','candidate_diffs':len(delta),'cases':26,
        'actual_sdk_case_count':metrics['current_model_invoked_case_denominator'],
        'actual_sdk_requests':metrics['current_support_sdk_request_count']},ensure_ascii=False))


if __name__=='__main__':
    main()
