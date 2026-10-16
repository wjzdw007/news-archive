"""X JSONL import acceptance (handoff from X早报)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from news_archive.x_import import import_jsonl
from news_archive.x_store import XStore


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


_WHITELIST_ACCOUNTS = [
    "BBCChinese",
    "Reuters",
    "FT",
    "TechCrunch",
    "Tesla",
    "elonmusk",
    "AP",
    "WSJ",
    "BBCWorld",
    "NPR",
    "nytimes",
    "TheEconomist",
    "SCMPNews",
]


def test_import_whitelist_accounts_nonempty_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "a.sqlite3"
        jl = Path(tmp) / "x.jsonl"
        rows = []
        for author in _WHITELIST_ACCOUNTS:
            rows.append(
                {
                    "post_id": f"id-{author}-1",
                    "author": author,
                    "url": f"https://x.com/{author}/status/1",
                    "text_snapshot": f"headline from {author} about markets",
                    "posted_at": "2026-10-15T01:00:00+00:00",
                }
            )
        _write_jsonl(jl, rows)
        store = XStore(db)
        stats = import_jsonl(store, jl)
        assert stats["inserted"] == 13
        for author in _WHITELIST_ACCOUNTS:
            row = store.get(f"id-{author}-1")
            assert row and row["text_snapshot"]
        store.close()
    print("✓ 1 whitelist accounts import")


def test_dedupe_same_post_id():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "a.sqlite3"
        jl = Path(tmp) / "x.jsonl"
        row = {
            "post_id": "dup-1",
            "author": "FT",
            "text_snapshot": "same post twice",
            "posted_at": "2026-10-15T01:00:00+00:00",
        }
        _write_jsonl(jl, [row, row])
        store = XStore(db)
        stats = import_jsonl(store, jl)
        assert stats["seen"] == 2
        assert stats["inserted"] == 1
        store.close()
    print("✓ 2 dedupe")


def test_mark_gone_keeps_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "a.sqlite3"
        store = XStore(db)
        jl1 = Path(tmp) / "1.jsonl"
        _write_jsonl(
            jl1,
            [
                {
                    "post_id": "old-1",
                    "author": "Reuters",
                    "text_snapshot": "old text stays",
                    "posted_at": "2026-10-14T01:00:00+00:00",
                }
            ],
        )
        import_jsonl(store, jl1)
        jl2 = Path(tmp) / "2.jsonl"
        _write_jsonl(
            jl2,
            [
                {
                    "post_id": "new-1",
                    "author": "Reuters",
                    "text_snapshot": "new post",
                    "posted_at": "2026-10-15T01:00:00+00:00",
                }
            ],
        )
        stats = import_jsonl(
            store, jl2, mark_missing_gone_for_authors=["Reuters"]
        )
        assert stats["gone"] == 1
        old = store.get("old-1")
        assert old["status"] == "gone"
        assert old["text_snapshot"] == "old text stays"
        store.close()
    print("✓ 3 gone keeps snapshot")


def test_import_failure_soft_cli():
    from news_archive.x_cli import main

    code = main(["--import-jsonl", "/no/such/file.jsonl", "--json"])
    assert code == 0  # soft-fail default
    print("✓ 4 import miss soft-fails")


if __name__ == "__main__":
    test_import_whitelist_accounts_nonempty_snapshot()
    test_dedupe_same_post_id()
    test_mark_gone_keeps_snapshot()
    test_import_failure_soft_cli()
    print("\n✅ All x_import tests PASSED")
