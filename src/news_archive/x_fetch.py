"""Fetch X posts for configured accounts. Mock mode for offline / CI.

Live mode is optional; failures raise XFetchError so callers can soft-fail
without touching the RSS pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .x_config import X_NEWS_ACCOUNTS
from .x_store import XPost


class XFetchError(Exception):
    """X API / auth / rate-limit failure (soft-fail at job boundary)."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mock_posts_for_accounts(
    accounts: list[str] | None = None,
    *,
    fetched_at: str | None = None,
) -> list[XPost]:
    """Deterministic mock posts for schema/pipeline tests (no network)."""
    accounts = accounts or list(X_NEWS_ACCOUNTS)
    now = fetched_at or _iso_now()
    out: list[XPost] = []
    for i, author in enumerate(accounts):
        pid = f"mock-{author}-100{i}"
        out.append(
            XPost(
                post_id=pid,
                author=author,
                url=f"https://x.com/{author}/status/{pid}",
                text_snapshot=f"[{author}] mock headline about markets and tech #{i}",
                posted_at=now,
                fetched_at=now,
                status="active",
            )
        )
    return out


def fetch_account_posts(
    accounts: list[str] | None = None,
    *,
    mode: str = "mock",
    live_fetcher: Callable[[str], list[dict[str, Any]]] | None = None,
) -> list[XPost]:
    """Fetch posts. mode=mock uses fixtures; mode=live auto-creates fetcher if credentials present.

    live_fetcher(author) -> list of dicts with keys post_id, text, posted_at, url.
    If mode=live and live_fetcher is None, will attempt to create one via x_http_client.
    """
    accounts = accounts or list(X_NEWS_ACCOUNTS)
    if mode == "mock":
        return mock_posts_for_accounts(accounts)
    if mode != "live":
        raise XFetchError(f"unknown mode: {mode}")
    
    # Auto-create live fetcher if not provided (uses env secrets)
    if live_fetcher is None:
        try:
            from .x_http_client import XHTTPError, create_live_fetcher
            live_fetcher = create_live_fetcher()
        except (ImportError, XHTTPError) as exc:
            raise XFetchError(f"live mode unavailable: {exc}") from exc
    
    now = _iso_now()
    out: list[XPost] = []
    try:
        for author in accounts:
            for raw in live_fetcher(author):
                pid = str(raw["post_id"])
                out.append(
                    XPost(
                        post_id=pid,
                        author=author,
                        url=raw.get("url") or f"https://x.com/{author}/status/{pid}",
                        text_snapshot=raw.get("text") or "",
                        posted_at=raw.get("posted_at"),
                        fetched_at=now,
                        status="active",
                    )
                )
    except XFetchError:
        raise
    except Exception as exc:  # noqa: BLE001 — boundary soft-fail
        raise XFetchError(str(exc)) from exc
    return out


def sync_posts(
    store: Any,
    posts: list[XPost],
    *,
    seen_ids: set[str] | None = None,
) -> dict[str, int]:
    """Upsert posts; mark previously active ids not seen as gone (optional)."""
    inserted = 0
    for p in posts:
        if store.upsert(p):
            inserted += 1
    gone = 0
    if seen_ids is not None:
        # caller passes prior active ids that disappeared this round
        for pid in seen_ids:
            if store.mark_gone(pid):
                gone += 1
    return {"inserted": inserted, "gone": gone, "seen": len(posts)}
