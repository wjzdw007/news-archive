"""Lightweight X/Twitter HTTP client for news accounts.

Strictly follows x-crawler patterns:
- HomeLatestTimeline GraphQL endpoint (query id from x-crawler)
- Auth via cookies (auth_token, ct0) + headers (Authorization Bearer, X-Csrf-Token)
- Fetch home timeline, then filter to target accounts (X_NEWS_ACCOUNTS: BBCChinese, Reuters, FT, TechCrunch, Tesla, elonmusk, AP, WSJ, BBCWorld, NPR, nytimes, TheEconomist, SCMPNews, Bloomberg, WIRED, AFP, CNBC, AJEnglish, Nature, SkyNews, ABC, CBSNews, axios, NikkeiAsia, politico)
- Soft-fails on missing credentials or network errors.

Reference: https://github.com/wjzdw007/x-crawler (crawler.py)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


class XHTTPError(Exception):
    """X API / auth / rate-limit failure."""


# GraphQL query IDs from x-crawler (crawler.py lines 40-42)
# These may change; monitor x-crawler repo for updates
X_API_ENDPOINTS = {
    "recommended": "xNGIIoXaz9DyeBXBfn3AjA/HomeLatestTimeline",
    "following": "1_nms9JVtHQxTw8VwZJciQ/HomeTimeline",
}


def _make_session(
    auth_token: str,
    ct0: str,
    bearer_token: str | None = None,
    csrf_token: str | None = None,
) -> Any:
    """Create HTTP session with X authentication (x-crawler pattern).
    
    Args:
        auth_token: X auth_token cookie (required)
        ct0: X ct0 cookie (required)
        bearer_token: Authorization header (optional, x-crawler includes it)
        csrf_token: X-Csrf-Token header (optional, defaults to ct0)
    """
    if requests is None:
        raise XHTTPError("requests library not installed (pip install requests)")

    session = requests.Session()

    # Browser-like headers (from x-crawler crawler.py lines 57-66)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://x.com/home",
        "Origin": "https://x.com",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })

    # Authorization header (x-crawler config_loader.py line 63)
    if bearer_token:
        # x-crawler accepts with or without "Bearer " prefix
        if not bearer_token.startswith("Bearer "):
            bearer_token = f"Bearer {bearer_token}"
        session.headers["Authorization"] = bearer_token

    # CSRF header (x-crawler config_loader.py line 65)
    session.headers["X-Csrf-Token"] = csrf_token or ct0

    # Cookies (x-crawler config_loader.py lines 59-61)
    session.cookies.set("auth_token", auth_token, domain=".x.com")
    session.cookies.set("ct0", ct0, domain=".x.com")

    return session


def _fetch_home_timeline_raw(
    session: Any,
    timeline_type: str = "following",
    max_results: int = 20,
) -> dict[str, Any]:
    """Fetch home timeline via X GraphQL API (x-crawler pattern).
    
    Uses HomeLatestTimeline or HomeTimeline endpoint from x-crawler.
    Returns raw GraphQL response dict.
    
    Args:
        session: Authenticated requests session
        timeline_type: "recommended" (HomeLatestTimeline) or "following" (HomeTimeline)
        max_results: Max tweets to fetch per request
    
    Raises:
        XHTTPError: On network/auth failures
    
    Reference: x-crawler crawler.py lines 186-210
    """
    endpoint = X_API_ENDPOINTS.get(timeline_type)
    if not endpoint:
        raise XHTTPError(f"unknown timeline_type: {timeline_type}")
    
    base_url = "https://x.com/i/api/graphql"
    url = f"{base_url}/{endpoint}"

    # Request parameters (x-crawler crawler.py lines 130-178)
    variables = {
        "count": max_results,
        "includePromotedContent": True,
        "latestControlAvailable": True,
        "requestContext": "launch",
        "withCommunity": True,
    }

    features = {
        "rweb_video_screen_enabled": False,
        "payments_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
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
    """Parse tweets from HomeTimeline GraphQL response.
    
    Returns list of dicts with keys: post_id, author, text, posted_at, url.
    
    Reference: x-crawler crawler.py lines 436-489 (extract_tweets_from_response)
    """
    tweets: list[dict[str, Any]] = []
    
    try:
        # GraphQL data structure (x-crawler pattern)
        home_timeline = data.get("data", {}).get("home", {}).get("home_timeline_urt", {})
        instructions = home_timeline.get("instructions", [])
        
        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                
                for entry in entries:
                    entry_id = entry.get("entryId", "")
                    
                    # Tweet entries (skip promoted tweets and cursors)
                    if entry_id.startswith("tweet-"):
                        content = entry.get("content", {})
                        item_content = content.get("itemContent", {})
                        tweet_results = item_content.get("tweet_results", {})
                        tweet_data = tweet_results.get("result", {})
                        
                        # Unwrap TweetWithVisibilityResults if present
                        if tweet_data.get("__typename") == "TweetWithVisibilityResults":
                            tweet_data = tweet_data.get("tweet", {})
                        
                        if tweet_data.get("__typename") == "Tweet":
                            parsed = _parse_single_tweet(tweet_data)
                            if parsed:
                                tweets.append(parsed)
                    
                    # Conversation modules (multi-tweet entries)
                    elif entry_id.startswith("home-conversation-"):
                        content = entry.get("content", {})
                        if content.get("entryType") == "TimelineTimelineModule":
                            items = content.get("items", [])
                            for item in items:
                                item_content = item.get("item", {}).get("itemContent", {})
                                if item_content.get("itemType") == "TimelineTweet":
                                    tweet_results = item_content.get("tweet_results", {})
                                    tweet_data = tweet_results.get("result", {})
                                    
                                    # Unwrap TweetWithVisibilityResults if present
                                    if tweet_data.get("__typename") == "TweetWithVisibilityResults":
                                        tweet_data = tweet_data.get("tweet", {})
                                    
                                    if tweet_data.get("__typename") == "Tweet":
                                        parsed = _parse_single_tweet(tweet_data)
                                        if parsed:
                                            tweets.append(parsed)
    except Exception:
        # Parsing errors are non-fatal; return what we got
        pass
    
    return tweets


def _parse_single_tweet(tweet_data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single tweet from GraphQL result.
    
    Reference: x-crawler crawler.py lines 330-429 (parse_tweet)
    """
    try:
        legacy = tweet_data.get("legacy", {})
        post_id = tweet_data.get("rest_id")
        
        # Extract text (handle long-form tweets)
        text = ""
        if "note_tweet" in tweet_data:
            note_result = tweet_data.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {})
            if note_result:
                text = note_result.get("text", "")
        
        if not text:
            text = legacy.get("full_text", "")
        
        # Extract user info (X moved screen_name to user.core.screen_name)
        user_results = tweet_data.get("core", {}).get("user_results", {}).get("result", {})
        # Try core.screen_name first (new location), fallback to legacy.screen_name (old)
        author = (
            user_results.get("core", {}).get("screen_name")
            or user_results.get("legacy", {}).get("screen_name")
            or "unknown"
        )
        
        # Parse timestamp (RFC 2822 format from X)
        created_at = legacy.get("created_at")  # e.g. "Mon Oct 14 12:34:56 +0000 2024"
        posted_at = _parse_x_timestamp(created_at) if created_at else None
        
        if not post_id or not text:
            return None
        
        return {
            "post_id": post_id,
            "author": author,
            "text": text,
            "posted_at": posted_at,
            "url": f"https://x.com/{author}/status/{post_id}",
        }
    except Exception:
        return None


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


