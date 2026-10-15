"""CLI tool to mark URLs as gone in the persisted archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mark one or more URLs as gone (status='gone') in the archive"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/archive.sqlite3"),
        help="SQLite path (default: data/archive.sqlite3)",
    )
    parser.add_argument(
        "--url",
        type=str,
        action="append",
        dest="urls",
        required=True,
        help="URL to mark as gone (can be specified multiple times)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be marked without actually updating",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"❌ Database not found: {args.db}", file=sys.stderr)
        return 1

    store = Store(args.db)
    
    marked_count = 0
    not_found_count = 0
    already_gone_count = 0
    
    for url in args.urls:
        if args.dry_run:
            # Check if URL exists
            row = store._conn.execute(
                "SELECT status FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if row is None:
                print(f"  {url} → NOT FOUND")
                not_found_count += 1
            elif row["status"] == "gone":
                print(f"  {url} → ALREADY GONE")
                already_gone_count += 1
            else:
                print(f"  {url} → WOULD MARK AS GONE")
                marked_count += 1
        else:
            # Actually mark as gone
            if store.mark_gone(url):
                print(f"✓ {url} → marked as gone")
                marked_count += 1
            else:
                # Check why it wasn't marked
                row = store._conn.execute(
                    "SELECT status FROM articles WHERE url = ?", (url,)
                ).fetchone()
                if row is None:
                    print(f"⚠ {url} → not found in database")
                    not_found_count += 1
                elif row["status"] == "gone":
                    print(f"  {url} → already gone")
                    already_gone_count += 1
    
    store.close()
    
    print()
    if args.dry_run:
        print(f"DRY RUN: would mark {marked_count} URL(s) as gone")
    else:
        print(f"Marked {marked_count} URL(s) as gone")
    
    if already_gone_count > 0:
        print(f"Already gone: {already_gone_count}")
    if not_found_count > 0:
        print(f"Not found: {not_found_count}")
    
    return 0 if not_found_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
