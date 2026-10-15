#!/usr/bin/env python3
"""Export SQLite archive to JSON for static site consumption.

Reads from archive.sqlite3 and generates:
- site/data/articles.json (sorted by published_at desc, fallback fetched_at)
- site/data/topics.json (only topics with status=ok briefs)
- site/data/x_posts.json (display fields only; no post_id / cookies / headers)

Soft failure: if DB missing, generates empty JSON files (Pages build won't fail).
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
from pathlib import Path

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

_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)


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


def export_articles(conn: sqlite3.Connection, output_path: Path) -> int:
    """Export articles sorted by published_at desc (fallback fetched_at).

    Omits content_snapshot (copyright / public-repo product lock).
    Strips HTML from summary so list/detail never show literal <p> tags.
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
        article["summary"] = strip_html(article.get("summary"))
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


def export_empty_files(site_data_dir: Path) -> None:
    """Generate empty JSON files when DB is missing."""
    site_data_dir.mkdir(parents=True, exist_ok=True)
    
    for filename in ["articles.json", "topics.json", "x_posts.json"]:
        filepath = site_data_dir / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump([], f)
    
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
        
        conn.close()
        
        print(f"✓ Exported {articles_count} articles")
        print(f"✓ Exported {topics_count} topics (status=ok only)")
        print(f"✓ Exported {x_posts_count} X posts")
        
        return 0
        
    except Exception as e:
        print(f"❌ Export failed: {e}", file=sys.stderr)
        # Still generate empty files to avoid breaking Pages build
        export_empty_files(site_data_dir)
        return 1


if __name__ == "__main__":
    sys.exit(main())
