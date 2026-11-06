"""Print ephemeral loopback Demo Auth credentials for H5-3 recording."""
from __future__ import annotations

import argparse
import json
import secrets
import shlex


def credentials() -> tuple[dict, dict]:
    tokens = {name: secrets.token_urlsafe(32) for name in
              ("customer-1", "customer-2", "reviewer", "admin")}
    identities = {
        tokens["customer-1"]: {
            "subject_id": "demo-customer-1", "customer_id": "customer-1",
            "roles": ["customer"],
        },
        tokens["customer-2"]: {
            "subject_id": "demo-customer-2", "customer_id": "customer-2",
            "roles": ["customer"],
        },
        tokens["reviewer"]: {
            "subject_id": "demo-reviewer", "customer_id": None,
            "roles": ["reviewer"], "review_customers": ["customer-1"],
        },
        tokens["admin"]: {
            "subject_id": "demo-admin", "customer_id": None, "roles": ["admin"],
        },
    }
    return tokens, identities


def export_lines(tokens: dict, identities: dict, shell: str = "bash") -> list[str]:
    payload = json.dumps(identities, ensure_ascii=False)
    values = {"CARTCARE_DEMO_CREDENTIALS": payload,
              "CUSTOMER1_TOKEN": tokens["customer-1"],
              "CUSTOMER2_TOKEN": tokens["customer-2"],
              "REVIEWER_TOKEN": tokens["reviewer"],
              "ADMIN_TOKEN": tokens["admin"]}
    if shell == "powershell":
        return [f"$env:{name}='{value.replace(chr(39), chr(39) * 2)}'"
                for name, value in values.items()]
    return [f"export {name}={shlex.quote(value)}" for name, value in values.items()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", choices=("bash", "powershell"), default="bash")
    parser.add_argument("--powershell", action="store_true",
                        help="alias for --shell powershell")
    args = parser.parse_args()
    tokens, identities = credentials()
    shell = "powershell" if args.powershell else args.shell
    for line in export_lines(tokens, identities, shell):
        print(line)
    print("# Tokens are ephemeral; do not save or commit them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
