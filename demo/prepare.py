"""Generate a fresh, explicitly demo-only commerce fixture; no service mutation."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.prepare_online_eval import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/demo_business_fixture.json"))
    args = parser.parse_args()
    fixture, _ = prepare(datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Demo fixture: {args.output.resolve()}; restart API with CARTCARE_BUSINESS_FIXTURE pointing here")


if __name__ == "__main__":
    main()
