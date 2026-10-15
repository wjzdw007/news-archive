"""CLI: fetch → dedupe → store → optional JSONL export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fetch import fetch_all
from .sources import SOURCES
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch P0 news feeds into SQLite")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/archive.sqlite3"),
        help="SQLite path (default: data/archive.sqlite3)",
    )
    parser.add_argument(
        "--export-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL export path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print run stats as JSON",
    )
    args = parser.parse_args(argv)

    store = Store(args.db)
    results = fetch_all(SOURCES)

    stats: dict[str, object] = {"sources": {}, "inserted": 0, "seen": 0, "errors": {}}
    for source_id, payload in results.items():
        if isinstance(payload, Exception):
            stats["errors"][source_id] = str(payload)  # type: ignore[index]
            continue
        inserted = 0
        for article in payload:
            stats["seen"] = int(stats["seen"]) + 1
            if store.upsert(article):
                inserted += 1
        stats["sources"][source_id] = {  # type: ignore[index]
            "fetched": len(payload),
            "inserted": inserted,
        }
        stats["inserted"] = int(stats["inserted"]) + inserted

    export_count = None
    if args.export_jsonl:
        export_count = store.export_jsonl(args.export_jsonl)

    store.close()

    if args.json:
        out = {
            **stats,
            "by_source_total": Store(args.db).count_by_source(),
            "export_count": export_count,
        }
        Store(args.db).close()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"seen={stats['seen']} inserted={stats['inserted']}")
        for sid, detail in stats["sources"].items():  # type: ignore[union-attr]
            print(f"  {sid}: fetched={detail['fetched']} inserted={detail['inserted']}")
        for sid, err in stats["errors"].items():  # type: ignore[union-attr]
            print(f"  ERROR {sid}: {err}", file=sys.stderr)
        if export_count is not None:
            print(f"exported={export_count} -> {args.export_jsonl}")

    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
