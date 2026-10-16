"""Fetch and normalize RSS entries."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Iterable

import feedparser
import httpx

from .schema import Article, title_as_summary
from .sources import Source

# Solidot (and some other feeds) 403 bare curl / empty-UA clients. A browser
# UA is sent for all RSS HTTP so live CI does not come back empty.
RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _to_iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, struct_time):
        return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, IndexError):
            return value.strip()
    return None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _content_snapshot(entry: dict) -> str | None:
    """Prefer content:encoded / content[].value, else summary."""
    content = entry.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = _clean_text(block.get("value"))
                if text:
                    return text
    for key in ("content_encoded", "content:encoded"):
        text = _clean_text(entry.get(key))
        if text:
            return text
    return _clean_text(entry.get("summary") or entry.get("description"))


def article_from_entry(
    entry: dict,
    source: Source,
    fetched_at: str,
) -> Article | None:
    """Normalize one RSS entry.

    Title + empty RSS description → public summary from trimmed title (≤280).
    No usable title and no body (summary/description/content:encoded) → skip.
    """
    url = _clean_text(entry.get("link") or entry.get("id"))
    title = _clean_text(entry.get("title"))
    summary = _clean_text(entry.get("summary") or entry.get("description"))
    snapshot = _content_snapshot(entry)
    if not url:
        return None
    if not title and not summary and not snapshot:
        return None
    if not title:
        return None
    if not summary:
        summary = title_as_summary(title)
    if not summary and not snapshot:
        return None
    published = _to_iso(
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("published")
        or entry.get("updated")
    )
    return Article(
        title=title,
        published_at=published,
        url=url,
        summary=summary,
        source=source.id,
        fetched_at=fetched_at,
        content_snapshot=snapshot,
        status="active",
    )


def fetch_source(source: Source, *, timeout: float = 30.0) -> list[Article]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=RSS_HEADERS) as client:
        resp = client.get(source.feed_url)
        resp.raise_for_status()
        raw = resp.content

    parsed = feedparser.parse(raw)
    articles: list[Article] = []
    for entry in parsed.entries:
        article = article_from_entry(entry, source, fetched_at)
        if article is not None:
            articles.append(article)
    return articles


def fetch_all(sources: Iterable[Source]) -> dict[str, list[Article] | Exception]:
    results: dict[str, list[Article] | Exception] = {}
    for source in sources:
        try:
            results[source.id] = fetch_source(source)
        except Exception as exc:  # noqa: BLE001 — per-source isolation
            results[source.id] = exc
    return results