def fetch_news_accounts(
    target_accounts: list[str],
    *,
    auth_token: str | None = None,
    ct0: str | None = None,
    bearer_token: str | None = None,
    csrf_token: str | None = None,
    timeline_type: str = "following",
    max_results: int = 40,
) -> list[dict[str, Any]]:
    """Fetch recent tweets from home timeline, filter to target accounts.
    
    This is the x-crawler pattern: fetch HomeLatestTimeline/HomeTimeline,
    then filter to the accounts we care about (X_NEWS_ACCOUNTS).
    
    Args:
        target_accounts: List of usernames to filter (e.g. ["BBCChinese", "Reuters"])
        auth_token: X auth_token cookie (env: X_AUTH_TOKEN, required)
        ct0: X ct0 cookie (env: X_CT0_TOKEN, required)
        bearer_token: Authorization header (env: X_BEARER_TOKEN, optional but recommended)
        csrf_token: X-Csrf-Token header (env: X_CSRF_TOKEN, optional, defaults to ct0)
        timeline_type: "recommended" or "following" (default: "following")
        max_results: Max tweets to fetch before filtering (default 40 to get enough after filter)
    
    Returns:
        List of dicts with keys: post_id, author, text, posted_at, url
        Filtered to only include tweets from target_accounts
    
    Raises:
        XHTTPError: On missing credentials or API errors
    
    Reference: x-crawler crawler.py crawl_daily_posts + save_by_user_daily pattern
    """
    # Auto-load from env if not provided
    auth_token = auth_token or os.getenv("X_AUTH_TOKEN")
    ct0 = ct0 or os.getenv("X_CT0_TOKEN")
    bearer_token = bearer_token or os.getenv("X_BEARER_TOKEN")
    csrf_token = csrf_token or os.getenv("X_CSRF_TOKEN")

    if not auth_token or not ct0:
        raise XHTTPError("missing X_AUTH_TOKEN and/or X_CT0_TOKEN (required)")

    session = _make_session(
        auth_token=auth_token,
        ct0=ct0,
        bearer_token=bearer_token,
        csrf_token=csrf_token,
    )

    data = _fetch_home_timeline_raw(session, timeline_type, max_results)
    all_tweets = _parse_tweets_from_timeline(data)
    
    # Log: author distribution before filtering (diagnostic)
    all_authors = [t.get("author", "unknown") for t in all_tweets]
    author_dist = dict(Counter(all_authors).most_common(20))
    print(
        f"[x-fetch] HomeTimeline: {len(all_tweets)} tweets, "
        f"author distribution (top 20): {json.dumps(author_dist, ensure_ascii=False)}",
        file=sys.stderr,
    )
    
    # Filter to target accounts (case-insensitive, x-crawler pattern line 688)
    target_set = {acc.lower() for acc in target_accounts}
    filtered = [
        tweet for tweet in all_tweets
        if tweet.get("author", "").lower() in target_set
    ]
    
    # Log: after filtering
    print(
        f"[x-fetch] Filtered to {len(filtered)} posts from target accounts: {target_accounts}",
        file=sys.stderr,
    )
    
    return filtered


