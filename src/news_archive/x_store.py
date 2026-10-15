"""SQLite store for X post snapshots (post_id keyed)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Status = Literal["active", "gone"]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS x_posts (
    post_id TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    url TEXT,
    text_snapshot TEXT NOT NULL DEFAULT '',
    posted_at TEXT,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'gone')),
    topic_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_x_posts_author ON x_posts(author);
CREATE INDEX IF NOT EXISTS idx_x_posts_status ON x_posts(status);
CREATE INDEX IF NOT EXISTS idx_x_posts_posted_at ON x_posts(posted_at);
"""


@dataclass
class XPost:
    post_id: str
    author: str
    url: str | None
    text_snapshot: str
    posted_at: str | None
    fetched_at: str
    status: Status = "active"
    topic_id: str | None = None


class XStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def upsert(self, post: XPost) -> bool:
        """Insert if post_id is new. Returns True when inserted. Existing keep snapshot."""
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO x_posts
                (post_id, author, url, text_snapshot, posted_at, fetched_at, status, topic_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.post_id,
                post.author,
                post.url,
                post.text_snapshot,
                post.posted_at,
                post.fetched_at,
                post.status,
                post.topic_id,
            ),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def mark_gone(self, post_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE x_posts SET status = 'gone' WHERE post_id = ? AND status != 'gone'",
            (post_id,),
        )
        self._conn.commit()
        return cur.rowcount == 1


    def active_ids_for_author(self, author: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT post_id FROM x_posts WHERE author = ? AND status = 'active'",
            (author.lstrip("@"),),
        ).fetchall()
        return [r["post_id"] for r in rows]

    def count_by_author(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT author, COUNT(*) AS n FROM x_posts GROUP BY author"
        ).fetchall()
        return {r["author"]: r["n"] for r in rows}

    def get(self, post_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM x_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
