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
        CHECK (status IN ('active', 'gone')),
    topic_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_topic_id ON articles(topic_id);
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
        if "topic_id" not in cols:
            self._conn.execute("ALTER TABLE articles ADD COLUMN topic_id TEXT")

    def upsert(self, article: Article) -> bool:
        """Insert if URL is new. Returns True when inserted.

        Existing rows keep their content_snapshot, status, and topic_id (gone stays gone).
        """
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (url, title, published_at, summary, source, fetched_at,
                 content_snapshot, status, topic_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                article.topic_id,
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

    def get_articles_for_clustering(self) -> list[dict]:
        """Fetch all articles for clustering (active + gone with topic_id)."""
        rows = self._conn.execute(
            """
            SELECT url, title, published_at, source, status, topic_id
            FROM articles
            ORDER BY published_at DESC NULLS LAST, url
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def update_topic_ids(self, url_to_topic: dict[str, str]) -> int:
        """Batch update topic_ids for given URLs. Returns count of updated rows."""
        if not url_to_topic:
            return 0
        
        updated = 0
        for url, topic_id in url_to_topic.items():
            cur = self._conn.execute(
                "UPDATE articles SET topic_id = ? WHERE url = ?",
                (topic_id, url),
            )
            updated += cur.rowcount
        
        self._conn.commit()
        return updated

    def count_by_source(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT source, COUNT(*) AS n FROM articles GROUP BY source"
        ).fetchall()
        return {r["source"]: r["n"] for r in rows}

    def export_jsonl(self, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            "SELECT title, published_at, url, summary, source, fetched_at, "
            "content_snapshot, status, topic_id "
            "FROM articles ORDER BY fetched_at, url"
        ).fetchall()
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        return len(rows)

    def close(self) -> None:
        self._conn.close()