# Convenience wrapper for x_fetch.fetch_account_posts
def create_live_fetcher(target_accounts: list[str]) -> Any:
    """Create a live_fetcher callable for x_fetch.fetch_account_posts.
    
    Args:
        target_accounts: List of usernames to filter (e.g. ["BBCChinese", "Reuters"])
    
    Returns:
        Callable[[str], list[dict]] that fetches tweets for the target accounts
        (Note: first arg is ignored since we filter home timeline)
    
    Raises:
        XHTTPError: On missing credentials (caller can soft-fail)
    """
    # Check credentials early
    auth_token = os.getenv("X_AUTH_TOKEN")
    ct0 = os.getenv("X_CT0_TOKEN")

    if not auth_token or not ct0:
        raise XHTTPError(
            "X credentials missing: need X_AUTH_TOKEN, X_CT0_TOKEN (X_BEARER_TOKEN recommended)"
        )

    # Return a fetcher that fetches home timeline and filters
    # The 'username' arg from fetch_account_posts is ignored since we fetch home timeline
    def fetcher(username: str) -> list[dict[str, Any]]:
        # Fetch all target accounts at once from home timeline
        # Return only posts from this specific username
        all_posts = fetch_news_accounts(
            target_accounts=target_accounts,
            timeline_type="following",
            max_results=40,  # Fetch enough to get posts from all accounts
        )
        # Filter to this specific username for fetch_account_posts loop
        return [p for p in all_posts if p["author"].lower() == username.lower()]

    return fetcher
