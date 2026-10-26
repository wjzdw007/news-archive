"""科技/AI curated topic: RSS whitelist + keyword filter, merged with X.

Static Pages consume the merged feed. No LLM. NEWS_SOURCE_CAP stays 6
on the news tab; this module does not change ingest/display caps.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .sources import SOURCES
from .x_config import X_AI_BACKUP_ACCOUNTS, X_AI_PRIMARY_ACCOUNTS

TECH_AI_TOPIC_ID = "tech-ai"
TECH_AI_TITLE = "科技/AI"

# Prefer items from the last day; if that window is empty, fall back so the
# 专题 page is never a dead end.
WINDOW_HOURS = 24
FALLBACK_HOURS = 168  # 7 days
MAX_ITEMS = 100
# Knife #2: RSS MAX must not wipe X. Reserve 25% when X posts exist.
# Remaining slots go to RSS; list stays one chronological feed (mobile-friendly).
X_RESERVED_SLOTS = 25

# Dedicated tech / hard-tech / 科技商业 feeds: include recent items as-is.
TECH_AI_ALWAYS_SOURCES: frozenset[str] = frozenset(
    {
        "36kr",
        "tmtpost",
        "geekpark",
        "solidot",
        "ifanr",
        "verge",
        "wired",
        "techcrunch",
        "mit_tr",
        "bbc_technology",
        "nyt_technology",
        "guardian_technology",
        "ars_technica",
        "forbes_innovation",
    }
)

# Broader science / business feeds: title+summary must match AI keywords.
TECH_AI_KEYWORD_SOURCES: frozenset[str] = frozenset(
    {
        "bbc_science",
        "nyt_science",
        "guardian_science",
        "npr_science",
        "bbc_business",
        "nyt_business",
        "nyt_economy",
        "cnbc_top",
        "scmp_business",
        "ftchinese",
        "theconversation",
        "axios",
        "bloomberg_markets",
    }
)

TECH_AI_SOURCE_WHITELIST: frozenset[str] = TECH_AI_ALWAYS_SOURCES | TECH_AI_KEYWORD_SOURCES

# Tight EN set. Word-boundary / phrase only — no bare "ML".
AI_KEYWORDS_EN: tuple[str, ...] = (
    r"\bA\.?I\.?\b",
    r"\bAGI\b",
    r"\bLLM\b",
    r"\bLLMs\b",
    r"\bGPT(?:-[\w]+)?\b",
    r"\bOpenAI\b",
    r"\bAnthropic\b",
    r"\bClaude\b",
    r"\bGemini\b",
    r"\bDeepMind\b",
    r"\bxAI\b",
    r"\bGrok\b",
    r"\bChatGPT\b",
    r"\bCopilot\b",
    r"\bNvidia\b",
    r"\bHugging\s*Face\b",
    r"\bHuggingFace\b",
    r"machine learning",
    r"deep learning",
    r"neural network",
    r"foundation model",
    r"generative (?:AI|model)",
    r"\bMistral\b",
    r"\bCohere\b",
    r"\bKarpathy\b",
    r"\bLeCun\b",
    r"\bHassabis\b",
    r"Sam Altman",
    r"\bSora\b",
    r"\bDALL[- ]?E\b",
    r"\bDeepSeek\b",
)

# Tight CN set. Substring match (no word boundaries in CJK).
AI_KEYWORDS_ZH: tuple[str, ...] = (
    "人工智能",
    "生成式",
    "大模型",
    "大语言模型",
    "机器学习",
    "深度学习",
    "智能体",
    "算力",
    "英伟达",
    "深度求索",
    "通义",
    "文心",
    "豆包",
    "智谱",
    "月之暗面",
)

_AI_EN_RE = re.compile("|".join(AI_KEYWORDS_EN), re.IGNORECASE)

_SOURCE_IDS = {s.id for s in SOURCES}

_PRIMARY_KEYS = frozenset(a.lstrip("@").lower() for a in X_AI_PRIMARY_ACCOUNTS)
_BACKUP_KEYS = frozenset(a.lstrip("@").lower() for a in X_AI_BACKUP_ACCOUNTS)


def matches_ai_keywords(text: str | None) -> bool:
    """True when title/summary hits the tight CN+EN AI keyword set."""
    if not text:
        return False
    blob = str(text)
    if any(token in blob for token in AI_KEYWORDS_ZH):
        return True
    return _AI_EN_RE.search(blob) is not None


def article_on_topic(article: dict[str, Any]) -> bool:
    """Whitelist gate, plus keyword filter for broader sources."""
    source = (article.get("source") or "").strip()
    if source not in TECH_AI_SOURCE_WHITELIST:
        return False
    if source not in _SOURCE_IDS:
        return False
    if source in TECH_AI_ALWAYS_SOURCES:
        return True
    text = f"{article.get('title') or ''} {article.get('summary') or ''}"
    return matches_ai_keywords(text)


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if not isinstance(value, str):
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


def item_sort_at(item: dict[str, Any]) -> str:
    """published_at / posted_at, else fetched_at (same rule as news list)."""
    for key in ("published_at", "posted_at", "sort_at"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    fetched = item.get("fetched_at")
    if isinstance(fetched, str):
        return fetched.strip()
    return fetched or ""


def item_dt(item: dict[str, Any]) -> datetime | None:
    return parse_dt(item_sort_at(item))


def _author_key(author: str | None) -> str:
    return (author or "").strip().lstrip("@").lower()


def _in_window(item: dict[str, Any], start: datetime) -> bool:
    dt = item_dt(item)
    return dt is not None and dt >= start


def primary_authors_usable(
    posts: Iterable[dict[str, Any]],
    start: datetime,
) -> set[str]:
    """Primary X accounts that have an active, non-empty post in-window."""
    found: set[str] = set()
    for post in posts:
        key = _author_key(post.get("author"))
        if key not in _PRIMARY_KEYS:
            continue
        if (post.get("status") or "active") == "gone":
            continue
        if not str(post.get("text_snapshot") or "").strip():
            continue
        if _in_window(post, start):
            found.add(key)
    return found


def select_x_posts(
    posts: Iterable[dict[str, Any]],
    start: datetime,
    *,
    include_backups: bool,
    authors: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = set(authors) if authors is not None else set(_PRIMARY_KEYS)
    if include_backups:
        allowed |= set(_BACKUP_KEYS)
    out: list[dict[str, Any]] = []
    for post in posts:
        if _author_key(post.get("author")) not in allowed:
            continue
        if not str(post.get("text_snapshot") or "").strip():
            continue
        if _in_window(post, start):
            out.append(post)
    return out


def _rss_item(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "rss",
        "title": article.get("title") or "无标题",
        "url": article.get("url"),
        "source": article.get("source"),
        "summary": article.get("summary") or "",
        "published_at": article.get("published_at"),
        "fetched_at": article.get("fetched_at"),
        "status": article.get("status") or "active",
        "sort_at": item_sort_at(article),
    }


def _x_item(post: dict[str, Any]) -> dict[str, Any]:
    text = str(post.get("text_snapshot") or "").strip()
    title = text[:80] + ("…" if len(text) > 80 else "")
    author = (post.get("author") or "").strip().lstrip("@")
    return {
        "kind": "x",
        "title": title or "无内容",
        "url": post.get("url"),
        "source": f"@{author}" if author else "X",
        "author": author,
        "summary": text,
        "published_at": post.get("posted_at"),
        "fetched_at": post.get("fetched_at"),
        "status": post.get("status") or "active",
        "sort_at": item_sort_at(post),
    }


def empty_tech_ai_payload(*, now: datetime | None = None) -> dict[str, Any]:
    generated = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "topic_id": TECH_AI_TOPIC_ID,
        "title": TECH_AI_TITLE,
        "generated_at": generated,
        "window_hours": WINDOW_HOURS,
        "fallback_hours": FALLBACK_HOURS,
        "used_fallback": False,
        "used_x_backups": False,
        "rss_count": 0,
        "x_count": 0,
        "x_reserved_slots": X_RESERVED_SLOTS,
        "items": [],
    }


def tech_ai_topic_card(payload: dict[str, Any]) -> dict[str, Any]:
    """Card shape compatible with topics.json (status=ok so 专题 always lists it)."""
    items = payload.get("items") or []
    sources = [
        {"title": it.get("title") or "无标题", "url": it.get("url")}
        for it in items[:3]
        if it.get("url")
    ]
    return {
        "topic_id": payload.get("topic_id") or TECH_AI_TOPIC_ID,
        "title": payload.get("title") or TECH_AI_TITLE,
        "generated_at": payload.get("generated_at"),
        "status": "ok",
        "sources": sources,
        "article_urls": [
            it["url"] for it in items if it.get("kind") == "rss" and it.get("url")
        ],
        "kind": "curated",
        "item_count": len(items),
    }


def _collect_window(
    articles: Iterable[dict[str, Any]],
    posts: Iterable[dict[str, Any]],
    start: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    rss = [a for a in articles if article_on_topic(a) and _in_window(a, start)]
    used_backups = False
    x_posts = select_x_posts(posts, start, include_backups=False)
    if not primary_authors_usable(posts, start):
        backup_posts = select_x_posts(
            posts,
            start,
            include_backups=False,
            authors=_BACKUP_KEYS,
        )
        # Backups only when primaries are dead/unusable in this window.
        if backup_posts:
            x_posts = x_posts + backup_posts
            used_backups = True
    return rss, x_posts, used_backups


def build_tech_ai_page(
    articles: Iterable[dict[str, Any]],
    posts: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the public 科技/AI payload: RSS ∪ X, time-ordered, no snapshots."""
    now_dt = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    article_list = list(articles)
    post_list = list(posts)

    start_24 = now_dt - timedelta(hours=WINDOW_HOURS)
    rss, x_posts, used_backups = _collect_window(article_list, post_list, start_24)
    used_fallback = False
    window_hours = WINDOW_HOURS

    if not rss and not x_posts:
        start_fb = now_dt - timedelta(hours=FALLBACK_HOURS)
        rss, x_posts, used_backups = _collect_window(article_list, post_list, start_fb)
        used_fallback = True
        window_hours = FALLBACK_HOURS

    items = merge_reserved_feed(rss, x_posts)

    for item in items:
        item.pop("content_snapshot", None)
        item.pop("post_id", None)

    return {
        "topic_id": TECH_AI_TOPIC_ID,
        "title": TECH_AI_TITLE,
        "generated_at": now_dt.isoformat(),
        "window_hours": window_hours,
        "fallback_hours": FALLBACK_HOURS,
        "used_fallback": used_fallback,
        "used_x_backups": used_backups,
        "rss_count": sum(1 for it in items if it.get("kind") == "rss"),
        "x_count": sum(1 for it in items if it.get("kind") == "x"),
        "x_reserved_slots": X_RESERVED_SLOTS,
        "items": items,
    }


def merge_reserved_feed(
    rss: Iterable[dict[str, Any]],
    x_posts: Iterable[dict[str, Any]],
    *,
    max_items: int = MAX_ITEMS,
    x_reserved: int = X_RESERVED_SLOTS,
) -> list[dict[str, Any]]:
    """Chronological RSS∪X with reserved X slots so RSS MAX cannot zero X.

    When X posts exist, keep up to `x_reserved` newest X items and fill the
    rest with newest RSS. When X is empty, RSS may use the full MAX.
    """
    rss_items = [_rss_item(a) for a in rss]
    x_items = [_x_item(p) for p in x_posts]
    rss_items.sort(key=item_sort_at, reverse=True)
    x_items.sort(key=item_sort_at, reverse=True)

    if x_items:
        x_keep = x_items[: min(max(x_reserved, 0), max_items)]
        rss_keep = rss_items[: max(max_items - len(x_keep), 0)]
        items = rss_keep + x_keep
        items.sort(key=item_sort_at, reverse=True)
        return items
    return rss_items[:max_items]


def assert_whitelist_registered() -> list[str]:
    """Return whitelist ids missing from SOURCES (empty means OK)."""
    return sorted(TECH_AI_SOURCE_WHITELIST - _SOURCE_IDS)
