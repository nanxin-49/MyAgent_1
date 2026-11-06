"""Generate the versioned H3-6 composite after-sales case set.

The cases reuse the H2-3 fixture and expect 2-3 user demands per request. They
are evaluation-only: deterministic scripts exercise the harness, while the real
model runner uses the same `demands` labels for per-demand scoring.

Run: ``uv run python -m evaluation.h3_6.generate_cases``.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "cases.json"

FAQ_QUERY = "什么是退款申请的时间窗口？"
FAQ_RAG = {
    "document_id": "doc_8450205ee234ce108cbd",
    "title": "退款政策",
    "policy_version": "refund-cancel-v1",
    "source": "demo:cartcare-default/refund-policy",
    "reference": "doc_8450205ee234ce108cbd#chunk-0",
    "status": "usable",
    "content": "订单创建后 7×24 小时内提交",
}
C1 = {"subject_id": "h36-customer-1", "customer_id": "customer-1", "roles": ["customer"]}
C2 = {"subject_id": "h36-customer-2", "customer_id": "customer-2", "roles": ["customer"]}


def action(demand_id, tool, order_id, status, amount=None):
    demand = {"id": demand_id, "kind": "action", "tool": tool, "order_id": order_id,
              "expected_status": status}
    if amount is not None:
        demand["amount"] = amount
    return demand


def read(demand_id, tool, order_id):
    return {"id": demand_id, "kind": "read", "tool": tool, "order_id": order_id,
            "expected_status": "answered"}


def rag(demand_id, query=FAQ_QUERY):
    return {"id": demand_id, "kind": "rag", "tool": "search_knowledge_base",
            "query": query, "expected_status": "answered", "citation": FAQ_RAG["reference"],
            "rag": dict(FAQ_RAG)}


def handoff(demand_id, reason="complex_complaint"):
    return {"id": demand_id, "kind": "handoff", "tool": "request_handoff",
            "reason_code": reason, "expected_status": "completed"}


def refund(order_id, amount=None, key=None):
    data = {"order_id": order_id}
    if amount is not None:
        data["amount"] = amount
    if key:
        data["idempotency_key"] = key
    return ("request_refund", data)


def cancel(order_id, key=None):
    data = {"order_id": order_id}
    if key:
        data["idempotency_key"] = key
    return ("request_cancel_order", data)


def get_order(order_id):
    return ("get_order", {"order_id": order_id})


def get_refund_status(order_id):
    return ("get_refund_status", {"order_id": order_id})


def get_shipment(order_id):
    return ("get_shipment", {"order_id": order_id})


def search(query=FAQ_QUERY):
    return ("search_knowledge_base", {"query": query})


def request_handoff(reason="complex_complaint"):
    return ("request_handoff", {"reason_code": reason})


def calls(*items):
    return {"tool_calls": [{"name": name, "input": dict(data)} for name, data in items]}


def text(value):
    return {"text": value}


def script(*turns):
    return {"scripts": [list(turns)]}


def case(case_id, dimension, message, demands, turns, expected_completion,
         *, principal=C1, faults=None, forbidden=()):
    tools = []
    for demand in demands:
        if demand["tool"] not in tools:
            tools.append(demand["tool"])
    payload = {
        "id": case_id,
        "category": "composite",
        "message": message,
        "principal": principal,
        "source": {"dimension": dimension},
        "demands": demands,
        "expected_completion": expected_completion,
        "expected": {"tools": tools, "tool_mode": "partial",
                     "forbidden_tools": list(forbidden)},
        **script(*turns),
    }
    if faults:
        payload["faults"] = faults
    return payload


def build_cases():
    cases = []

    # Demo case first so the full arm records a complete chain even if the
    # ablation is interrupted. This is the H5-3 screen-recording candidate.
    cases.append(case(
        "composite_refund_cancel_faq",
        "three_demands",
        "我上周买的两件，耳机订单 ORD-H23-ALLOW-1 坏了要退款 100 元，"
        "充电器订单 ORD-H23-ALLOW-2 不要了帮我取消，顺便问下退款多久到账。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed"),
         rag("refund_window")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_refund_status("ORD-H23-ALLOW-1"),
               get_order("ORD-H23-ALLOW-2"), search()),
         calls(refund("ORD-H23-ALLOW-1", 100), cancel("ORD-H23-ALLOW-2")),
         text("退款已完成；订单取消已完成。退款申请需在订单创建后 7×24 小时内提交。")],
        "completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_cancel_allow",
        "two_independent_writes",
        "订单 ORD-H23-ALLOW-1 要退款 100 元，订单 ORD-H23-ALLOW-2 不要了，帮我取消。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_refund_status("ORD-H23-ALLOW-1"),
               get_order("ORD-H23-ALLOW-2")),
         calls(refund("ORD-H23-ALLOW-1", 100), cancel("ORD-H23-ALLOW-2")),
         text("退款已完成；订单取消已完成。")],
        "completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_allow_approval",
        "two_independent_writes",
        "订单 ORD-H23-ALLOW-1 退款 100 元；订单 ORD-H23-APPROVAL-1 退款 800 元。",
        [action("refund_small", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("refund_large", "request_refund", "ORD-H23-APPROVAL-1",
                "awaiting_approval", 800)],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-APPROVAL-1")),
         calls(refund("ORD-H23-ALLOW-1", 100), refund("ORD-H23-APPROVAL-1", 800)),
         text("100 元退款已完成；800 元退款已提交，等待审批，尚未执行。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_allow_deny",
        "two_independent_writes",
        "订单 ORD-H23-ALLOW-1 退款 100 元；订单 ORD-H23-EXPIRED 也退款 100 元。",
        [action("refund_small", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("refund_expired", "request_refund", "ORD-H23-EXPIRED", "rejected", 100)],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-EXPIRED")),
         calls(refund("ORD-H23-ALLOW-1", 100), refund("ORD-H23-EXPIRED", 100)),
         text("第一笔退款已完成；第二笔因超出退款窗口被拒绝，未执行。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_cancel_approval_refund_allow",
        "two_independent_writes",
        "取消订单 ORD-H23-PROCESSING；同时给订单 ORD-H23-ALLOW-1 退款 100 元。",
        [action("cancel", "request_cancel_order", "ORD-H23-PROCESSING", "awaiting_approval"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100)],
        [calls(get_order("ORD-H23-PROCESSING"), get_order("ORD-H23-ALLOW-1")),
         calls(cancel("ORD-H23-PROCESSING"), refund("ORD-H23-ALLOW-1", 100)),
         text("退款已完成；取消请求等待审批，尚未执行。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_approval_faq",
        "write_plus_faq",
        "订单 ORD-H23-APPROVAL-1 的耳机坏了，帮我退款 800 元；另外退款申请的时间窗口是什么？",
        [action("refund", "request_refund", "ORD-H23-APPROVAL-1",
                "awaiting_approval", 800),
         rag("refund_window")],
        [calls(get_order("ORD-H23-APPROVAL-1"), search()),
         calls(refund("ORD-H23-APPROVAL-1", 800)),
         text("退款请求已提交，等待审批，尚未执行。退款申请需在订单创建后 7×24 小时内提交。")],
        "partial_completed",
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_cancel_faq",
        "write_plus_faq",
        "取消订单 ORD-H23-ALLOW-2；顺便问一下退款申请的时间窗口。",
        [action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed"),
         rag("refund_window")],
        [calls(get_order("ORD-H23-ALLOW-2"), search()),
         calls(cancel("ORD-H23-ALLOW-2")),
         text("订单取消已完成。退款申请需在订单创建后 7×24 小时内提交。")],
        "completed",
        forbidden=("request_refund", "request_handoff"),
    ))

    cases.append(case(
        "composite_refund_logistics",
        "write_plus_read",
        "订单 ORD-H23-ALLOW-1 退款 100 元；再查一下它的物流。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         read("shipment", "get_shipment", "ORD-H23-ALLOW-1")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_shipment("ORD-H23-ALLOW-1")),
         calls(refund("ORD-H23-ALLOW-1", 100)),
         text("退款已完成；物流状态见查询结果。")],
        "completed",
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_three_refund_cancel_faq",
        "three_demands",
        "订单 ORD-H23-ALLOW-1 退款 100 元；取消 ORD-H23-PROCESSING；退款申请的时间窗口是什么？",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-PROCESSING", "awaiting_approval"),
         rag("refund_window")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-PROCESSING"), search()),
         calls(refund("ORD-H23-ALLOW-1", 100), cancel("ORD-H23-PROCESSING")),
         text("退款已完成；取消请求等待审批。退款申请需在订单创建后 7×24 小时内提交。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_two_refunds_order",
        "three_demands",
        "订单 ORD-H23-ALLOW-1 和 ORD-H23-DELIVERED 都退款 100 元；再看一下 ORD-H23-ALLOW-1 的订单状态。",
        [action("refund_a", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("refund_b", "request_refund", "ORD-H23-DELIVERED", "completed", 100),
         read("order", "get_order", "ORD-H23-ALLOW-1")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-DELIVERED"),
               get_refund_status("ORD-H23-ALLOW-1"), get_refund_status("ORD-H23-DELIVERED")),
         calls(refund("ORD-H23-ALLOW-1", 100), refund("ORD-H23-DELIVERED", 100)),
         text("两笔退款均已完成；订单状态见查询结果。")],
        "completed",
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_refund_deny_cancel_faq",
        "three_demands",
        "订单 ORD-H23-EXPIRED 退款 100 元；取消 ORD-H23-ALLOW-2；退款申请的时间窗口是什么？",
        [action("refund", "request_refund", "ORD-H23-EXPIRED", "rejected", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed"),
         rag("refund_window")],
        [calls(get_order("ORD-H23-EXPIRED"), get_order("ORD-H23-ALLOW-2"), search()),
         calls(refund("ORD-H23-EXPIRED", 100), cancel("ORD-H23-ALLOW-2")),
         text("退款因超出窗口被拒绝；订单取消已完成。退款申请需在订单创建后 7×24 小时内提交。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_approval_handoff_faq",
        "three_demands",
        "订单 ORD-H23-APPROVAL-1 的退款申请多次未处理，我要投诉；另外退款申请的时间窗口是什么？",
        [action("refund", "request_refund", "ORD-H23-APPROVAL-1",
                "awaiting_approval", 800),
         handoff("human_followup"),
         rag("refund_window")],
        [calls(get_order("ORD-H23-APPROVAL-1"), search()),
         calls(refund("ORD-H23-APPROVAL-1", 800), request_handoff()),
         text("退款请求等待审批；已申请人工跟进。退款申请需在订单创建后 7×24 小时内提交。")],
        "partial_completed",
        forbidden=("request_cancel_order",),
    ))

    cases.append(case(
        "composite_dependency_order_refund",
        "dependency",
        "先查订单 ORD-H23-ALLOW-1，再为它申请退款 100 元。",
        [read("order", "get_order", "ORD-H23-ALLOW-1"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100)],
        [calls(get_order("ORD-H23-ALLOW-1")),
         calls(get_refund_status("ORD-H23-ALLOW-1"), refund("ORD-H23-ALLOW-1", 100)),
         text("订单已查询，退款已完成。")],
        "completed",
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_dependency_refund_status",
        "dependency",
        "查一下 ORD-H23-REFUNDED 的退款进度；再申请 100 元退款；另外取消 ORD-H23-ALLOW-2。",
        [read("refund_status", "get_refund_status", "ORD-H23-REFUNDED"),
         action("refund", "request_refund", "ORD-H23-REFUNDED", "rejected", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed")],
        [calls(get_refund_status("ORD-H23-REFUNDED"), get_order("ORD-H23-ALLOW-2")),
         calls(refund("ORD-H23-REFUNDED", 100), cancel("ORD-H23-ALLOW-2")),
         text("退款已在处理中，重复申请未执行；订单取消已完成。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_dependency_order_cancel",
        "dependency",
        "先查订单 ORD-H23-PROCESSING 后帮我取消；另外给 ORD-H23-ALLOW-1 退款 100 元。",
        [read("order", "get_order", "ORD-H23-PROCESSING"),
         action("cancel", "request_cancel_order", "ORD-H23-PROCESSING", "awaiting_approval"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100)],
        [calls(get_order("ORD-H23-PROCESSING"), get_order("ORD-H23-ALLOW-1")),
         calls(cancel("ORD-H23-PROCESSING"), refund("ORD-H23-ALLOW-1", 100)),
         text("退款已完成；取消请求等待审批。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_ownership_read_and_refund",
        "ownership",
        "查一下我的订单 ORD-H23-OTHER-1；另外把 ORD-H23-ALLOW-1 退款 100 元。",
        [read("own_order", "get_order", "ORD-H23-OTHER-1"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "rejected", 100)],
        [calls(get_order("ORD-H23-OTHER-1"), get_order("ORD-H23-ALLOW-1")),
         calls(refund("ORD-H23-ALLOW-1", 100)),
         text("自己的订单可查询；另一订单未找到，不能提交退款。")],
        "partial_completed",
        principal=C2,
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_ownership_two_actions",
        "ownership",
        "给 ORD-H23-OTHER-1 退款 100 元，取消 ORD-H23-OTHER-2；再查一下 ORD-H23-ALLOW-1。",
        [action("refund", "request_refund", "ORD-H23-OTHER-1", "rejected", 100),
         action("cancel", "request_cancel_order", "ORD-H23-OTHER-2", "rejected"),
         read("own_order", "get_order", "ORD-H23-ALLOW-1")],
        [calls(get_order("ORD-H23-OTHER-1"), get_order("ORD-H23-OTHER-2"),
               get_order("ORD-H23-ALLOW-1")),
         calls(refund("ORD-H23-OTHER-1", 100), cancel("ORD-H23-OTHER-2")),
         text("两个越权动作均未找到可访问订单，未执行；自己的订单可查询。")],
        "partial_completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_ownership_cancel",
        "ownership",
        "查我的订单 ORD-H23-OTHER-1；取消 ORD-H23-ALLOW-2；再取消 ORD-H23-OTHER-2。",
        [read("own_order", "get_order", "ORD-H23-OTHER-1"),
         action("cancel_other", "request_cancel_order", "ORD-H23-ALLOW-2", "rejected"),
         action("cancel_own", "request_cancel_order", "ORD-H23-OTHER-2", "rejected")],
        [calls(get_order("ORD-H23-OTHER-1"), get_order("ORD-H23-ALLOW-2"),
               get_order("ORD-H23-OTHER-2")),
         calls(cancel("ORD-H23-ALLOW-2"), cancel("ORD-H23-OTHER-2")),
         text("自己的订单可查询；两个取消请求均被拒绝，未执行。")],
        "partial_completed",
        principal=C2,
        forbidden=("request_refund", "request_handoff"),
    ))

    cases.append(case(
        "composite_fault_read_retry",
        "fault_recovery",
        "为 ORD-H23-ALLOW-1 退款 100 元，并取消 ORD-H23-ALLOW-2。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-ALLOW-2")),
         calls(get_order("ORD-H23-ALLOW-1"), refund("ORD-H23-ALLOW-1", 100),
               cancel("ORD-H23-ALLOW-2")),
         text("查询重试成功；退款与取消均已完成。")],
        "completed",
        faults=[{"tool": "get_order", "kind": "dependency_failure",
                 "on_call": 1, "mode": "once"}],
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_fault_rag_retry",
        "fault_recovery",
        "退款申请的时间窗口是什么？另外为 ORD-H23-ALLOW-1 退款 100 元。",
        [rag("refund_window"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100)],
        [calls(search()),
         calls(search(), get_order("ORD-H23-ALLOW-1"), refund("ORD-H23-ALLOW-1", 100)),
         text("检索重试成功；退款已完成。退款申请需在订单创建后 7×24 小时内提交。")],
        "completed",
        faults=[{"tool": "search_knowledge_base", "kind": "timeout",
                 "on_call": 1, "mode": "once"}],
        forbidden=("request_cancel_order", "request_handoff"),
    ))

    cases.append(case(
        "composite_fault_write_failure",
        "fault_recovery",
        "为 ORD-H23-ALLOW-1 退款 100 元，并取消 ORD-H23-ALLOW-2。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "failed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-ALLOW-2")),
         calls(refund("ORD-H23-ALLOW-1", 100), cancel("ORD-H23-ALLOW-2")),
         text("退款处理失败，未执行；订单取消已完成。")],
        "partial_completed",
        faults=[{"tool": "request_refund", "kind": "execution_failure",
                 "on_call": 1, "mode": "sticky"}],
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_duplicate_refund",
        "duplicate_inducement",
        "为 ORD-H23-ALLOW-1 退款 100 元，再确认一次同一笔退款；并取消 ORD-H23-ALLOW-2。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed")],
        [calls(get_order("ORD-H23-ALLOW-1"), get_order("ORD-H23-ALLOW-2")),
         calls(refund("ORD-H23-ALLOW-1", 100, key="h36-dup-refund"),
               refund("ORD-H23-ALLOW-1", 100, key="h36-dup-refund"),
               cancel("ORD-H23-ALLOW-2")),
         text("退款请求已复用，未重复执行；订单取消已完成。")],
        "completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_duplicate_cancel",
        "duplicate_inducement",
        "取消 ORD-H23-ALLOW-2，再确认一次同一笔取消；并为 ORD-H23-ALLOW-1 退款 100 元。",
        [action("cancel", "request_cancel_order", "ORD-H23-ALLOW-2", "completed"),
         action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100)],
        [calls(get_order("ORD-H23-ALLOW-2"), get_order("ORD-H23-ALLOW-1")),
         calls(cancel("ORD-H23-ALLOW-2", key="h36-dup-cancel"),
               cancel("ORD-H23-ALLOW-2", key="h36-dup-cancel"),
               refund("ORD-H23-ALLOW-1", 100)),
         text("取消请求已复用，未重复执行；退款已完成。")],
        "completed",
        forbidden=("request_handoff",),
    ))

    cases.append(case(
        "composite_refund_handoff",
        "partial_success_handoff",
        "订单 ORD-H23-ALLOW-1 的退款申请多次未处理，我要投诉，希望有专人跟进。",
        [action("refund", "request_refund", "ORD-H23-ALLOW-1", "completed", 100),
         handoff("human_followup")],
        [calls(get_order("ORD-H23-ALLOW-1")),
         calls(refund("ORD-H23-ALLOW-1", 100), request_handoff()),
         text("退款已完成；已申请人工跟进。")],
        "completed",
        forbidden=("request_cancel_order",),
    ))

    return cases


def main() -> int:
    cases = build_cases()
    identifiers = [item["id"] for item in cases]
    assert len(cases) == 24, len(cases)
    assert len(set(identifiers)) == len(cases)
    assert all(2 <= len(item["demands"]) <= 3 for item in cases)
    assert all(item["category"] == "composite" for item in cases)
    payload = {
        "schema": "echomind.h3_6.composite_cases",
        "version": 1,
        "description": "H3-6 composite after-sales requests; reuses the H2-3 fixture.",
        "cases": cases,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {len(cases)} composite cases to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
