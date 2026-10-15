"""X fetch CLI — soft-fails by default (exit 0 with error JSON) so RSS stays green."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .x_config import X_NEWS_ACCOUNTS
from .x_fetch import XFetchError, fetch_account_posts, sync_posts
from .x_store import XStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch X posts into SQLite (news accounts)")
    parser.add_argument("--db", type=Path, default=Path("data/archive.sqlite3"))
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument(
        "--hard-fail",
        action="store_true",
        help="Exit non-zero on X failure (default: soft-fail, exit 0)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    store = XStore(args.db)
    result: dict = {"accounts": X_NEWS_ACCOUNTS, "mode": args.mode}
    try:
        posts = fetch_account_posts(mode=args.mode)
        stats = sync_posts(store, posts)
        result.update(stats)
        result["status"] = "ok"
    except XFetchError as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        store.close()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"X soft-fail: {exc}", file=sys.stderr)
        return 1 if args.hard_fail else 0
    store.close()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"x status={result['status']} inserted={result.get('inserted', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
