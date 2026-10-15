"""Lightweight X/Twitter HTTP client for fetching user timelines.

Follows patterns from x-crawler but minimal: only user timeline fetching.
Auth via Bearer token + cookies (auth_token, ct0).
Soft-fails on missing credentials or network errors.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


class XHTTPError(Exception):
    """X API / auth / rate-limit failure."""


def _make_session(
    bearer_token: str | None = None,
    auth_token: str | None = None,
    ct0: str | None = None,
    csrf_token: str | None = None,
) -> Any:
    """Create HTTP session with X authentication headers and cookies."""
    if requests is None:
        raise XHTTPError("requests library not installed (pip install requests)")

    session = requests.Session()

    # Browser-like headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://x.com/home",
        "Origin": "https://x.com",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })

    # Bearer token (required)
    if bearer_token:
        session.headers["authorization"] = bearer_token if bearer_token.startswith("Bearer ") else f"Bearer {bearer_token}"

    # CSRF token (required for mutations, good practice for reads)
    if csrf_token:
        session.headers["x-csrf-token"] = csrf_token
    elif ct0:
        session.headers["x-csrf-token"] = ct0

    # Cookies for authentication
    if auth_token:
        session.cookies.set("auth_token", auth_token, domain=".x.com")
    if ct0:
        session.cookies.set("ct0", ct0, domain=".x.com")

    return session


def _fetch_user_timeline_raw(
    session: Any,
    username: str,
    max_results: int = 20,
) -> dict[str, Any]:
    """Fetch user timeline via X GraphQL API (UserTweets endpoint).
    
    Returns raw GraphQL response dict.
    Raises XHTTPError on network/auth failures.
    """
    # UserTweets GraphQL endpoint (observed pattern, may change)
    # Alternative: UserByScreenName + user.result.timeline_v2
    # We use a simple approach: get recent tweets from public timeline
    endpoint_id = "V7H0Ap3_Hh2FyS75OCDO3Q"  # UserTweets query ID (example, may need update)
    base_url = "https://x.com/i/api/graphql"
    url = f"{base_url}/{endpoint_id}/UserTweets"

    variables = {
        "userId": username,  # Will be resolved to user ID by X API if needed
        "count": max_results,
        "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withVoice": False,
        "withV2Timeline": True,
    }

    features = {
        "rweb_lists_timeline_redesign_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }

    params = {
        "variables": json.dumps(variables),
        "features": json.dumps(features),
    }

    try:
        resp = session.get(url, params=params, timeout=30)
    except Exception as exc:
        # Network/connection errors
        raise XHTTPError(f"network error: {exc}") from exc
    
    # Handle HTTP status codes
    if resp.status_code == 429:
        raise XHTTPError("rate limited (429)")
    if resp.status_code == 401:
        raise XHTTPError("unauthorized (401) — check credentials")
    if resp.status_code != 200:
        raise XHTTPError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    # Parse JSON
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise XHTTPError(f"invalid JSON response: {exc}") from exc


def _parse_tweets_from_timeline(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse tweets from UserTweets GraphQL response.
    
    Returns list of dicts with keys: post_id, text, posted_at, url.
    """
    tweets: list[dict[str, Any]] = []
    
    try:
        # GraphQL data structure (may vary by endpoint)
        # Typical path: data.user.result.timeline_v2.timeline.instructions
        # Fallback: try multiple known paths
        instructions = []
        
        # Try path 1: data.user.result.timeline_v2.timeline.instructions
        user = data.get("data", {}).get("user", {})
        if user:
            timeline = user.get("result", {}).get("timeline_v2", {}).get("timeline", {})
            instructions = timeline.get("instructions", [])
        
        # Try path 2: data.threaded_conversation_with_injections_v2.instructions
        if not instructions:
            threaded = data.get("data", {}).get("threaded_conversation_with_injections_v2", {})
            instructions = threaded.get("instructions", [])

        for instruction in instructions:
            if instruction.get("type") in ("TimelineAddEntries", "TimelineReplaceEntry"):
                entries = instruction.get("entries", [])
                for entry in entries:
                    # Skip promoted tweets and cursors
                    entry_id = entry.get("entryId", "")
                    if not entry_id.startswith("tweet-"):
                        continue
                    
                    # Extract tweet data
                    content = entry.get("content", {})
                    item_content = content.get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {})
                    result = tweet_results.get("result", {})
                    
                    if result.get("__typename") == "Tweet":
                        legacy = result.get("legacy", {})
                        post_id = result.get("rest_id")
                        text = legacy.get("full_text", "")
                        created_at = legacy.get("created_at")  # RFC 2822 format
                        
                        # Get username from core.user_results
                        user_results = result.get("core", {}).get("user_results", {}).get("result", {})
                        username = user_results.get("legacy", {}).get("screen_name", "unknown")
                        
                        if post_id and text:
                            tweets.append({
                                "post_id": post_id,
                                "text": text,
                                "posted_at": _parse_x_timestamp(created_at) if created_at else None,
                                "url": f"https://x.com/{username}/status/{post_id}",
                            })
    except Exception:
        # Parsing errors are non-fatal; return what we got
        pass
    
    return tweets


