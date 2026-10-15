"""SQLite store with URL uniqueness and deletion-aware status."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import Article

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    published_at TEXT,
    summary TEXT,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'gone'))
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
"""

# Migrate older DBs created before content_snapshot/status existed.
MIGRATE_SQL = """
ALTER TABLE articles ADD COLUMN content_snapshot TEXT;
ALTER TABLE articles ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        if "content_snapshot" not in cols:
            self._conn.execute("ALTER TABLE articles ADD COLUMN content_snapshot TEXT")
        if "status" not in cols:
            self._conn.execute(
                "ALTER TABLE articles ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )

    def upsert(self, article: Article) -> bool:
        """Insert if URL is new. Returns True when inserted.

        Existing rows keep their content_snapshot and status (gone stays gone).
        """
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (url, title, published_at, summary, source, fetched_at,
                 content_snapshot, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.url,
                article.title,
                article.published_at,
                article.summary,
                article.source,
                article.fetched_at,
                article.content_snapshot,
                article.status,
            ),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def mark_gone(self, url: str) -> bool:
        cur = self._conn.execute(
            "UPDATE articles SET status = 'gone' WHERE url = ? AND status != 'gone'",
            (url,),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def count_by_source(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT source, COUNT(*) AS n FROM articles GROUP BY source"
        ).fetchall()
        return {r["source"]: r["n"] for r in rows}

    def export_jsonl(self, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            "SELECT title, published_at, url, summary, source, fetched_at, "
            "content_snapshot, status "
            "FROM articles ORDER BY fetched_at, url"
        ).fetchall()
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        return len(rows)

    def close(self) -> None:
        self._conn.close()
