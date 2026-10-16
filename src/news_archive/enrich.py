"""Archive-first page enrich: fill private content_snapshot from the original URL.

Enqueue every eligible article that is missing a *usable* private snapshot
(empty or too-short shell/nav chrome), not only thin public summaries.

Private DB stores readable plain-text in content_snapshot.
Public summary stays ≤280 chars, tags stripped. If public summary is already
qualified (≥80), leave it; only empty/<80 summaries are derived from the
snapshot so Pages export never needs to read content_snapshot.

Soft-fail per article: paywall / anti-bot / timeout / non-2xx must not
fail the main RSS/X fetch job. Logs host + reason only (no secrets).
X posts are out of scope this cut (text_snapshot only).

Per-source backoff: ≥3 consecutive HTTP 403 / 429 / timeout in one run
stops enqueueing that source for the rest of the run and writes a 6-hour
cooldown into sqlite (persisted on the data branch with archive.sqlite3).
"""

from __future__ import annotations

import html
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from .store import Store

MIN_USABLE_SUMMARY = 80
PUBLIC_SUMMARY_MAX = 280
ENRICH_TIMEOUT = 12.0
ENRICH_DELAY_S = 0.5
MAX_HTTP_PER_RUN = 40
CONSECUTIVE_FAIL_LIMIT = 3
COOLDOWN_HOURS = 6
BACKOFF_FAIL_REASONS = frozenset({"403", "429", "timeout"})

_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>", re.S)
_WS_RE = re.compile(r"\s+")

# Chrome / nav / legal tokens. Too-short remainder after stripping these
# counts as an unusable shell snapshot (same 80-char product floor).
_SHELL_TOKEN_RE = re.compile(
    r"(?i)"
    r"首页|导航|登录|注册|搜索|版权所有|网站地图|联系我们|"
    r"home|menu|login|sign[\s-]?in|sign[\s-]?up|subscribe now|"
    r"cookie[\s-]?policy|all rights reserved|privacy policy|"
    r"terms of (?:use|service)|advertisement|newsletter"
)

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


def is_shell_or_nav_text(text: str) -> bool:
    """True when chrome/nav tokens leave too little real body (< 80 chars)."""
    if not text:
        return True
    remainder = _SHELL_TOKEN_RE.sub(" ", text)
    remainder = _WS_RE.sub(" ", remainder).strip()
    return len(remainder) < MIN_USABLE_SUMMARY


def is_usable_snapshot(snapshot: object | None) -> bool:
    """Usable private body: stripped length ≥80 and not shell/nav chrome only."""
    text = html_to_text(snapshot)
    if len(text) < MIN_USABLE_SUMMARY:
        return False
    if is_shell_or_nav_text(text):
        return False
    return True


def needs_summary_fill(row: dict[str, Any]) -> bool:
    """True when stripped public summary is empty or < 80 Unicode chars."""
    if row.get("status") == "gone":
        return False
    return summary_plain_len(row.get("summary")) < MIN_USABLE_SUMMARY


def should_fetch_page(row: dict[str, Any]) -> bool:
    """HTTP when http(s), not gone, and private snapshot is missing/unusable."""
    if row.get("status") == "gone":
        return False
    if not is_http_url(row.get("url")):
        return False
    if is_usable_snapshot(row.get("content_snapshot")):
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


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _empty_source_stats() -> dict[str, Any]:
    return {
        "success": 0,
        "soft_fail": 0,
        "skipped": 0,
        "stopped": False,
        "in_cooldown": False,
    }


def _source_bucket(by_source: dict[str, dict[str, Any]], source: str) -> dict[str, Any]:
    if source not in by_source:
        by_source[source] = _empty_source_stats()
    return by_source[source]


def load_active_cooldowns(
    store: Store, now: datetime
) -> dict[str, datetime]:
    """Sources whose persisted cooldown `until_utc` is still in the future."""
    active: dict[str, datetime] = {}
    try:
        rows = store.get_enrich_backoff()
    except Exception as exc:  # noqa: BLE001
        print(
            f"enrich soft-fail reason=load_backoff error={type(exc).__name__}",
            file=sys.stderr,
        )
        return active
    for source, until_raw in rows.items():
        until = _parse_iso(until_raw)
        if until is not None and until > now:
            active[source] = until
    return active


