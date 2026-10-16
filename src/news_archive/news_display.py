"""News Tab display-window helpers (Python mirror of site/app.js).

Used by the daily-fetch Job Summary so coverage/diversity reports the
same per-source cap the user actually sees. Do not change NEWS_SOURCE_CAP
here independently of site/app.js.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Keep in lockstep with site/app.js — tests assert both copies.
NEWS_DISPLAY_WINDOW = 50
NEWS_SOURCE_CAP = 6


def article_list_time(article: dict[str, Any]) -> str:
    """News list SORT key: published_at, else fetched_at (site/app.js)."""
    published = article.get("published_at")
    if isinstance(published, str) and published.strip():
        return published.strip()
    fetched = article.get("fetched_at")
    if isinstance(fetched, str):
        return fetched.strip()
    return str(fetched or "")


def is_newsflash(article: dict[str, Any]) -> bool:
    url = article.get("url")
    return isinstance(url, str) and "newsflashes" in url


def build_news_display_model(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Same placement rules as site/app.js `buildNewsDisplayModel`."""
    sorted_articles = sorted(articles, key=article_list_time, reverse=True)
    source_counts: dict[str, int] = {}
    top: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []

    def try_place(article: dict[str, Any]) -> None:
        src = article.get("source") or ""
        count = source_counts.get(src, 0)
        if len(top) < NEWS_DISPLAY_WINDOW and count < NEWS_SOURCE_CAP:
            top.append(article)
            source_counts[src] = count + 1
            return
        overflow.append(article)

    for article in sorted_articles:
        if not is_newsflash(article):
            try_place(article)
    for article in sorted_articles:
        if is_newsflash(article):
            try_place(article)

    top.sort(key=article_list_time, reverse=True)
    overflow.sort(key=article_list_time, reverse=True)
    return {"sorted": sorted_articles, "top": top, "overflow": overflow}


def _max_source(articles: list[dict[str, Any]]) -> tuple[int, str | None]:
    counts = Counter((article.get("source") or "") for article in articles)
    if not counts:
        return 0, None
    source, n = counts.most_common(1)[0]
    return n, source or None


def display_window_diversity(articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Same-source max in the News Tab display window vs raw time order.

    Primary metric is display-window (NEWS_SOURCE_CAP applied while filling
    the top-50). Raw published_at-order front-50 is diagnostic only.
    """
    model = build_news_display_model(articles)
    display_max, display_source = _max_source(model["top"])
    raw_front = model["sorted"][:NEWS_DISPLAY_WINDOW]
    raw_max, raw_source = _max_source(raw_front)
    return {
        "window": NEWS_DISPLAY_WINDOW,
        "cap": NEWS_SOURCE_CAP,
        "display_window_size": len(model["top"]),
        "display_max": display_max,
        "display_max_source": display_source,
        "raw_max": raw_max,
        "raw_max_source": raw_source,
    }
