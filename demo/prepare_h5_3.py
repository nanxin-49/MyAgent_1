"""Prepare a fresh H5-3 demo fixture and copy-paste scenario messages."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "providers" / "fixtures" / "business_provider_data.json"
DEFAULT_FIXTURE = ROOT / "data" / "eval" / "demo_h5_3_fixture.json"
DEFAULT_SCENARIOS = ROOT / "data" / "eval" / "demo_h5_3_scenarios.json"

ORDER_IDS = {
    "refund": "ORD-DEMO-REFUND",
    "approval": "ORD-DEMO-APPROVAL",
    "ownership": "ORD-DEMO-OWNERSHIP",
}

SCENARIOS = [
    {
        "id": "policy",
        "label": "1. Policy Q&A",
        "message": "退款政策是什么？",
        "user_id": "customer-1",
    },
    {
        "id": "composite",
        "label": "2. Composite + approval",
        "message": (
            "请现在为订单 ORD-DEMO-REFUND 提交 100 元退款；"
            "为订单 ORD-DEMO-APPROVAL 提交 800 元退款，需要审批就暂停等待审批。"
        ),
        "user_id": "customer-1",
    },
    {
        "id": "ownership",
        "label": "4. Ownership blocked",
        "message": "请尝试取消订单 ORD-DEMO-OWNERSHIP。",
        "user_id": "customer-2",
    },
]


def _order(base: dict, *, order_id: str, total: str, now: datetime, customer: str = "customer-1") -> dict:
    order = deepcopy(base)
    order.update({
        "order_id": order_id,
        "customer_id": customer,
        "status": "shipped",
        "total_amount": total,
        "currency": "CNY",
        "created_at": (now - timedelta(days=2)).isoformat(),
    })
    order["items"][0]["unit_price"] = total
    return order


def prepare(now: datetime) -> tuple[dict, list[dict]]:
    if now.tzinfo is None:
        raise ValueError("as-of time must include timezone")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    base = data["orders"]["ORD-1001"]
    data["orders"][ORDER_IDS["refund"]] = _order(
        base, order_id=ORDER_IDS["refund"], total="129.90", now=now)
    data["orders"][ORDER_IDS["approval"]] = _order(
        base, order_id=ORDER_IDS["approval"], total="800.00", now=now)
    data["orders"][ORDER_IDS["ownership"]] = _order(
        base, order_id=ORDER_IDS["ownership"], total="129.90", now=now)
    data["refunds"] = {}
    return data, deepcopy(SCENARIOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    args = parser.parse_args()
    fixture, scenarios = prepare(datetime.now(timezone.utc))
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.scenarios.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.scenarios.write_text(
        json.dumps(scenarios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fixture={args.fixture.resolve()}")
    print(f"scenarios={args.scenarios.resolve()}")
    print("Restart the API with CARTCARE_BUSINESS_FIXTURE pointing at the fixture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
