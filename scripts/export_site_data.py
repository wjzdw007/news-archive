#!/usr/bin/env python3
"""Export SQLite archive to JSON for static site consumption.

Reads from archive.sqlite3 and generates:
- site/data/articles.json (sorted by published_at desc, fallback fetched_at)
- site/data/topics.json (only topics with status=ok briefs; 科技/AI card prepended)
- site/data/x_posts.json (display fields only; no post_id / cookies / headers)
- site/data/daily_briefs.json (one row per Shanghai day; no content_snapshot)
- site/data/tech_ai.json (科技/AI curated RSS∪X feed; no content_snapshot / post_id)

Soft failure: if DB missing, generates empty JSON files (Pages build won't fail).
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from news_archive.tech_ai import (  # noqa: E402
    build_tech_ai_page,
    empty_tech_ai_payload,
    tech_ai_topic_card,
)

# Public Pages must never ship RSS full-text snapshots.
_ARTICLE_EXPORT_FIELDS = (
    "url",
    "title",
    "published_at",
    "summary",
    "source",
    "fetched_at",
    "status",
    "topic_id",
)

# Public X tab: display fields only. Never cookies / Authorization / headers / post_id.
_X_POST_EXPORT_FIELDS = (
    "author",
    "posted_at",
    "fetched_at",
    "text_snapshot",
    "url",
    "status",
)

# Public 日报 tab. Never content_snapshot; omit internal error strings.
_DAILY_BRIEF_EXPORT_FIELDS = (
    "date",
    "generated_at",
    "status",
    "model",
    "lede",
    "sections",
)

_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
# Public Pages summary cap (Unicode chars). Full text stays in private DB.
PUBLIC_SUMMARY_MAX = 280


def article_list_time(article: dict) -> str:
    """News list SORT and displayed time: published_at, else fetched_at.

    Missing / null / empty published_at falls back to fetched_at so a
    late-fetched old article does not jump to the top of the public list.
    """
    published = article.get("published_at")
    if isinstance(published, str) and published.strip():
        return published.strip()
    fetched = article.get("fetched_at")
    if isinstance(fetched, str):
        return fetched.strip()
    return fetched or ""


def strip_html(text: str | None) -> str | None:
    """Unescape entities and strip tags for list/detail summary text."""
    if text is None:
        return None
    unescaped = html.unescape(str(text))
    stripped = _TAG_RE.sub(" ", unescaped)
    cleaned = re.sub(r"\s+", " ", stripped).strip()
    return cleaned or None


def cap_public_summary(text: str | None) -> str | None:
    """Plain-text public summary, never longer than 280 Unicode chars."""
    cleaned = strip_html(text)
    if cleaned is None:
        return None
    if len(cleaned) > PUBLIC_SUMMARY_MAX:
        return cleaned[:PUBLIC_SUMMARY_MAX]
    return cleaned


def export_articles(conn: sqlite3.Connection, output_path: Path) -> int:
    """Export articles sorted by published_at desc (fallback fetched_at).

    Omits content_snapshot (copyright / public-repo product lock).
    Strips HTML from summary and caps at 280 chars so Pages never shows
    full article text (even when the private snapshot is long).
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT url, title, published_at, summary, source, fetched_at,
               status, topic_id
        FROM articles
        """
    )
    articles = []
    for row in cursor.fetchall():
        article = {field: row[field] for field in _ARTICLE_EXPORT_FIELDS}
        article["summary"] = cap_public_summary(article.get("summary"))
        articles.append(article)

    articles.sort(key=article_list_time, reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return len(articles)


def export_topics(conn: sqlite3.Connection, output_path: Path) -> int:
    """Export only topics with status=ok briefs."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT topic_id, title, sources_json, article_urls_json,
               generated_at, model, status
        FROM topic_briefs
        WHERE status = 'ok'
        ORDER BY generated_at DESC
        """
    )
    
    topics = []
    for row in cursor.fetchall():
        topic = dict(row)
        # Parse JSON fields
        topic["sources"] = json.loads(topic.pop("sources_json", "[]"))
        topic["article_urls"] = json.loads(topic.pop("article_urls_json", "[]"))
        topics.append(topic)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
    
    return len(topics)


def export_x_posts(conn: sqlite3.Connection, output_path: Path) -> int:
    """Export X posts sorted by posted_at desc.

    Allowlist only: author / posted_at / fetched_at / text_snapshot / url / status.
    Never cookies, Authorization, headers, or post_id.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT author, posted_at, fetched_at, text_snapshot, url, status
        FROM x_posts
        ORDER BY posted_at DESC NULLS LAST, fetched_at DESC
        """
    )
    posts = []
    for row in cursor.fetchall():
        posts.append({field: row[field] for field in _X_POST_EXPORT_FIELDS})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    return len(posts)


def export_daily_briefs(conn: sqlite3.Connection, output_path: Path) -> int:
    """Export daily_briefs for the 日报 tab (ok/failed/empty).

    Soft-fail if the table is missing (old data-branch sqlite).
    Never includes content_snapshot or internal error fields.
    """
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT date, generated_at, status, model, lede, sections_json
            FROM daily_briefs
            ORDER BY date DESC
            """
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    briefs = []
    for row in rows:
        brief = {field: row[field] for field in _DAILY_BRIEF_EXPORT_FIELDS if field != "sections"}
        brief["sections"] = json.loads(row["sections_json"] or "[]")
        briefs.append(brief)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(briefs, f, ensure_ascii=False, indent=2)

    return len(briefs)


