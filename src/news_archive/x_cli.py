"""X fetch/import CLI — soft-fails by default so RSS stays green."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .x_config import X_NEWS_ACCOUNTS
from .x_fetch import XFetchError, fetch_account_posts, sync_posts
from .x_import import import_jsonl
from .x_store import XStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch/import X posts into SQLite")
    parser.add_argument("--db", type=Path, default=Path("data/archive.sqlite3"))
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument(
        "--import-jsonl",
        type=Path,
        default=None,
        help="Import JSONL from X早报 (post_id/author/text_snapshot/...)",
    )
    parser.add_argument(
        "--mark-missing-gone",
        action="store_true",
        help="With --import-jsonl: mark active posts for configured authors gone if absent",
    )
    parser.add_argument(
        "--hard-fail",
        action="store_true",
        help="Exit non-zero on X failure (default: soft-fail, exit 0)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    store = XStore(args.db)
    result: dict = {"accounts": X_NEWS_ACCOUNTS}
    try:
        if args.import_jsonl:
            result["mode"] = "import-jsonl"
            authors = list(X_NEWS_ACCOUNTS) if args.mark_missing_gone else None
            stats = import_jsonl(
                store,
                args.import_jsonl,
                mark_missing_gone_for_authors=authors,
            )
            result.update(stats)
            result["by_author"] = store.count_by_author()
            result["status"] = "ok"
        else:
            result["mode"] = args.mode
            posts = fetch_account_posts(mode=args.mode)
            stats = sync_posts(store, posts)
            result.update(stats)
            result["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 — soft boundary
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
        print(
            f"x status={result['status']} inserted={result.get('inserted', 0)} "
            f"seen={result.get('seen', 0)} gone={result.get('gone', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
