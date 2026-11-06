"""H5-3 preflight: fixture, local Demo Auth env, and HTTP entrypoints."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "data" / "eval" / "demo_h5_3_fixture.json"
REQUIRED_ORDERS = {"ORD-DEMO-REFUND", "ORD-DEMO-APPROVAL", "ORD-DEMO-OWNERSHIP"}


def fixture_errors(path: Path) -> list[str]:
    if not path.is_file():
        return [f"fixture missing: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"fixture unreadable: {exc}"]
    missing = REQUIRED_ORDERS - set((data.get("orders") or {}))
    return [f"fixture missing orders: {', '.join(sorted(missing))}"] if missing else []


def auth_env_errors() -> list[str]:
    errors: list[str] = []
    if os.getenv("CARTCARE_AUTH_MODE") != "demo":
        errors.append("CARTCARE_AUTH_MODE must be demo")
    if os.getenv("APP_ENV") != "development":
        errors.append("APP_ENV must be development")
    if os.getenv("API_HOST") not in {"127.0.0.1", "::1"}:
        errors.append("API_HOST must be 127.0.0.1 or ::1")
    if not os.getenv("CARTCARE_DEMO_CREDENTIALS"):
        errors.append("CARTCARE_DEMO_CREDENTIALS is not set")
    return errors


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, str(exc)


def http_errors(base_url: str) -> list[str]:
    errors: list[str] = []
    status, body = _get(base_url.rstrip("/") + "/health")
    if status != 200:
        errors.append(f"/health returned {status}")
    status, body = _get(base_url.rstrip("/") + "/ready")
    if status != 200:
        errors.append(f"/ready returned {status}: {body[:200]}")
    else:
        try:
            checks = json.loads(body).get("checks", {})
        except ValueError:
            checks = {}
        if not all(checks.get(name) for name in ("orchestrator", "redis", "chroma")):
            errors.append(f"/ready checks not all true: {checks}")
    status, body = _get(base_url.rstrip("/") + "/demo")
    if status != 200 or "CartCare" not in body:
        errors.append(f"/demo returned {status} without CartCare")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--skip-auth", action="store_true",
                        help="only for non-Demo deployments; H5-3 recording should not skip")
    args = parser.parse_args()

    errors = fixture_errors(args.fixture)
    if not args.skip_auth:
        errors.extend(auth_env_errors())
    errors.extend(http_errors(args.base_url))
    if errors:
        print("H5-3 preflight: FAIL")
        for error in errors:
            print(" -", error)
        return 1
    print("H5-3 preflight: PASS")
    print(f" - fixture: {args.fixture}")
    print(f" - base_url: {args.base_url}")
    print(" - /health, /ready, /demo: 200")
    if args.skip_auth:
        print(" - Demo Auth check skipped")
    else:
        print(" - Demo Auth env present; tokens are not printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