def _load_export_articles(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT url, title, published_at, summary, source, fetched_at,
                   status, topic_id
            FROM articles
            """
        )
    except sqlite3.OperationalError:
        return []
    articles = []
    for row in cursor.fetchall():
        article = {field: row[field] for field in _ARTICLE_EXPORT_FIELDS}
        article["summary"] = cap_public_summary(article.get("summary"))
        articles.append(article)
    return articles


def _load_export_x_posts(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT author, posted_at, fetched_at, text_snapshot, url, status
            FROM x_posts
            """
        )
    except sqlite3.OperationalError:
        return []
    return [{field: row[field] for field in _X_POST_EXPORT_FIELDS} for row in cursor.fetchall()]


def export_tech_ai(conn: sqlite3.Connection, output_path: Path) -> dict:
    """Export the curated 科技/AI feed. Never content_snapshot / post_id."""
    payload = build_tech_ai_page(
        _load_export_articles(conn),
        _load_export_x_posts(conn),
    )
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    for forbidden in ("content_snapshot", "post_id"):
        if forbidden in raw:
            raise AssertionError(f"tech_ai.json must not include {forbidden}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(raw, encoding="utf-8")
    return payload


def prepend_tech_ai_topic(topics_path: Path, payload: dict) -> None:
    """Keep 科技/AI first in topics.json so 专题 is never an empty dead end."""
    if topics_path.exists():
        topics = json.loads(topics_path.read_text(encoding="utf-8"))
        if not isinstance(topics, list):
            topics = []
    else:
        topics = []
    card = tech_ai_topic_card(payload)
    topics = [t for t in topics if t.get("topic_id") != card["topic_id"]]
    topics.insert(0, card)
    topics_path.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_empty_files(site_data_dir: Path) -> None:
    """Generate empty JSON files when DB is missing."""
    site_data_dir.mkdir(parents=True, exist_ok=True)
    
    for filename in ["articles.json", "topics.json", "x_posts.json", "daily_briefs.json"]:
        filepath = site_data_dir / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump([], f)

    payload = empty_tech_ai_payload()
    (site_data_dir / "tech_ai.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    prepend_tech_ai_topic(site_data_dir / "topics.json", payload)
    
    print("⚠ No database found - generated empty JSON files (first run OK)")


def main() -> int:
    db_path = Path("data/archive.sqlite3")
    site_data_dir = Path("site/data")
    
    # Soft failure: if DB missing, export empty files
    if not db_path.exists():
        export_empty_files(site_data_dir)
        return 0
    
    try:
        conn = sqlite3.connect(db_path)
        
        articles_count = export_articles(conn, site_data_dir / "articles.json")
        topics_count = export_topics(conn, site_data_dir / "topics.json")
        x_posts_count = export_x_posts(conn, site_data_dir / "x_posts.json")
        daily_briefs_count = export_daily_briefs(conn, site_data_dir / "daily_briefs.json")
        tech_ai_payload = export_tech_ai(conn, site_data_dir / "tech_ai.json")
        prepend_tech_ai_topic(site_data_dir / "topics.json", tech_ai_payload)
        topics_count = topics_count + 1
        
        conn.close()
        
        print(f"✓ Exported {articles_count} articles")
        print(f"✓ Exported {topics_count} topics (status=ok + 科技/AI)")
        print(f"✓ Exported {x_posts_count} X posts")
        print(f"✓ Exported {daily_briefs_count} daily briefs")
        print(
            f"✓ Exported 科技/AI "
            f"(rss={tech_ai_payload.get('rss_count', 0)} "
            f"x={tech_ai_payload.get('x_count', 0)})"
        )
        
        return 0
        
    except Exception as e:
        print(f"❌ Export failed: {e}", file=sys.stderr)
        # Still generate empty files to avoid breaking Pages build
        export_empty_files(site_data_dir)
        return 1


if __name__ == "__main__":
    sys.exit(main())
