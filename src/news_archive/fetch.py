"""Fetch and normalize RSS entries."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Callable, Iterable

import feedparser
import httpx

from .schema import Article
from .sources import Source

# One RSS timeout must not drop the whole daily archive write. Retry the same
# source twice more (3 attempts total), then let fetch_all isolate the failure.
RSS_FETCH_ATTEMPTS = 3
RSS_RETRY_BACKOFF_S = 1.0
# Per-source HTTP budget. 87 sequential 30s×3 attempts can consume a 30m GHA
# job before Persist; keep retries (#53) but cap each attempt and overlap GETs.
RSS_TIMEOUT_S = 15.0
RSS_FETCH_WORKERS = 8
# Wall clock for the RSS wave only (enrich still runs after). Remaining
# sources soft-fail so Persist still sees the feeds that finished.
RSS_FETCH_DEADLINE_S = 600.0
# Dense feeds (Electrek / 36kr-style) can dump 50–100 items in one RSS body.
# Keep newest-first feed order; do not change the source registry.
INGEST_CAP_PER_SOURCE = 30

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

    Thin items (title but no description/summary/content:encoded body) are
    skipped — do not fill summary from title. True both-empty is also skipped.
    """
    url = _clean_text(entry.get("link") or entry.get("id"))
    title = _clean_text(entry.get("title"))
    summary = _clean_text(entry.get("summary") or entry.get("description"))
    snapshot = _content_snapshot(entry)
    if not url:
        return None
    if not title:
        return None
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


def _get_feed_bytes(
    source: Source,
    *,
    timeout: float,
    sleep_fn: Callable[[float], None] | None = None,
) -> bytes:
    """GET the RSS body, retrying transient HTTP timeouts.

    Retries httpx.TimeoutException (ReadTimeout / ConnectTimeout / "The read
    operation timed out" and similar). HTTP 4xx/5xx and other errors are not
    retried here; fetch_all still isolates them per source.
    """
    sleeper = time.sleep if sleep_fn is None else sleep_fn
    last_exc: httpx.TimeoutException | None = None
    for attempt in range(1, RSS_FETCH_ATTEMPTS + 1):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers=RSS_HEADERS,
            ) as client:
                resp = client.get(source.feed_url)
                resp.raise_for_status()
                return resp.content
        except httpx.TimeoutException as exc:
            last_exc = exc
            print(
                f"WARN {source.id}: RSS timeout attempt {attempt}/{RSS_FETCH_ATTEMPTS}: {exc}",
                file=sys.stderr,
            )
            if attempt < RSS_FETCH_ATTEMPTS:
                sleeper(RSS_RETRY_BACKOFF_S * attempt)
                continue
            raise
    assert last_exc is not None  # pragma: no cover — loop always returns or raises
    raise last_exc


def fetch_source(
    source: Source,
    *,
    timeout: float = RSS_TIMEOUT_S,
    sleep_fn: Callable[[float], None] | None = None,
    ingest_cap: int = INGEST_CAP_PER_SOURCE,
) -> list[Article]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    raw = _get_feed_bytes(source, timeout=timeout, sleep_fn=sleep_fn)

    parsed = feedparser.parse(raw)
    articles: list[Article] = []
    for entry in parsed.entries:
        article = article_from_entry(entry, source, fetched_at)
        if article is not None:
            articles.append(article)
    if ingest_cap > 0 and len(articles) > ingest_cap:
        print(
            f"INFO {source.id}: ingest cap {ingest_cap}/{len(articles)} "
            "(dense-source spike; newest-first feed order)",
            file=sys.stderr,
        )
        articles = articles[:ingest_cap]
    return articles


class RssFetchDeadlineExceeded(TimeoutError):
    """Remaining RSS sources skipped because the fetch wave hit its wall clock."""


def fetch_all(
    sources: Iterable[Source],
    *,
    timeout: float = RSS_TIMEOUT_S,
    max_workers: int = RSS_FETCH_WORKERS,
    deadline_s: float | None = RSS_FETCH_DEADLINE_S,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, list[Article] | Exception]:
    """Fetch every source with per-source isolation.

    Overlaps HTTP across `max_workers` threads. If `deadline_s` elapses,
    sources that have not started yet are recorded as RssFetchDeadlineExceeded
    (soft-fail, same as a per-source timeout) so finished feeds still persist.
    """
    source_list = list(sources)
    results: dict[str, list[Article] | Exception] = {}
    if not source_list:
        return results

    deadline_at: float | None = None
    if deadline_s is not None and deadline_s > 0:
        deadline_at = monotonic() + deadline_s

    def _one(source: Source) -> tuple[str, list[Article] | Exception]:
        if deadline_at is not None and monotonic() >= deadline_at:
            return source.id, RssFetchDeadlineExceeded(
                f"RSS fetch deadline ({deadline_s:.0f}s) reached; skipped"
            )
        try:
            return source.id, fetch_source(
                source, timeout=timeout, sleep_fn=sleep_fn
            )
        except Exception as exc:  # noqa: BLE001 — per-source isolation
            return source.id, exc

    workers = max(1, min(max_workers, len(source_list)))
    pending: dict[str, list[Article] | Exception] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, source) for source in source_list]
        for fut in as_completed(futures):
            source_id, payload = fut.result()
            pending[source_id] = payload
    # Preserve registry order for run-stats / tests.
    for source in source_list:
        results[source.id] = pending[source.id]
    return results