def _parse_x_timestamp(ts: str) -> str:
    """Convert X created_at (RFC 2822) to ISO 8601.
    
    Example: "Mon Oct 14 12:34:56 +0000 2024" -> "2024-10-14T12:34:56+00:00"
    """
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(ts)
        return dt.isoformat()
    except Exception:
        return ts  # Fallback: return as-is


def fetch_user_timeline(
    username: str,
    max_results: int = 20,
    *,
    bearer_token: str | None = None,
    auth_token: str | None = None,
    ct0: str | None = None,
    csrf_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent tweets from a user's timeline.
    
    Args:
        username: X/Twitter username (without @)
        max_results: Max tweets to fetch (default 20)
        bearer_token: X API Bearer token (env: X_BEARER_TOKEN)
        auth_token: X auth_token cookie (env: X_AUTH_TOKEN)
        ct0: X ct0 cookie (env: X_CT0_TOKEN)
        csrf_token: X CSRF token (env: X_CSRF_TOKEN, fallback to ct0)
    
    Returns:
        List of dicts with keys: post_id, text, posted_at, url
    
    Raises:
        XHTTPError: On missing credentials or API errors
    """
    # Auto-load from env if not provided
    bearer_token = bearer_token or os.getenv("X_BEARER_TOKEN")
    auth_token = auth_token or os.getenv("X_AUTH_TOKEN")
    ct0 = ct0 or os.getenv("X_CT0_TOKEN")
    csrf_token = csrf_token or os.getenv("X_CSRF_TOKEN") or ct0

    if not bearer_token:
        raise XHTTPError("missing X_BEARER_TOKEN (required)")
    if not auth_token or not ct0:
        raise XHTTPError("missing X_AUTH_TOKEN and/or X_CT0_TOKEN (required)")

    session = _make_session(
        bearer_token=bearer_token,
        auth_token=auth_token,
        ct0=ct0,
        csrf_token=csrf_token,
    )

    data = _fetch_user_timeline_raw(session, username, max_results)
    return _parse_tweets_from_timeline(data)


# Convenience wrapper for fetch_account_posts
def create_live_fetcher() -> Any:
    """Create a live_fetcher callable for x_fetch.fetch_account_posts.
    
    Returns:
        Callable[[str], list[dict]] that fetches tweets for a username
    
    Raises:
        XHTTPError: On missing credentials (caller can soft-fail)
    """
    # Check credentials early
    bearer_token = os.getenv("X_BEARER_TOKEN")
    auth_token = os.getenv("X_AUTH_TOKEN")
    ct0 = os.getenv("X_CT0_TOKEN")

    if not bearer_token or not auth_token or not ct0:
        raise XHTTPError(
            "X credentials missing: need X_BEARER_TOKEN, X_AUTH_TOKEN, X_CT0_TOKEN"
        )

    def fetcher(username: str) -> list[dict[str, Any]]:
        return fetch_user_timeline(username, max_results=20)

    return fetcher
