"""H1-1 batch 2: re-verify adjusted S4 and cover eligibility, missing params, ownership."""
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
BASE = 'http://127.0.0.1:8018'
LEDGER = RUN / 'model_ledger.json'


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding='utf-8'))
    return {'requests': 0, 'charged_or_reserved_usd': 0.0, 'halted': False}


def ledger_snapshot():
    ledger = load_ledger()
    return {'requests': ledger.get('requests', 0),
            'charged_or_reserved_usd': ledger.get('charged_or_reserved_usd', 0.0),
            'halted': ledger.get('halted', False)}


def identities():
    return json.loads((PRIVATE / 'credentials.json').read_text(encoding='utf-8'))


def headers(idmap, who):
    return {'Authorization': 'Bearer ' + idmap[who]['token']}


def check(results, name, condition, detail=None):
    results.append({'assertion': name, 'pass': bool(condition), 'detail': detail})


def verdict(results):
    return 'pass' if results and all(item['pass'] for item in results) else 'fail'


def chat(client, idmap, who, message, conv_id):
    body = {'message': message, 'conv_id': conv_id}
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


def tool_names(case):
    trace = (case.get('trace') or {}).get('trace') or {}
    return [call.get('tool_name') for call in (trace.get('tool_calls') or [])]


def wait_ready(client):
    last = None
    for _ in range(60):
        try:
            response = client.get('/health')
            if response.status_code == 200:
                return response.json()
            last = response.status_code
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(1)
    raise RuntimeError(f'API not ready: {last}')


def no_new_writes(before, after):
    return (len(after.get('actions') or {}) == len(before.get('actions') or {})
            and len(after.get('handoffs') or {}) == len(before.get('handoffs') or {}))


def run_preflight(client, idmap):
    results = []
    for label, path, who, expected in [
        ('anonymous_trace', '/trace/tools', None, 401),
        ('customer_trace', '/trace/tools', 'customer1', 403),
        ('admin_trace', '/trace/tools', 'admin', 200),
    ]:
        response = client.get(path, headers=headers(idmap, who) if who else {})
        check(results, label, response.status_code == expected, response.status_code)
    response = client.post('/chat', json={'message': 'unauthorized probe'})
    check(results, 'anonymous_chat_401', response.status_code == 401, response.status_code)
    response = client.post('/chat', json={'message': 'identity probe', 'user_id': 'customer-2'},
                           headers=headers(idmap, 'customer1'))
    check(results, 'identity_mismatch_403', response.status_code == 403, response.status_code)
    save('http_preflight.json', {'assertions': results})
    return results


def run_b1(client, idmap):
    """Adjusted S4: eligibility checks must precede the explicit submission."""
    results = []
    conv = 'h11-b2-s4r-customer1'
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    first = chat(client, idmap, 'customer1', '为订单 ORD-H11-APPROVAL 申请退款 600 元', conv)
    payload = first['api_response']
    names = tool_names(first)
    actions = payload.get('action_results') or []
    action_id = actions[0].get('action_id') if actions else None
    action = actions[0].get('action') if actions else {}
    check(results, 'apply_http_200', first['http_status'] == 200, first['http_status'])
    check(results, 'get_order_before_submit', 'get_order' in names and 'request_refund' in names
          and names.index('get_order') < names.index('request_refund'), names)
    check(results, 'get_refund_status_before_submit', 'get_refund_status' in names and 'request_refund' in names
          and names.index('get_refund_status') < names.index('request_refund'), names)
    check(results, 'request_refund_selected', 'request_refund' in names, names)
    check(results, 'action_receipt_present', bool(actions), len(actions))
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
        mid = state(client, idmap)
        check(results, 'post_approval_executor_calls_one', mid.get('executor_calls') == 1, mid.get('executor_calls'))
        again = client.post('/actions/' + action_id + '/approve', json={}, headers=headers(idmap, 'reviewer'))
        again_state = state(client, idmap)
        check(results, 'repeat_approve_reused', again.json().get('reused') is True, again.json().get('reused'))
        check(results, 'repeat_approve_no_second_execution', again_state.get('executor_calls') == 1, again_state.get('executor_calls'))

    second = chat(client, idmap, 'customer1', '我的退款现在什么状态？', conv)
    payload2 = second['api_response']
    names2 = tool_names(second)
    answer2 = payload2.get('response') or ''
    after = state(client, idmap)
    refunds = after.get('business', {}).get('refunds') or {}
    check(results, 'query_http_200', second['http_status'] == 200, second['http_status'])
    check(results, 'get_refund_status_selected', 'get_refund_status' in names2, names2)
    check(results, 'refund_record_pending', any((r or {}).get('status') == 'pending' for r in refunds.values()), refunds)
    check(results, 'order_refund_pending', after.get('business', {}).get('orders', {}).get('ORD-H11-APPROVAL', {}).get('status') == 'refund_pending',
          after.get('business', {}).get('orders', {}).get('ORD-H11-APPROVAL', {}).get('status'))
    check(results, 'answer_distinguishes_pending', bool(re.search(r'pending|待处理|待审核|未到账|不代表.{0,6}到账', answer2, re.IGNORECASE)), answer2[:250])
    case = {'scenario': 'B1-S4R', 'apply_turn': first, 'query_turn': second, 'action_id': action_id,
            'state_before': before, 'state_after': after, 'assertions': results,
            'verdict': verdict(results), 'ledger_before': ledger_before, 'ledger_after': ledger_snapshot()}
    save('case_b1_s4r.json', case)
    return case


