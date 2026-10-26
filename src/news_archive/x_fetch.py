"""Fetch X posts for configured accounts. Mock mode for offline / CI.

Live mode is optional; failures raise XFetchError so callers can soft-fail
without touching the RSS pipeline.

News accounts stay on HomeTimeline + filter.
AI primaries (and backups when needed) use per-handle UserTweets.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .x_config import (
    X_AI_BACKUP_ACCOUNTS,
    X_AI_PRIMARY_ACCOUNTS,
    X_NEWS_ACCOUNTS,
    x_fetch_accounts,
)
from .x_store import XPost

# Same 24h window as tech_ai.WINDOW_HOURS — backups only if primaries are empty.
_AI_WINDOW_HOURS = 24


class XFetchError(Exception):
    """X API / auth / rate-limit failure (soft-fail at job boundary)."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _author_key(name: str | None) -> str:
    return (name or "").strip().lstrip("@").lower()


def _split_fetch_accounts(
    accounts: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Partition requested handles into news / AI primary / AI backup.

    Canonical config order is kept. elonmusk is both news and AI primary —
    it stays on HomeTimeline (news) and is also user-timeline fetched (AI).
    """
    requested = {_author_key(a) for a in accounts}
    news = [a for a in X_NEWS_ACCOUNTS if _author_key(a) in requested]
    primaries = [a for a in X_AI_PRIMARY_ACCOUNTS if _author_key(a) in requested]
    backups = [a for a in X_AI_BACKUP_ACCOUNTS if _author_key(a) in requested]
    return news, primaries, backups


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def primaries_usable_in_window(
    posts: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    hours: int = _AI_WINDOW_HOURS,
) -> bool:
    """True when any primary-shaped post is nonempty and in the time window."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=hours)
    for post in posts:
        text = str(post.get("text") or post.get("text_snapshot") or "").strip()
        if not text:
            continue
        dt = _parse_iso(post.get("posted_at"))
        if dt is not None and dt >= cutoff:
            return True
    return False


def mock_posts_for_accounts(
    accounts: list[str] | None = None,
    *,
    fetched_at: str | None = None,
) -> list[XPost]:
    """Deterministic mock posts for schema/pipeline tests (no network)."""
    accounts = accounts or x_fetch_accounts()
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


def _snowflake_newer(post_id: str, since_id: str) -> bool:
    try:
        return int(post_id) > int(since_id)
    except (TypeError, ValueError):
        return True


def _apply_since_ids(
    tweets: list[dict[str, Any]],
    since_ids: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Drop already-seen snowflakes after the backup-window decision."""
    if not since_ids:
        return tweets
    kept: list[dict[str, Any]] = []
    for tweet in tweets:
        key = _author_key(tweet.get("author"))
        since_id = since_ids.get(key)
        pid = str(tweet.get("post_id") or "")
        if since_id and pid and not _snowflake_newer(pid, since_id):
            continue
        kept.append(tweet)
    return kept


def _to_xposts(raw_tweets: list[dict[str, Any]], fetched_at: str) -> list[XPost]:
    out: list[XPost] = []
    seen: set[str] = set()
    for raw in raw_tweets:
        pid = str(raw.get("post_id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(
            XPost(
                post_id=pid,
                author=raw["author"],
                url=raw["url"],
                text_snapshot=raw["text"],
                posted_at=raw.get("posted_at"),
                fetched_at=fetched_at,
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
    since_ids: dict[str, str] | None = None,
) -> list[XPost]:
    """Fetch posts. mode=mock uses fixtures; mode=live splits news vs AI.

    Live news: HomeTimeline via x_http_client, filter to news accounts.
    Live AI: UserTweets per primary handle; backups only if primaries have
    no usable posts in the 24h window. Follow is not required for AI.
    """
    accounts = accounts or x_fetch_accounts()
    if mode == "mock":
        return mock_posts_for_accounts(accounts)
    if mode != "live":
        raise XFetchError(f"unknown mode: {mode}")

    news_accounts, primary_accounts, backup_accounts = _split_fetch_accounts(accounts)

    try:
        from .x_http_client import XHTTPError, fetch_news_accounts, fetch_user_accounts
    except Exception as exc:  # noqa: BLE001
        raise XFetchError(str(exc)) from exc

    raw: list[dict[str, Any]] = []
    try:
        if news_accounts:
            raw.extend(
                fetch_news_accounts(
                    target_accounts=news_accounts,
                    auth_token=auth_token,
                    ct0=ct0,
                    bearer_token=bearer_token,
                    timeline_type="following",
                    max_results=40,
                )
            )
    except XHTTPError as exc:
        raise XFetchError(str(exc)) from exc

    rate_limited = False
    primary_raw: list[dict[str, Any]] = []
    if primary_accounts:
        try:
            primary_raw = fetch_user_accounts(
                target_accounts=primary_accounts,
                auth_token=auth_token,
                ct0=ct0,
                bearer_token=bearer_token,
            )
            raw.extend(primary_raw)
        except XHTTPError as exc:
            msg = str(exc)
            # Auth/config failures are job-level; 429 keeps any news posts.
            if "unauthorized" in msg or "missing X_AUTH_TOKEN" in msg:
                raise XFetchError(msg) from exc
            rate_limited = "429" in msg or "rate limited" in msg

    if (
        backup_accounts
        and not rate_limited
        and not primaries_usable_in_window(primary_raw)
    ):
        try:
            raw.extend(
                fetch_user_accounts(
                    target_accounts=backup_accounts,
                    auth_token=auth_token,
                    ct0=ct0,
                    bearer_token=bearer_token,
                )
            )
        except XHTTPError as exc:
            msg = str(exc)
            if "unauthorized" in msg or "missing X_AUTH_TOKEN" in msg:
                raise XFetchError(msg) from exc

    return _to_xposts(_apply_since_ids(raw, since_ids), _iso_now())


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
