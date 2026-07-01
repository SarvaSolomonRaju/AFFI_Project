#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.auth import generate_api_key, hash_api_key


def main():
    parser = argparse.ArgumentParser(description="Manage AFFI API keys")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a new API key")
    gen.add_argument("--owner", required=True, help="Key owner (e.g., 'santa_cruz_oem')")
    gen.add_argument("--role", default="readonly", choices=["readonly", "operator", "admin"])

    sub.add_parser("list", help="List all active keys")

    rev = sub.add_parser("revoke", help="Revoke an API key by owner name")
    rev.add_argument("--owner", required=True)

    args = parser.parse_args()
    keys_file = ROOT / "config" / "api_keys.json"

    if keys_file.exists():
        data = json.loads(keys_file.read_text())
    else:
        data = {"keys": []}

    if args.command == "generate":
        result = generate_api_key(args.owner, args.role)
        data["keys"].append(result["record"])
        keys_file.write_text(json.dumps(data, indent=2))
        print(f"API key generated for: {args.owner}")
        print(f"Role: {args.role}")
        print(f"Key: {result['raw_key']}")
        print(f"Store this key securely — it cannot be retrieved later.")

    elif args.command == "list":
        for entry in data["keys"]:
            status = "ACTIVE" if entry.get("active") else "REVOKED"
            print(f"  [{status}] {entry['owner']} — role={entry.get('role', 'readonly')} — created={entry.get('created_utc', '?')}")

    elif args.command == "revoke":
        found = False
        for entry in data["keys"]:
            if entry["owner"] == args.owner:
                entry["active"] = False
                found = True
        if found:
            keys_file.write_text(json.dumps(data, indent=2))
            print(f"Revoked all keys for: {args.owner}")
        else:
            print(f"No keys found for: {args.owner}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