def run_b2(client, idmap):
    """Expired order: the Agent must judge ineligible and not submit."""
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer1', '为订单 ORD-H11-EXPIRED 申请退款 100 元', 'h11-b2-expired-customer1')
    after = state(client, idmap)
    payload = case['api_response']
    names = tool_names(case)
    answer = payload.get('response') or ''
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'get_order_selected', 'get_order' in names, names)
    check(results, 'request_refund_not_submitted', 'request_refund' not in names, names)
    check(results, 'no_action_created', not (payload.get('action_results') or []), payload.get('action_results'))
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    check(results, 'explains_ineligibility', bool(re.search(r'7|七天|过期|超过|不符合|无法|不能|不具备', answer)), answer[:250])
    case.update(scenario='B2-EXPIRED', assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_b2_expired.json', case)
    return case


def run_b3(client, idmap):
    """Missing order id: clarify, do not submit."""
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer1', '我要退款', 'h11-b2-missing-customer1')
    after = state(client, idmap)
    payload = case['api_response']
    names = tool_names(case)
    answer = payload.get('response') or ''
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'request_refund_not_submitted', 'request_refund' not in names, names)
    check(results, 'no_action_created', not (payload.get('action_results') or []), payload.get('action_results'))
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    check(results, 'asks_for_order_id', bool(re.search(r'订单号|订单编号|order\s*(?:id|number)', answer, re.IGNORECASE)), answer[:250])
    case.update(scenario='B3-MISSING', assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_b3_missing.json', case)
    return case


def run_b4(client, idmap):
    """Cross-owner query: customer-2 must not see customer-1 data."""
    results = []
    before = state(client, idmap)
    ledger_before = ledger_snapshot()
    case = chat(client, idmap, 'customer2', '帮我查订单 ORD-H11-ORDER', 'h11-b2-owner-customer2')
    after = state(client, idmap)
    payload = case['api_response']
    names = tool_names(case)
    answer = payload.get('response') or ''
    leaked = re.search(r'shipped|已发货|129\.90|SKU-H11|TRACK-ORD-H11-ORDER', answer, re.IGNORECASE)
    check(results, 'http_200', case['http_status'] == 200, case['http_status'])
    check(results, 'no_owner_data_leak', leaked is None, leaked.group(0) if leaked else None)
    check(results, 'no_business_write', no_new_writes(before, after), {'before': len(before.get('actions') or {}), 'after': len(after.get('actions') or {})})
    check(results, 'does_not_claim_found', not re.search(r'订单状态.{0,6}(?:已发货|shipped)', answer, re.IGNORECASE), answer[:250])
    case.update(scenario='B4-OWNERSHIP', tools=names, assertions=results, verdict=verdict(results),
                state_before=before, state_after=after, ledger_before=ledger_before, ledger_after=ledger_snapshot())
    save('case_b4_ownership.json', case)
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='B1,B2,B3,B4')
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
        for name, func in [('B1', run_b1), ('B2', run_b2), ('B3', run_b3), ('B4', run_b4)]:
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
