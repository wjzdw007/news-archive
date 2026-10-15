"""Fetch X posts for configured accounts. Mock mode for offline / CI.

Live mode is optional; failures raise XFetchError so callers can soft-fail
without touching the RSS pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
    auth_token: str | None = None,
    ct0: str | None = None,
    bearer_token: str | None = None,
) -> list[XPost]:
    """Fetch posts. mode=mock uses fixtures; mode=live uses HomeTimeline + filter.

    Live mode fetches HomeTimeline via x_http_client, filters to target accounts,
    and logs author distribution (pre/post filter).
    """
    accounts = accounts or list(X_NEWS_ACCOUNTS)
    if mode == "mock":
        return mock_posts_for_accounts(accounts)
    if mode != "live":
        raise XFetchError(f"unknown mode: {mode}")
    
    # Live mode: use x_http_client (HomeTimeline + filter + logging built-in)
    try:
        from .x_http_client import XHTTPError, fetch_news_accounts
        
        # fetch_news_accounts logs author distribution internally
        raw_tweets = fetch_news_accounts(
            target_accounts=accounts,
            auth_token=auth_token,
            ct0=ct0,
            bearer_token=bearer_token,
            timeline_type="following",
            max_results=40,
        )
        
        # Convert to XPost format
        now = _iso_now()
        out: list[XPost] = []
        for raw in raw_tweets:
            out.append(
                XPost(
                    post_id=raw["post_id"],
                    author=raw["author"],
                    url=raw["url"],
                    text_snapshot=raw["text"],
                    posted_at=raw.get("posted_at"),
                    fetched_at=now,
                    status="active",
                )
            )
        
        return out
        
    except XFetchError:
        raise
    except Exception as exc:  # noqa: BLE001 — boundary soft-fail
        # Wrap XHTTPError and other exceptions
        if exc.__class__.__name__ == "XHTTPError":
            raise XFetchError(str(exc)) from exc
        raise XFetchError(str(exc)) from exc


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