def snapshot_coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Private usable-snapshot count over active (non-gone) articles."""
    active = [row for row in rows if row.get("status") != "gone"]
    usable = sum(
        1 for row in active if is_usable_snapshot(row.get("content_snapshot"))
    )
    return {
        "usable_snapshots": usable,
        "active_articles": len(active),
    }


@dataclass(frozen=True)
class PageFetch:
    """Outcome of one original-page GET. `text` set on success."""

    text: str | None = None
    reason: str | None = None
    status: int | None = None

    @property
    def ok(self) -> bool:
        return self.text is not None

    @property
    def is_backoff_failure(self) -> bool:
        return self.reason in BACKOFF_FAIL_REASONS


def fetch_page_text(url: str, client: httpx.Client) -> PageFetch:
    """GET original page; return readable plain text or a soft-fail outcome."""
    try:
        resp = client.get(url)
    except httpx.TimeoutException:
        log_soft_fail(url, "timeout")
        return PageFetch(reason="timeout")
    except httpx.HTTPError as exc:
        log_soft_fail(url, f"http_error:{type(exc).__name__}")
        return PageFetch(reason=f"http_error:{type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001 — never break the fetch job
        log_soft_fail(url, f"error:{type(exc).__name__}")
        return PageFetch(reason=f"error:{type(exc).__name__}")

    if resp.status_code == 403:
        log_soft_fail(url, "403", status=403)
        return PageFetch(reason="403", status=403)
    if resp.status_code == 429:
        log_soft_fail(url, "429", status=429)
        return PageFetch(reason="429", status=429)
    if resp.status_code < 200 or resp.status_code >= 300:
        log_soft_fail(url, "non_2xx", status=resp.status_code)
        return PageFetch(reason="non_2xx", status=resp.status_code)

    content_type = (resp.headers.get("content-type") or "").lower()
    if any(
        token in content_type
        for token in ("image/", "audio/", "video/", "application/pdf", "octet-stream")
    ):
        log_soft_fail(url, "unsupported_content_type")
        return PageFetch(reason="unsupported_content_type", status=resp.status_code)

    text = html_to_text(resp.text)
    if not text:
        log_soft_fail(url, "empty_body", status=resp.status_code)
        return PageFetch(reason="empty_body", status=resp.status_code)
    return PageFetch(text=text, status=resp.status_code)


def _trip_backoff(
    store: Store,
    source: str,
    *,
    now: datetime,
    by_source: dict[str, dict[str, Any]],
) -> None:
    bucket = _source_bucket(by_source, source)
    bucket["stopped"] = True
    bucket["in_cooldown"] = True
    until = now + timedelta(hours=COOLDOWN_HOURS)
    try:
        store.upsert_enrich_backoff(source, until.isoformat())
    except Exception as exc:  # noqa: BLE001
        print(
            f"enrich soft-fail reason=save_backoff source={source} "
            f"error={type(exc).__name__}",
            file=sys.stderr,
        )
    print(
        f"enrich backoff source={source} consecutive={CONSECUTIVE_FAIL_LIMIT} "
        f"cooldown_hours={COOLDOWN_HOURS}",
        file=sys.stderr,
    )


def render_job_summary(enrich_stats: dict[str, Any]) -> str:
    """Markdown coverage board for GITHUB_STEP_SUMMARY. No article body text."""
    coverage = enrich_stats.get("coverage") or {}
    usable = int(coverage.get("usable_snapshots") or 0)
    active = int(coverage.get("active_articles") or 0)
    lines = [
        "## Enrich coverage board",
        "",
        f"- **candidates:** {int(enrich_stats.get('candidates') or 0)}",
        f"- **fetched (ok):** {int(enrich_stats.get('fetched') or 0)}",
        f"- **soft_failed:** {int(enrich_stats.get('soft_failed') or 0)}",
        f"- **skipped:** {int(enrich_stats.get('skipped') or 0)}",
        "",
        "### Per-source",
        "",
        "| source | success | soft_fail | stopped (backoff) |",
        "| --- | ---: | ---: | --- |",
    ]
    by_source = enrich_stats.get("by_source") or {}
    if by_source:
        for source in sorted(by_source):
            bucket = by_source[source] or {}
            stopped = "yes" if bucket.get("stopped") else "no"
            lines.append(
                f"| {source} | {int(bucket.get('success') or 0)} | "
                f"{int(bucket.get('soft_fail') or 0)} | {stopped} |"
            )
    else:
        lines.append("| — | 0 | 0 | no |")
    lines.extend(
        [
            "",
            "### Private snapshot coverage",
            "",
            f"usable `content_snapshot`: **{usable} / {active}** active (non-gone) articles",
            "",
        ]
    )
    return "\n".join(lines)


def write_job_summary(
    enrich_stats: dict[str, Any],
    path: str | Path | None = None,
) -> None:
    """Append coverage board to GITHUB_STEP_SUMMARY (or `path` in tests)."""
    target = path if path is not None else os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    text = render_job_summary(enrich_stats)
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def enrich_store(
    store: Store,
    *,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    max_http: int = MAX_HTTP_PER_RUN,
    timeout: float = ENRICH_TIMEOUT,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Fill missing private snapshots. Soft-fails per article; never raises out.

    Caps HTTP at max_http per run (~0.5s delay) so the stockpile drains
    across cron runs. 403/paywall/timeout leave the row retryable later.

    Per source: ≥3 consecutive 403/429/timeout in this run → stop enqueueing
    that source for the rest of the run and persist a 6-hour cooldown.

    Returns counters for run-stats (no URLs, no secrets, no snapshot bodies).
    """
    stats: dict[str, Any] = {
        "candidates": 0,
        "fetched": 0,
        "derived": 0,
        "skipped": 0,
        "soft_failed": 0,
        "http_used": 0,
        "by_source": {},
        "coverage": {"usable_snapshots": 0, "active_articles": 0},
    }
    try:
        rows = store.get_articles_for_enrich()
    except Exception as exc:  # noqa: BLE001
        print(f"enrich soft-fail reason=list_rows error={type(exc).__name__}", file=sys.stderr)
        return stats

    own_client = client is None
    sleep = sleep_fn if sleep_fn is not None else time.sleep
    clock = now_fn if now_fn is not None else (lambda: datetime.now(timezone.utc))
    now = clock()
    http_used = 0
    consecutive: dict[str, int] = {}
    by_source: dict[str, dict[str, Any]] = stats["by_source"]
    cooldown_active = load_active_cooldowns(store, now)
    stopped_sources: set[str] = set()
    for source in cooldown_active:
        _source_bucket(by_source, source)["in_cooldown"] = True

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
                url = row.get("url") or ""
                snapshot = row.get("content_snapshot")
                source = str(row.get("source") or "unknown")
                bucket = _source_bucket(by_source, source)

                if is_usable_snapshot(snapshot):
                    if needs_summary_fill(row):
                        summary = derive_public_summary(
                            snapshot=snapshot, summary=row.get("summary")
                        )
                        if summary:
                            store.update_enrichment(url, summary=summary)
                            stats["derived"] += 1
                            continue
                    stats["skipped"] += 1
                    bucket["skipped"] += 1
                    continue

                if not should_fetch_page(row):
                    stats["skipped"] += 1
                    bucket["skipped"] += 1
                    continue

                if source in cooldown_active or source in stopped_sources:
                    # Do not enqueue this source (in-run stop or 6h cooldown).
                    stats["skipped"] += 1
                    bucket["skipped"] += 1
                    if source in cooldown_active:
                        bucket["in_cooldown"] = True
                    if source in stopped_sources:
                        bucket["stopped"] = True
                    continue

                stats["candidates"] += 1

                if http_used >= max_http:
                    # Stockpile: leave unusable snapshot for a later cron run.
                    stats["skipped"] += 1
                    bucket["skipped"] += 1
                    continue

                if http_used:
                    sleep(ENRICH_DELAY_S)
                http_used += 1
                outcome = fetch_page_text(url, client)
                if not outcome.ok:
                    stats["soft_failed"] += 1
                    bucket["soft_fail"] += 1
                    if outcome.is_backoff_failure:
                        consecutive[source] = consecutive.get(source, 0) + 1
                        if consecutive[source] >= CONSECUTIVE_FAIL_LIMIT:
                            stopped_sources.add(source)
                            _trip_backoff(
                                store, source, now=now, by_source=by_source
                            )
                    else:
                        consecutive[source] = 0
                    continue

                consecutive[source] = 0
                body = outcome.text or ""
                # Qualified public summary (≥80) stays; only fill empty/<80.
                if needs_summary_fill(row):
                    summary = derive_public_summary(
                        snapshot=body, summary=row.get("summary")
                    )
                    store.update_enrichment(
                        url, content_snapshot=body, summary=summary
                    )
                else:
                    store.update_enrichment(url, content_snapshot=body)
                stats["fetched"] += 1
                bucket["success"] += 1
            except Exception as exc:  # noqa: BLE001 — isolate one row
                stats["soft_failed"] += 1
                source = str(row.get("source") or "unknown")
                _source_bucket(by_source, source)["soft_fail"] += 1
                log_soft_fail(str(row.get("url") or ""), f"row_error:{type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        print(f"enrich soft-fail reason=loop error={type(exc).__name__}", file=sys.stderr)
    finally:
        if own_client and client is not None:
            client.close()

    stats["http_used"] = http_used
    try:
        stats["coverage"] = snapshot_coverage(store.get_articles_for_enrich())
    except Exception as exc:  # noqa: BLE001
        print(
            f"enrich soft-fail reason=coverage error={type(exc).__name__}",
            file=sys.stderr,
        )
    return stats
