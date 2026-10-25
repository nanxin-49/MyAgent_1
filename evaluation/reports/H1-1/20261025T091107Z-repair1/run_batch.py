"""H1-1 batch 1: five real-HTTP /chat scenarios with deterministic assertions.

No retries. Every request/response, trace, state snapshot and model-ledger delta is
saved next to this script. Failed assertions do not stop the batch; later scenarios
still run unless the model budget is exhausted.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding='utf-8')

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[3]
PRIVATE = ROOT / 'cash' / 'h11-e2e-20261025'
BASE = 'http://127.0.0.1:8017'
LEDGER = RUN / 'model_ledger.json'


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding='utf-8'))
    return {'requests': 0, 'charged_or_reserved_usd': 0.0, 'halted': False}


def ledger_snapshot():
    ledger = load_ledger()
    return {
        'requests': ledger.get('requests', 0),
        'charged_or_reserved_usd': ledger.get('charged_or_reserved_usd', 0.0),
        'halted': ledger.get('halted', False),
    }


def identities():
    return json.loads((PRIVATE / 'credentials.json').read_text(encoding='utf-8'))


def headers(identities_map, who):
    return {'Authorization': 'Bearer ' + identities_map[who]['token']}


def check(results, name, condition, detail=None):
    results.append({'assertion': name, 'pass': bool(condition), 'detail': detail})


def verdict(results):
    return 'pass' if results and all(item['pass'] for item in results) else 'fail'


def chat(client, idmap, who, message, conv_id, handoff_key=None):
    body = {'message': message, 'conv_id': conv_id}
    if handoff_key is not None:
        body['handoff_key'] = handoff_key
    response = client.post('/chat', json=body, headers=headers(idmap, who))
    try:
        payload = response.json()
    except ValueError:
        payload = {'raw': response.text}
    result = {'request': body, 'principal': idmap[who]['identity'],
              'http_status': response.status_code, 'api_response': payload}
    request_id = payload.get('request_id')
    if request_id:
        trace = client.get('/trace/tool/' + request_id, headers=headers(idmap, 'admin'))
        result['trace_http_status'] = trace.status_code
        result['trace'] = trace.json()
    return result


def state(client, idmap):
    response = client.get('/__h11/state', headers=headers(idmap, 'admin'))
    response.raise_for_status()
    return response.json()


def mutate(client, idmap, payload):
    response = client.post('/__h11/state', json=payload, headers=headers(idmap, 'admin'))
    response.raise_for_status()
    return response.json()


def wait_ready(client):
    last = None
    for _ in range(60):
        try:
            response = client.get('/health')
            if response.status_code == 200:
                return response.json()
            last = response.status_code
        except Exception as exc:  # connection refused while uvicorn starts
            last = type(exc).__name__
        time.sleep(1)
    raise RuntimeError(f'API not ready: {last}')


def no_new_writes(before, after):
    return (len(after.get('actions') or {}) == len(before.get('actions') or {})
            and len(after.get('handoffs') or {}) == len(before.get('handoffs') or {}))


def run_preflight(client, idmap):
    results = []
    checks = {}
    for label, path, who, expected in [
        ('anonymous_trace', '/trace/tools', None, 401),
        ('customer_trace', '/trace/tools', 'customer1', 403),
        ('admin_trace', '/trace/tools', 'admin', 200),
    ]:
        response = client.get(path, headers=headers(idmap, who) if who else {})
        checks[label] = {'status': response.status_code}
        check(results, label, response.status_code == expected, response.status_code)
    response = client.post('/chat', json={'message': 'unauthorized probe'})
    checks['anonymous_chat'] = {'status': response.status_code}
    check(results, 'anonymous_chat_401', response.status_code == 401, response.status_code)
    response = client.post('/chat', json={'message': 'identity probe', 'user_id': 'customer-2'},
                           headers=headers(idmap, 'customer1'))
    checks['identity_mismatch'] = {'status': response.status_code}
    check(results, 'identity_mismatch_403', response.status_code == 403, response.status_code)
    save('http_preflight.json', {'checks': checks, 'assertions': results})
    return results


def run_s1(client, idmap):
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer1', '退款需要满足什么条件？', 'h11-s1-customer1')
    after = state(client, idmap)
    payload = case['api_response']
    tools = payload.get('tools_used') or []
    citations = payload.get('citations') or []
    answer = payload.get('response') or ''
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'search_knowledge_base_selected', 'search_knowledge_base' in tools, tools)
    check(results, 'retrieval_status_usable', payload.get('retrieval_status') == 'usable', payload.get('retrieval_status'))
    check(results, 'citations_present', bool(citations), len(citations))
    check(results, 'citation_policy_version',
          any((c.get('policy_version') == 'refund-cancel-v1') for c in citations),
          [c.get('policy_version') for c in citations])
    check(results, 'citation_content_hash', any(c.get('content_hash') for c in citations),
          [bool(c.get('content_hash')) for c in citations])
    check(results, 'answer_mentions_window', bool(re.search(r'7\s*(?:天|×24|个?24)', answer)) or '七天' in answer, answer[:200])
    check(results, 'answer_mentions_threshold', '500' in answer, answer[:200])
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    case.update(scenario='S1', assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_s1.json', case)
    return case


def run_s1b(client, idmap):
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer1', '退款政策是什么？', 'h11-s1b-customer1')
    after = state(client, idmap)
    payload = case['api_response']
    tools = payload.get('tools_used') or []
    citations = payload.get('citations') or []
    answer = payload.get('response') or ''
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'search_knowledge_base_selected', 'search_knowledge_base' in tools, tools)
    check(results, 'retrieval_status_usable', payload.get('retrieval_status') == 'usable', payload.get('retrieval_status'))
    check(results, 'citations_present', bool(citations), len(citations))
    check(results, 'citation_policy_version',
          any((c.get('policy_version') == 'refund-cancel-v1') for c in citations),
          [c.get('policy_version') for c in citations])
    check(results, 'citation_content_hash', any(c.get('content_hash') for c in citations),
          [bool(c.get('content_hash')) for c in citations])
    check(results, 'answer_mentions_window', bool(re.search(r'7\s*(?:天|×24|个?24)', answer)) or '七天' in answer, answer[:200])
    check(results, 'answer_mentions_threshold', '500' in answer, answer[:200])
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    case.update(scenario='S1B', assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_s1b.json', case)
    return case


def run_s2(client, idmap):
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer1', '退款审核通过后，钱几天能到我的银行卡？', 'h11-s2-customer1')
    after = state(client, idmap)
    payload = case['api_response']
    tools = payload.get('tools_used') or []
    citations = payload.get('citations') or []
    answer = payload.get('response') or ''
    fabricated = re.search(r'(?:到账|退回|退款)[^。！？\n]{0,12}?(?:\d+|[一二两三四五六七八九十]+)\s*(?:个)?\s*(?:工作日|天|小时)', answer)
    boundary = re.search(r'(?:无法确认|不能确认|不承诺|没有承诺|未承诺|无法保证|不保证|无法核实|不能保证)', answer)
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'search_knowledge_base_selected', 'search_knowledge_base' in tools, tools)
    check(results, 'no_fabricated_arrival_time', fabricated is None, fabricated.group(0) if fabricated else None)
    check(results, 'states_boundary', boundary is not None, boundary.group(0) if boundary else None)
    check(results, 'retrieval_evidence_recorded',
          bool(citations) or payload.get('retrieval_status') in {'low_confidence', 'no_answer'},
          {'retrieval_status': payload.get('retrieval_status'), 'citations': len(citations)})
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    case.update(scenario='S2', assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_s2.json', case)
    return case


def run_s3(client, idmap):
    results = []
    conv = 'h11-s3-customer1'
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    first = chat(client, idmap, 'customer1', '帮我查订单 ORD-H11-ORDER 的状态', conv)
    payload = first['api_response']
    tools = payload.get('tools_used') or []
    answer = payload.get('response') or ''
    check(results, 'turn1_http_200', first['http_status'] == 200, first['http_status'])
    check(results, 'turn1_get_order_selected', 'get_order' in tools, tools)
    check(results, 'turn1_shipped_seen', bool(re.search(r'shipped|已发货|运输中', answer, re.IGNORECASE)), answer[:200])

    mutate(client, idmap, {'orders': {'ORD-H11-ORDER': {'status': 'delivered'}},
                           'shipments': {'ORD-H11-ORDER': {'status': 'delivered'}}})
    between = state(client, idmap)
    check(results, 'isolated_state_mutated', between['business']['orders']['ORD-H11-ORDER']['status'] == 'delivered',
          between['business']['orders']['ORD-H11-ORDER']['status'])

    second = chat(client, idmap, 'customer1', '现在呢？', conv)
    payload2 = second['api_response']
    tools2 = payload2.get('tools_used') or []
    answer2 = payload2.get('response') or ''
    after = state(client, idmap)
    check(results, 'turn2_http_200', second['http_status'] == 200, second['http_status'])
    check(results, 'turn2_get_order_selected', 'get_order' in tools2, tools2)
    check(results, 'turn2_delivered_seen', bool(re.search(r'delivered|已送达|已签收', answer2, re.IGNORECASE)), answer2[:200])
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    case = {'scenario': 'S3', 'turn1': first, 'turn2': second, 'state_before': before,
            'state_between': between, 'state_after': after, 'assertions': results,
            'verdict': verdict(results), 'ledger_before': ledger_before,
            'ledger_after': ledger_snapshot(), 'isolated_mutation': 'ORD-H11-ORDER shipped -> delivered'}
    save('case_s3.json', case)
    return case


def run_s4(client, idmap):
    results = []
    conv = 'h11-s4-customer1'
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    first = chat(client, idmap, 'customer1', '为订单 ORD-H11-APPROVAL 申请退款 600 元', conv)
    payload = first['api_response']
    tools = payload.get('tools_used') or []
    actions = payload.get('action_results') or []
    check(results, 'apply_http_200', first['http_status'] == 200, first['http_status'])
    check(results, 'request_refund_selected', 'request_refund' in tools, tools)
    check(results, 'action_receipt_present', bool(actions), len(actions))
    action_id = actions[0].get('action_id') if actions else None
    action = actions[0].get('action') if actions else {}
    check(results, 'apply_status_awaiting_approval', action.get('status') == 'awaiting_approval', action.get('status'))
    check(results, 'apply_amount_600', str(action.get('amount')) in {'600', '600.00', '600.0'}, action.get('amount'))

    if action_id:
        fetched = client.get('/actions/' + action_id, headers=headers(idmap, 'customer1'))
        fetched_body = fetched.json()
        check(results, 'pre_approval_execution_result_null',
              fetched.status_code == 200 and fetched_body.get('action', {}).get('execution_result') is None,
              fetched_body)
        pre = state(client, idmap)
        check(results, 'pre_approval_executor_calls_zero', pre.get('executor_calls') == 0, pre.get('executor_calls'))

        approved = client.post('/actions/' + action_id + '/approve', json={}, headers=headers(idmap, 'reviewer'))
        approved_body = approved.json()
        check(results, 'reviewer_approve_http_200', approved.status_code == 200, approved.status_code)
        check(results, 'approved_completed', approved_body.get('status') == 'completed', approved_body.get('status'))
        check(results, 'approved_execution_result', bool(approved_body.get('action', {}).get('execution_result')), approved_body.get('action', {}).get('execution_result'))
        mid = state(client, idmap)
        check(results, 'post_approval_executor_calls_one', mid.get('executor_calls') == 1, mid.get('executor_calls'))

        again = client.post('/actions/' + action_id + '/approve', json={}, headers=headers(idmap, 'reviewer'))
        again_body = again.json()
        again_state = state(client, idmap)
        check(results, 'repeat_approve_reused', again_body.get('reused') is True, again_body.get('reused'))
        check(results, 'repeat_approve_no_second_execution', again_state.get('executor_calls') == 1, again_state.get('executor_calls'))

    second = chat(client, idmap, 'customer1', '我的退款现在什么状态？', conv)
    payload2 = second['api_response']
    tools2 = payload2.get('tools_used') or []
    answer2 = payload2.get('response') or ''
    after = state(client, idmap)
    check(results, 'query_http_200', second['http_status'] == 200, second['http_status'])
    check(results, 'get_refund_status_selected', 'get_refund_status' in tools2, tools2)
    refunds = after.get('business', {}).get('refunds') or {}
    check(results, 'refund_record_pending', any((r or {}).get('status') == 'pending' for r in refunds.values()), refunds)
    check(results, 'order_refund_pending', after.get('business', {}).get('orders', {}).get('ORD-H11-APPROVAL', {}).get('status') == 'refund_pending',
          after.get('business', {}).get('orders', {}).get('ORD-H11-APPROVAL', {}).get('status'))
    check(results, 'answer_distinguishes_pending', bool(re.search(r'pending|待处理|待审核|未到账|不代表.{0,6}到账', answer2, re.IGNORECASE)), answer2[:250])
    case = {'scenario': 'S4', 'apply_turn': first, 'query_turn': second, 'action_id': action_id,
            'state_before': before, 'state_after': after, 'assertions': results,
            'verdict': verdict(results), 'ledger_before': ledger_before, 'ledger_after': ledger_snapshot()}
    save('case_s4.json', case)
    return case


def run_s5(client, idmap):
    results = []
    conv = 'h11-s5-customer1'
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    first = chat(client, idmap, 'customer1', '请帮我转人工客服', conv)
    payload = first['api_response']
    handoff = payload.get('handoff') or {}
    handoff_id = handoff.get('handoff_id')
    mid = state(client, idmap)
    check(results, 'turn1_http_200', first['http_status'] == 200, first['http_status'])
    check(results, 'handoff_created', handoff.get('handoff_created') is True, handoff)
    check(results, 'handoff_id_present', bool(handoff_id), handoff_id)
    check(results, 'handoff_record_count_one', len(mid.get('handoffs') or {}) == 1, len(mid.get('handoffs') or {}))

    if handoff_id:
        fetched = client.get('/handoffs/' + handoff_id, headers=headers(idmap, 'customer1'))
        fetched_body = fetched.json()
        check(results, 'owner_can_read_handoff', fetched.status_code == 200 and fetched_body.get('status') == 'created',
              fetched_body)

    second = chat(client, idmap, 'customer1', '刚才的交接现在有人接手了吗？', conv)
    payload2 = second['api_response']
    handoff2 = payload2.get('handoff') or {}
    answer2 = payload2.get('response') or ''
    after = state(client, idmap)
    check(results, 'turn2_http_200', second['http_status'] == 200, second['http_status'])
    check(results, 'no_duplicate_handoff', handoff2.get('handoff_created') is not True, handoff2)
    check(results, 'handoff_count_still_one', len(after.get('handoffs') or {}) == 1, len(after.get('handoffs') or {}))
    claimed = re.search(r'(?:真人|人工)(?:客服)?(?:已|已经)?(?:接单|接手|接听)', answer2)
    check(results, 'no_false_human_acceptance', claimed is None, claimed.group(0) if claimed else None)
    case = {'scenario': 'S5', 'turn1': first, 'turn2': second, 'handoff_id': handoff_id,
            'state_before': before, 'state_after': after, 'assertions': results,
            'verdict': verdict(results), 'ledger_before': ledger_before, 'ledger_after': ledger_snapshot()}
    save('case_s5.json', case)
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='S1B,S2,S4')
    args = parser.parse_args()
    selected = {x.strip().upper() for x in args.only.split(',') if x.strip()}
    idmap = identities()
    summary = {'run': RUN.name, 'scenarios': {}, 'model_ledger_before': ledger_snapshot()}
    with httpx.Client(base_url=BASE, trust_env=False, timeout=180) as client:
        health = wait_ready(client)
        save('health.json', health)
        preflight = run_preflight(client, idmap)
        summary['preflight'] = verdict(preflight)
        summary['preflight_assertions'] = preflight
        if summary['preflight'] != 'pass':
            summary['stopped'] = 'preflight failed'
            save('summary.json', summary)
            print(json.dumps(summary, ensure_ascii=False))
            return 1
        for name, func in [('S1B', run_s1b), ('S2', run_s2), ('S4', run_s4)]:
            if name not in selected:
                continue
            ledger = load_ledger()
            if ledger.get('halted') or ledger.get('requests', 0) >= 20:
                summary['scenarios'][name] = {'verdict': 'skipped', 'reason': 'model budget exhausted or halted'}
                continue
            case = func(client, idmap)
            summary['scenarios'][name] = {
                'verdict': case['verdict'],
                'assertions': case['assertions'],
                'model_requests': case['ledger_after']['requests'] - case['ledger_before']['requests'],
            }
            print(json.dumps({'scenario': name, 'verdict': case['verdict'],
                              'failed': [a['assertion'] for a in case['assertions'] if not a['pass']],
                              'model_requests': summary['scenarios'][name]['model_requests']},
                             ensure_ascii=False))
        summary['model_ledger_after'] = ledger_snapshot()
    save('summary.json', summary)
    print(json.dumps({'summary': {k: v['verdict'] for k, v in summary['scenarios'].items()},
                      'ledger': summary['model_ledger_after']}, ensure_ascii=False))
    return 0 if all(v['verdict'] == 'pass' for v in summary['scenarios'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
