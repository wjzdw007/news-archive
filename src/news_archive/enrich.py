"""Fill thin RSS summaries by fetching the original page.

Private DB stores readable plain-text in content_snapshot.
Public summary is derived (≤280 chars) and written to the summary column
so Pages export never needs to read content_snapshot.

Soft-fail per article: paywall / anti-bot / timeout / non-2xx must not
fail the main RSS/X fetch job. Logs host + reason only (no secrets).
"""

from __future__ import annotations

import html
import re
import sys
import time
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from .store import Store

MIN_USABLE_SUMMARY = 80
PUBLIC_SUMMARY_MAX = 280
ENRICH_TIMEOUT = 12.0
ENRICH_DELAY_S = 0.5
MAX_HTTP_PER_RUN = 40

_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>", re.S)
_WS_RE = re.compile(r"\s+")

_ENRICH_HEADERS = {
    "User-Agent": "news-archive/0.1 (+https://localhost; daily archive bot)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
}


def html_to_text(value: object | None) -> str:
    """Strip tags / scripts and collapse whitespace to readable plain text."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = _SCRIPT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def public_summary_from(text: str | None) -> str | None:
    """Plain-text public summary, capped at 280 Unicode chars."""
    cleaned = html_to_text(text)
    if not cleaned:
        return None
    if len(cleaned) > PUBLIC_SUMMARY_MAX:
        return cleaned[:PUBLIC_SUMMARY_MAX]
    return cleaned


def derive_public_summary(*, snapshot: str | None, summary: str | None) -> str | None:
    """Prefer snapshot body, else existing summary. Always ≤280, no HTML."""
    preferred = public_summary_from(snapshot)
    if preferred:
        return preferred
    return public_summary_from(summary)


def is_http_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    return urlparse(url.strip()).scheme in ("http", "https")


def summary_plain_len(summary: object | None) -> int:
    return len(html_to_text(summary))


def snapshot_plain_len(snapshot: object | None) -> int:
    return len(html_to_text(snapshot))


def needs_summary_fill(row: dict[str, Any]) -> bool:
    """True when stripped summary is empty or < 80 Unicode chars."""
    if row.get("status") == "gone":
        return False
    return summary_plain_len(row.get("summary")) < MIN_USABLE_SUMMARY


def should_fetch_page(row: dict[str, Any]) -> bool:
    """HTTP only when summary is thin, URL is http(s), and snapshot is unused."""
    if not needs_summary_fill(row):
        return False
    if not is_http_url(row.get("url")):
        return False
    if snapshot_plain_len(row.get("content_snapshot")) >= MIN_USABLE_SUMMARY:
        return False
    return True


def _safe_host(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


def log_soft_fail(url: str, reason: str, status: int | None = None) -> None:
    host = _safe_host(url)
    extra = f" status={status}" if status is not None else ""
    print(f"enrich soft-fail host={host}{extra} reason={reason}", file=sys.stderr)


def fetch_page_text(url: str, client: httpx.Client) -> str | None:
    """GET original page; return readable plain text or None on soft-fail."""
    try:
        resp = client.get(url)
    except httpx.TimeoutException:
        log_soft_fail(url, "timeout")
        return None
    except httpx.HTTPError as exc:
        log_soft_fail(url, f"http_error:{type(exc).__name__}")
        return None
    except Exception as exc:  # noqa: BLE001 — never break the fetch job
        log_soft_fail(url, f"error:{type(exc).__name__}")
        return None

    if resp.status_code < 200 or resp.status_code >= 300:
        log_soft_fail(url, "non_2xx", status=resp.status_code)
        return None

    content_type = (resp.headers.get("content-type") or "").lower()
    if any(
        token in content_type
        for token in ("image/", "audio/", "video/", "application/pdf", "octet-stream")
    ):
        log_soft_fail(url, "unsupported_content_type")
        return None

    text = html_to_text(resp.text)
    if not text:
        log_soft_fail(url, "empty_body", status=resp.status_code)
        return None
    return text


def enrich_store(
    store: Store,
    *,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    max_http: int = MAX_HTTP_PER_RUN,
    timeout: float = ENRICH_TIMEOUT,
) -> dict[str, int]:
    """Enrich thin-summary rows. Soft-fails per article; never raises out.

    Returns counters for run-stats (no URLs, no secrets).
    """
    stats = {
        "candidates": 0,
        "fetched": 0,
        "derived": 0,
        "skipped": 0,
        "soft_failed": 0,
    }
    try:
        rows = store.get_articles_for_enrich()
    except Exception as exc:  # noqa: BLE001
        print(f"enrich soft-fail reason=list_rows error={type(exc).__name__}", file=sys.stderr)
        return stats

    own_client = client is None
    sleep = sleep_fn if sleep_fn is not None else time.sleep
    http_used = 0

    try:
        if own_client:
            client = httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers=_ENRICH_HEADERS,
            )
        assert client is not None

        for row in rows:
            try:
                if not needs_summary_fill(row):
                    stats["skipped"] += 1
                    continue
                stats["candidates"] += 1
                url = row.get("url") or ""

                snapshot = row.get("content_snapshot")
                if snapshot_plain_len(snapshot) >= MIN_USABLE_SUMMARY:
                    summary = derive_public_summary(
                        snapshot=snapshot, summary=row.get("summary")
                    )
                    store.update_enrichment(url, summary=summary)
                    stats["derived"] += 1
                    continue

                if not is_http_url(url):
                    stats["skipped"] += 1
                    continue

                if http_used >= max_http:
                    stats["skipped"] += 1
                    continue

                if http_used:
                    sleep(ENRICH_DELAY_S)
                http_used += 1
                body = fetch_page_text(url, client)
                if not body:
                    stats["soft_failed"] += 1
                    continue

                summary = derive_public_summary(snapshot=body, summary=row.get("summary"))
                store.update_enrichment(url, content_snapshot=body, summary=summary)
                stats["fetched"] += 1
            except Exception as exc:  # noqa: BLE001 — isolate one row
                stats["soft_failed"] += 1
                log_soft_fail(str(row.get("url") or ""), f"row_error:{type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        print(f"enrich soft-fail reason=loop error={type(exc).__name__}", file=sys.stderr)
    finally:
        if own_client and client is not None:
            client.close()

    return stats
