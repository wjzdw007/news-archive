"""SQLite store with URL uniqueness and deletion-aware status."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .clustering import parse_iso_datetime
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

CREATE TABLE IF NOT EXISTS topic_briefs (
    topic_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    article_urls_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    error TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS daily_briefs (
    date TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'empty')),
    model TEXT NOT NULL DEFAULT '',
    lede TEXT NOT NULL DEFAULT '',
    sections_json TEXT NOT NULL,
    error TEXT,
    input_fingerprint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enrich_backoff (
    source TEXT PRIMARY KEY,
    until_utc TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
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
        # Indexes that depend on migrated columns (CREATE TABLE IF NOT EXISTS
        # skips altering old DBs, so these must run after ALTER).
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_topic_id ON articles(topic_id)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_briefs (
                date TEXT PRIMARY KEY,
                generated_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'empty')),
                model TEXT NOT NULL DEFAULT '',
                lede TEXT NOT NULL DEFAULT '',
                sections_json TEXT NOT NULL,
                error TEXT,
                input_fingerprint TEXT NOT NULL DEFAULT ''
            )
            """
        )
        daily_cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(daily_briefs)").fetchall()
        }
        if daily_cols and "input_fingerprint" not in daily_cols:
            self._conn.execute(
                "ALTER TABLE daily_briefs ADD COLUMN input_fingerprint "
                "TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS enrich_backoff (
                source TEXT PRIMARY KEY,
                until_utc TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def get_articles_for_enrich(self) -> list[dict]:
        """Private rows for archive-first snapshot enrich (includes content_snapshot)."""
        rows = self._conn.execute(
            """
            SELECT url, title, summary, content_snapshot, status, source
            FROM articles
            ORDER BY fetched_at DESC, url
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_articles_for_news_list(self) -> list[dict]:
        """Public list fields for News Tab display-window stats (no snapshots)."""
        rows = self._conn.execute(
            """
            SELECT url, title, published_at, summary, source, fetched_at, status
            FROM articles
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_enrich_backoff(self) -> dict[str, str]:
        """Persisted per-source enrich cooldown: source -> until_utc ISO string."""
        rows = self._conn.execute(
            "SELECT source, until_utc FROM enrich_backoff"
        ).fetchall()
        return {row["source"]: row["until_utc"] for row in rows}

    def upsert_enrich_backoff(self, source: str, until_utc: str) -> None:
        """Record a 6h (or caller-chosen) enrich cooldown for `source`."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO enrich_backoff (source, until_utc, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                until_utc = excluded.until_utc,
                updated_at = excluded.updated_at
            """,
            (source, until_utc, now),
        )
        self._conn.commit()

    def get_article(self, url: str) -> dict | None:
        """Single private row (includes content_snapshot). Tests / enrich only."""
        row = self._conn.execute(
            "SELECT * FROM articles WHERE url = ?", (url,)
        ).fetchone()
        return dict(row) if row else None

    def update_enrichment(
        self,
        url: str,
        *,
        content_snapshot: str | None = None,
        summary: str | None = None,
    ) -> bool:
        """Write private snapshot and/or derived public summary after page fetch.

        Only sets columns the caller passes; never changes status / topic_id.
        """
        assignments: list[str] = []
        values: list[object] = []
        if content_snapshot is not None:
            assignments.append("content_snapshot = ?")
            values.append(content_snapshot)
        if summary is not None:
            assignments.append("summary = ?")
            values.append(summary)
        if not assignments:
            return False
        values.append(url)
        cur = self._conn.execute(
            f"UPDATE articles SET {', '.join(assignments)} WHERE url = ?",
            values,
        )
        self._conn.commit()
        return cur.rowcount == 1

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

    def purge_both_empty_active(self) -> int:
        """One-shot heal: delete active rows missing both summary and snapshot.

        Idempotent: clean DBs delete 0. Does not fill summary from title.
        Leaves gone rows and any row that still has summary or snapshot.
        """
        cur = self._conn.execute(
            """
            DELETE FROM articles
            WHERE status = 'active'
              AND (summary IS NULL OR trim(summary) = '')
              AND (content_snapshot IS NULL OR trim(content_snapshot) = '')
            """
        )
        self._conn.commit()
        return cur.rowcount

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


    def count_active_without_topic(self) -> int:
        """Active rows that still need a topic_id (new inserts / prior overflow)."""
        row = self._conn.execute(
            """
            SELECT COUNT(*) FROM articles
            WHERE status = 'active'
              AND (topic_id IS NULL OR topic_id = '')
            """
        ).fetchone()
        return int(row[0]) if row else 0

    def clear_topic_ids_without_ok_brief(
        self,
        *,
        lookback_hours: float | None = None,
        max_clear: int | None = None,
        now: datetime | None = None,
    ) -> int:
        """Null topic_id on active rows whose topic has no ok brief (enable recluster).

        Preserves topic_ids that already have an ok topic_briefs row.
        When `lookback_hours` is set, only recent rows (published_at, else
        fetched_at) are cleared so Fetch does not O(n²) the whole archive.
        `max_clear` keeps the newest eligible rows (newest-first).
        Returns number of rows cleared.
        """
        if lookback_hours is None and max_clear is None:
            cur = self._conn.execute(
                """
                UPDATE articles
                SET topic_id = NULL
                WHERE status = 'active'
                  AND topic_id IS NOT NULL
                  AND topic_id NOT IN (
                      SELECT topic_id FROM topic_briefs WHERE status = 'ok'
                  )
                """
            )
            self._conn.commit()
            return cur.rowcount

        if max_clear is not None and max_clear <= 0:
            return 0

        rows = self._conn.execute(
            """
            SELECT url, published_at, fetched_at
            FROM articles
            WHERE status = 'active'
              AND topic_id IS NOT NULL
              AND topic_id NOT IN (
                  SELECT topic_id FROM topic_briefs WHERE status = 'ok'
              )
            """
        ).fetchall()
        clock = now if now is not None else datetime.now(timezone.utc)
        cutoff = None
        if lookback_hours is not None:
            cutoff = clock - timedelta(hours=lookback_hours)
        eligible: list[tuple[datetime, str]] = []
        for row in rows:
            dt = parse_iso_datetime(row["published_at"]) or parse_iso_datetime(
                row["fetched_at"]
            )
            if dt is None:
                continue
            if cutoff is not None and dt < cutoff:
                continue
            eligible.append((dt, row["url"]))
        eligible.sort(key=lambda item: item[0], reverse=True)
        if max_clear is not None:
            eligible = eligible[:max_clear]
        urls = [(url,) for _dt, url in eligible]
        if not urls:
            return 0
        cur = self._conn.executemany(
            "UPDATE articles SET topic_id = NULL WHERE url = ?",
            urls,
        )
        self._conn.commit()
        return cur.rowcount

    def update_topic_ids(self, url_to_topic: dict[str, str]) -> int:
        """Batch update topic_ids for given URLs. Returns count of updated rows."""
        if not url_to_topic:
            return 0

        cur = self._conn.executemany(
            "UPDATE articles SET topic_id = ? WHERE url = ?",
            [(topic_id, url) for url, topic_id in url_to_topic.items()],
        )
        self._conn.commit()
        return cur.rowcount


    def get_articles_for_briefs(self) -> list[dict]:
        """Active (+ context) articles with body fields for brief generation."""
        rows = self._conn.execute(
            """
            SELECT url, title, published_at, summary, source, status, topic_id,
                   content_snapshot
            FROM articles
            WHERE topic_id IS NOT NULL
            ORDER BY published_at ASC NULLS LAST, url
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_topic_briefs(self) -> dict[str, dict]:
        """Map topic_id -> brief dict with parsed JSON lists."""
        rows = self._conn.execute(
            "SELECT topic_id, title, sources_json, article_urls_json, "
            "generated_at, model, status, error, last_error FROM topic_briefs"
        ).fetchall()
        out: dict[str, dict] = {}
        for row in rows:
            d = dict(row)
            d["sources"] = json.loads(d.pop("sources_json") or "[]")
            d["article_urls"] = json.loads(d.pop("article_urls_json") or "[]")
            out[d["topic_id"]] = d
        return out

    def upsert_topic_brief(self, brief: dict) -> str:
        """Save brief. On failed, do not overwrite an existing ok brief.

        Returns: 'inserted' | 'updated' | 'kept_ok' | 'inserted_failed'
        """
        topic_id = brief["topic_id"]
        existing = self._conn.execute(
            "SELECT status FROM topic_briefs WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        sources_json = json.dumps(brief.get("sources") or [], ensure_ascii=False)
        urls_json = json.dumps(brief.get("article_urls") or [], ensure_ascii=False)
        status = brief.get("status") or "ok"
        error = brief.get("error")

        if existing and existing["status"] == "ok" and status == "failed":
            self._conn.execute(
                "UPDATE topic_briefs SET last_error = ? WHERE topic_id = ?",
                (error or "failed", topic_id),
            )
            self._conn.commit()
            return "kept_ok"

        if existing:
            self._conn.execute(
                """
                UPDATE topic_briefs SET
                    title = ?, sources_json = ?, article_urls_json = ?,
                    generated_at = ?, model = ?, status = ?, error = ?,
                    last_error = CASE WHEN ? = 'failed' THEN ? ELSE last_error END
                WHERE topic_id = ?
                """,
                (
                    brief["title"],
                    sources_json,
                    urls_json,
                    brief["generated_at"],
                    brief.get("model") or "rules-v2",
                    status,
                    error,
                    status,
                    error,
                    topic_id,
                ),
            )
            self._conn.commit()
            return "updated"

        self._conn.execute(
            """
            INSERT INTO topic_briefs
                (topic_id, title, sources_json, article_urls_json,
                 generated_at, model, status, error, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic_id,
                brief["title"],
                sources_json,
                urls_json,
                brief["generated_at"],
                brief.get("model") or "rules-v2",
                status,
                error,
                error if status == "failed" else None,
            ),
        )
        self._conn.commit()
        return "inserted_failed" if status == "failed" else "inserted"

    def get_articles_for_daily_brief(self) -> list[dict]:
        """Active articles for daily briefs. Never selects content_snapshot."""
        rows = self._conn.execute(
            """
            SELECT url, title, published_at, summary, source, fetched_at,
                   status, topic_id
            FROM articles
            WHERE status = 'active'
            ORDER BY published_at ASC NULLS LAST, fetched_at ASC, url
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_x_posts_for_daily_brief(self) -> list[dict]:
        """Active x_posts public fields for daily briefs.

        Allowlist only: author, text_snapshot, url, posted_at.
        Never selects post_id, cookies, Authorization, or other internals.
        Soft-empty if the x_posts table is missing (old data-branch sqlite).
        """
        try:
            rows = self._conn.execute(
                """
                SELECT author, text_snapshot, url, posted_at
                FROM x_posts
                WHERE status = 'active'
                ORDER BY posted_at ASC NULLS LAST, url
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            {
                "author": row["author"],
                "text_snapshot": row["text_snapshot"] or "",
                "url": row["url"],
                "posted_at": row["posted_at"],
            }
            for row in rows
        ]

    def get_daily_brief(self, date: str) -> dict | None:
        row = self._conn.execute(
            "SELECT date, generated_at, status, model, lede, sections_json, error, "
            "input_fingerprint FROM daily_briefs WHERE date = ?",
            (date,),
        ).fetchone()
        if row is None:
            return None
        return self._parse_daily_brief_row(row)

    def get_daily_briefs(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT date, generated_at, status, model, lede, sections_json, error, "
            "input_fingerprint FROM daily_briefs ORDER BY date DESC"
        ).fetchall()
        return [self._parse_daily_brief_row(row) for row in rows]

    @staticmethod
    def _parse_daily_brief_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["sections"] = json.loads(d.pop("sections_json") or "[]")
        return d

    def upsert_daily_brief(self, brief: dict) -> str:
        """Insert or replace one calendar-day brief.

        Never overwrite an existing ok row with failed/empty. A timeout or
        other error must not clobber a good day. Returns inserted|updated|kept_ok.
        """
        date = brief["date"]
        new_status = brief.get("status") or "failed"
        sections_json = json.dumps(brief.get("sections") or [], ensure_ascii=False)
        existing = self._conn.execute(
            "SELECT status FROM daily_briefs WHERE date = ?", (date,)
        ).fetchone()
        if existing and existing["status"] == "ok" and new_status != "ok":
            return "kept_ok"
        payload = (
            brief.get("generated_at") or "",
            brief.get("status") or "failed",
            brief.get("model") or "",
            brief.get("lede") or "",
            sections_json,
            brief.get("error"),
            brief.get("input_fingerprint") or "",
            date,
        )
        if existing:
            self._conn.execute(
                """
                UPDATE daily_briefs SET
                    generated_at = ?, status = ?, model = ?, lede = ?,
                    sections_json = ?, error = ?, input_fingerprint = ?
                WHERE date = ?
                """,
                payload,
            )
            self._conn.commit()
            return "updated"
        self._conn.execute(
            """
            INSERT INTO daily_briefs
                (generated_at, status, model, lede, sections_json, error,
                 input_fingerprint, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        self._conn.commit()
        return "inserted"

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
