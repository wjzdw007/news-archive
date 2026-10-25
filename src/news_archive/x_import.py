"""Import X posts from JSONL (handoff from X早报 public reads)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .x_config import x_fetch_accounts
from .x_store import XPost, XStore


def _canon_author(author: str) -> str:
    a = author.lstrip("@")
    lookup = {x.lower(): x for x in x_fetch_accounts()}
    return lookup.get(a.lower(), a)


REQUIRED = ("post_id", "author", "text_snapshot")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_jsonl_line(line: str, *, fetched_at: str | None = None) -> XPost | None:
    line = line.strip()
    if not line:
        return None
    raw: dict[str, Any] = json.loads(line)
    for key in REQUIRED:
        if not raw.get(key) and raw.get(key) != "":
            raise ValueError(f"missing {key}")
    if not str(raw.get("text_snapshot") or "").strip():
        raise ValueError("text_snapshot empty")
    author = _canon_author(str(raw["author"]))
    pid = str(raw["post_id"])
    status = raw.get("status") or "active"
    if status not in ("active", "gone"):
        status = "active"
    return XPost(
        post_id=pid,
        author=author,
        url=raw.get("url") or f"https://x.com/{author}/status/{pid}",
        text_snapshot=str(raw["text_snapshot"]),
        posted_at=raw.get("posted_at"),
        fetched_at=fetched_at or raw.get("fetched_at") or _iso_now(),
        status=status,  # type: ignore[arg-type]
        topic_id=raw.get("topic_id"),
    )


def iter_jsonl(path: Path) -> Iterable[XPost]:
    now = _iso_now()
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                post = parse_jsonl_line(line, fetched_at=now)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"line {i}: {exc}") from exc
            if post:
                yield post


def import_jsonl(
    store: XStore,
    path: Path,
    *,
    mark_missing_gone_for_authors: list[str] | None = None,
) -> dict[str, int]:
    """Upsert JSONL posts. Optionally mark active posts for authors as gone if absent."""
    posts = list(iter_jsonl(path))
    seen: set[str] = set()
    inserted = 0
    for p in posts:
        seen.add(p.post_id)
        if store.upsert(p):
            inserted += 1
    gone = 0
    if mark_missing_gone_for_authors:
        authors = {a.lstrip("@") for a in mark_missing_gone_for_authors}
        for author in authors:
            for row in store.active_ids_for_author(author):
                if row not in seen:
                    if store.mark_gone(row):
                        gone += 1
    return {"inserted": inserted, "seen": len(posts), "gone": gone}
