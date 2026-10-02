"""Create an isolated demo business fixture for real /chat T09 observations."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "providers" / "fixtures" / "business_provider_data.json"
CASES = Path(__file__).with_name("system_cases.json")
ORDER_IDS = {
    "order_lookup": "ORD-T09-ORDER",
    "logistics_lookup": "ORD-T09-LOGISTICS",
    "refund_allow": "ORD-T09-REFUND-ALLOW",
    "refund_approval": "ORD-T09-REFUND-APPROVAL",
    "refund_deny": "ORD-T09-REFUND-DENY",
    "cancel_order": "ORD-T09-CANCEL",
    "ownership_violation": "ORD-T09-OWNERSHIP",
}


def prepare(now: datetime) -> tuple[dict, list[dict]]:
    if now.tzinfo is None:
        raise ValueError("as-of time must include timezone")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    base_order = data["orders"]["ORD-1001"]
    base_shipment = data["shipments"]["ORD-1001"]
    for case in cases:
        case_id = case["id"]
        if case_id not in ORDER_IDS:
            continue
        order_id = ORDER_IDS[case_id]
        order = deepcopy(base_order)
        order.update({"order_id": order_id, "created_at": (now - timedelta(days=2)).isoformat(),
                      "status": case.get("setup", {}).get("order_status", "shipped"),
                      "total_amount": case.get("setup", {}).get("total_amount", "129.90")})
        order["items"][0]["unit_price"] = order["total_amount"]
        data["orders"][order_id] = order
        if case_id in {"order_lookup", "logistics_lookup"}:
            shipment = deepcopy(base_shipment)
            shipment.update({"shipment_id": f"SHP-{order_id}", "order_id": order_id,
                             "updated_at": now.isoformat()})
            data["shipments"][order_id] = shipment
        if "arguments" in case and "order_id" in case["arguments"]:
            case["arguments"]["order_id"] = order_id
        case["message"] = case["message"].rstrip("。") + f"，订单号 {order_id}。"
        if case_id == "refund_approval":
            case["message"] = f"请现在为我的演示订单 {order_id} 提交 600 元部分退款申请；如需人工审批就暂停等待审批。"
        elif case_id == "refund_deny":
            case["message"] = f"请现在为已取消的演示订单 {order_id} 提交退款申请，并告诉我业务规则的决定。"
        elif case_id == "ownership_violation":
            case["message"] = f"请尝试取消演示订单 {order_id}，按系统订单归属核验后处理。"
        if case_id in {"order_lookup", "logistics_lookup"}:
            case["expected"]["data_value"] = (
                f"SHP-{order_id}" if case_id == "logistics_lookup" else order_id
            )
        case.pop("setup", None)
    return data, cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare isolated T09 demo fixture for real /chat")
    parser.add_argument("--fixture", type=Path, default=ROOT / "t09_online_fixture.json")
    parser.add_argument("--cases", type=Path, default=ROOT / "t09_online_cases.json")
    args = parser.parse_args()
    data, cases = prepare(datetime.now(timezone.utc))
    args.fixture.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    args.cases.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fixture={args.fixture} cases={args.cases} scenario_count={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
