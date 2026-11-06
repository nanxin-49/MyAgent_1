"""Deterministic gate checks for batch 2. No HTTP, no model calls.

Covers customer withdrawal, idempotency (same key / different params / cross-user),
and an expired-order policy denial. This is unit-level evidence and is reported
separately from the real HTTP /chat results.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[3]
sys.path.insert(0, str(ROOT))

from actions import ActionService, InMemoryBusinessActionBackend
from core.auth import Principal
from providers.mock_backend import InMemoryBusinessBackend

sys.stdout.reconfigure(encoding='utf-8')
FIXTURE = json.loads((RUN / 'fixture.json').read_text(encoding='utf-8'))


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def fresh_service():
    business = InMemoryBusinessBackend(json.loads(json.dumps(FIXTURE)))
    action_backend = InMemoryBusinessActionBackend(business.state)
    return ActionService(business_backend=business, action_backend=action_backend), action_backend


def check(results, name, condition, detail=None):
    results.append({'assertion': name, 'pass': bool(condition), 'detail': detail})


def main():
    customer1 = Principal('gate-customer-1', 'customer-1', frozenset({'customer'}))
    customer2 = Principal('gate-customer-2', 'customer-2', frozenset({'customer'}))
    results = []

    # 1. Customer can withdraw their own pending approval; no execution.
    service, backend = fresh_service()
    pending = service.request_refund(order_id='ORD-H11-APPROVAL', user_id='customer-1',
                                     request_id='gate-reject-1', amount=Decimal('600'), principal=customer1)
    check(results, 'withdraw_pending_created', pending.status.value == 'awaiting_approval', pending.status.value)
    rejected = service.reject(action_id=pending.action_id, user_id='customer-1',
                              request_id='gate-reject-2', principal=customer1)
    check(results, 'withdraw_rejected', rejected.status.value == 'rejected', rejected.status.value)
    check(results, 'withdraw_no_execution', len(backend.calls) == 0, len(backend.calls))

    # 2. Same key + same params reuse; different amount conflicts; cross-user does not reuse.
    service, backend = fresh_service()
    first = service.request_refund(order_id='ORD-H11-ORDER', user_id='customer-1',
                                   request_id='gate-idem-1', amount=Decimal('100'),
                                   idempotency_key='gate-key-1', principal=customer1)
    check(results, 'idem_first_completed', first.status.value == 'completed', first.status.value)
    check(results, 'idem_first_executed_once', len(backend.calls) == 1, len(backend.calls))
    second = service.request_refund(order_id='ORD-H11-ORDER', user_id='customer-1',
                                    request_id='gate-idem-2', amount=Decimal('100.00'),
                                    idempotency_key='gate-key-1', principal=customer1)
    check(results, 'idem_same_key_reused', second.reused is True and second.action_id == first.action_id,
          {'reused': second.reused, 'same_id': second.action_id == first.action_id})
    check(results, 'idem_no_second_execution', len(backend.calls) == 1, len(backend.calls))
    conflict = service.request_refund(order_id='ORD-H11-ORDER', user_id='customer-1',
                                      request_id='gate-idem-3', amount=Decimal('50'),
                                      idempotency_key='gate-key-1', principal=customer1)
    check(results, 'idem_different_amount_conflict',
          conflict.success is False and conflict.error_code == 'idempotency_conflict',
          {'success': conflict.success, 'error_code': conflict.error_code})
    cross = service.request_refund(order_id='ORD-H11-OTHER', user_id='customer-2',
                                   request_id='gate-idem-4', amount=Decimal('100'),
                                   idempotency_key='gate-key-1', principal=customer2)
    check(results, 'idem_cross_user_new_action',
          cross.action_id != first.action_id and cross.action is not None and cross.action.user_id == 'customer-2',
          {'new_id': cross.action_id != first.action_id,
           'user': cross.action.user_id if cross.action else None})
    check(results, 'idem_cross_user_executes_own_once', len(backend.calls) == 2, len(backend.calls))

    # 3. Expired order is denied by Policy; no execution.
    service, backend = fresh_service()
    denied = service.request_refund(order_id='ORD-H11-EXPIRED', user_id='customer-1',
                                    request_id='gate-expired-1', amount=Decimal('100'), principal=customer1)
    check(results, 'expired_denied', denied.success is False and denied.status.value == 'rejected',
          {'success': denied.success, 'status': denied.status.value})
    check(results, 'expired_reason', denied.error_code == 'refund_window_expired', denied.error_code)
    check(results, 'expired_no_execution', len(backend.calls) == 0, len(backend.calls))

    payload = {'layer': 'deterministic unit (no HTTP, no model)', 'assertions': results,
               'verdict': 'pass' if all(item['pass'] for item in results) else 'fail'}
    save('gate_checks.json', payload)
    print(json.dumps({'verdict': payload['verdict'],
                      'failed': [a['assertion'] for a in results if not a['pass']]}, ensure_ascii=False))
    return 0 if payload['verdict'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
