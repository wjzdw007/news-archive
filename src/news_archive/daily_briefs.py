"""Daily briefs from title+summary only (never content_snapshot).

One row per Asia/Shanghai calendar day. Soft-fail: missing LLM key, model
errors, or an empty day write status=failed|empty and must not raise into
fetch/deploy.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .briefs import extract_bullets, is_noise_bullet
from .clustering import jaccard_similarity, normalize_title
from .sources import SOURCES
from .x_config import X_NEWS_ACCOUNTS

try:
    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - tzdata missing on some images
    SHANGHAI_TZ = timezone(timedelta(hours=8))

LEDE_MAX = 80
SECTIONS_MAX = 8
BULLETS_MAX = 3
LINKS_MAX = 5
X_LINKS_MAX = 8
# Truncate x_posts.text_snapshot before LLM/fingerprint (SQLite field only).
X_TEXT_SNAPSHOT_MAX = 400
# Code default only (not a GitHub Secret). Live path uses Tencent LKEAP
# OpenAI-compatible POST {DAILY_BRIEF_API_BASE}/chat/completions.
# Boss-locked LKEAP model id — deepseek-v3 403s on this endpoint.
DEFAULT_MODEL = "deepseek/deepseek-flash"
MODEL_ENV = "DAILY_BRIEF_MODEL"
API_KEY_ENV = "DAILY_BRIEF_API_KEY"
API_BASE_ENV = "DAILY_BRIEF_API_BASE"
# Run 40258264336: a 45s read timeout on one LKEAP call, then more 45s
# misses, burned the 300s CLI deadline and skipped remaining days.
# Today gets retries; older days stay one-shot so they cannot starve today.
LLM_READ_TIMEOUT_S = 90.0
LLM_CONNECT_TIMEOUT_S = 15.0
LLM_WRITE_TIMEOUT_S = 30.0
LLM_POOL_TIMEOUT_S = 10.0
TODAY_LLM_ATTEMPTS = 3
OLDER_LLM_ATTEMPTS = 1
LLM_RETRY_BACKOFF_S = 2.0

# Public/LLM article fields. content_snapshot is intentionally absent.
DAILY_BRIEF_ARTICLE_FIELDS = (
    "url",
    "title",
    "published_at",
    "summary",
    "source",
    "fetched_at",
    "status",
    "topic_id",
)

# Public/LLM X fields from SQLite x_posts only. Never post_id / cookies / Authorization.
DAILY_BRIEF_X_FIELDS = (
    "author",
    "text_snapshot",
    "url",
    "posted_at",
)

OTHER_TITLE = "其它"
X_SECTION_TITLE = "X 动态"
# Documented constant (not an RSS cluster id). Avoids colliding with 「其它」(null).
X_SECTION_TOPIC_ID = "x-daily"
# Bust kept_ok once so ranking/merge/X-filter calibration regenerates ok rows.
BRIEF_CALIBRATION = "hard-news-v1"
# Leave room in the 8-section cap for archive tech / 其它 when hard news is plentiful.
HARD_SECTION_RESERVE = 2

_SOURCE_CATEGORY = {source.id: source.category for source in SOURCES}

# Personality / company accounts stay on the X tab; they crowd the brief.
_SOFT_X_AUTHORS = frozenset({"tesla", "elonmusk"})
_X_WIRE_AUTHORS = frozenset(
    {
        "reuters",
        "ap",
        "afp",
        "bbcworld",
        "bbcchinese",
        "nytimes",
        "wsj",
        "ft",
        "theeconomist",
        "scmpnews",
        "ajenglish",
        "skynews",
        "npr",
        "bloomberg",
        "cbsnews",
        "abc",
        "axios",
        "politico",
        "nikkeiasia",
        "nature",
    }
)
_SOFT_X_PROMO_RE = re.compile(
    r"(?i)\b(just launched|congrats(?: to)?|follow us|subscribe now|giveaway)\b"
)
_HARD_NEWS_RE = re.compile(
    r"(?i)("
    r"\b(?:stampede|earthquake|aftershock|tsunami|typhoon|hurricane|cyclone|"
    r"wildfire|floods?|landslide|explosion|airstrike|air strike|missile|"
    r"ceasefire|sanctions?|coup|massacre|hostage|shooting|terrorist|"
    r"invasion|casualt(?:y|ies)|killed|killing|deaths?)\b|"
    r"踩踏|地震|海啸|台风|飓风|洪水|山火|爆炸|空袭|导弹|停火|制裁|"
    r"政变|屠杀|人质|枪击|恐袭|入侵|遇难|死亡"
    r")"
)
_STORY_STOPWORDS = frozenset(
    {
        "after",
        "from",
        "with",
        "that",
        "this",
        "have",
        "been",
        "were",
        "will",
        "over",
        "more",
        "than",
        "into",
        "just",
        "about",
        "could",
        "would",
        "today",
        "yesterday",
        "latest",
        "update",
        "news",
        "says",
        "said",
        "report",
        "reports",
        "live",
        "video",
        "watch",
        "least",
        "dozens",
        "people",
        "kills",
        "killed",
        "dead",
        "death",
        "dies",
        "died",
        "toll",
        "rising",
        "rises",
        "amid",
        "near",
        "south",
        "north",
        "east",
        "west",
        "world",
        "china",
        "chinese",
        "india",
        "indian",
        "japan",
        "japanese",
        "russia",
        "russian",
        "united",
        "states",
        "officials",
        "announced",
        "breaking",
    }
)
# Event-type aliases (not distinctive on their own). CJK/EN same-story merge.
_EVENT_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stampede", ("crush", "踩踏")),
    ("earthquake", ("quake", "地震")),
    ("typhoon", ("hurricane", "cyclone", "台风", "飓风")),
    ("explosion", ("blast", "爆炸")),
    ("ceasefire", ("truce", "停火")),
    ("protest", ("protests", "抗议")),
    ("election", ("elections", "选举")),
    ("sanction", ("sanctions", "制裁")),
)
# Place / entity aliases (distinctive). Thin list; expand only when a split story lands.
_ENTITY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kolkata", ("calcutta", "加尔各答")),
    ("spacex", ("space x",)),
)
_GENERIC_EVENT_TOKENS = frozenset(canonical for canonical, _alts in _EVENT_ALIASES)
_BRIEF_STORY_JACCARD = 0.32

LlmFn = Callable[[list[dict[str, Any]]], dict[str, Any]]


def shanghai_now(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI_TZ)


def shanghai_calendar_date(now: datetime | None = None) -> str:
    return shanghai_now(now).date().isoformat()


def last_n_shanghai_dates(n: int = 7, now: datetime | None = None) -> list[str]:
    today = shanghai_now(now).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n)]


def order_dates_today_first(dates: list[str], today: str | None = None) -> list[str]:
    """Stable unique order with the current Shanghai day first."""
    today = today or shanghai_calendar_date()
    head: list[str] = []
    tail: list[str] = []
    seen: set[str] = set()
    for date in dates:
        if date in seen:
            continue
        seen.add(date)
        if date == today:
            head.append(date)
        else:
            tail.append(date)
    return head + tail


_BACKFILL_STATUSES = frozenset({"failed", "empty", "skipped"})


def prioritize_failed_backfill(
    dates: list[str],
    today: str,
    status_for_date,
) -> list[str]:
    """Today first, then failed/empty/missing historical days, then the rest.

    Live 2026-10-25/24/23/21 stayed failed after today's timeout burned the
    old 300s budget. After today is generated (with retries), spend remaining
    time regenerating those failed rows — not re-touching already-ok days.
    """
    ordered = order_dates_today_first(dates, today=today)
    head = [date for date in ordered if date == today]
    rest = [date for date in ordered if date != today]
    failed: list[str] = []
    others: list[str] = []
    for date in rest:
        status = status_for_date(date)
        if status in _BACKFILL_STATUSES or not status:
            failed.append(date)
        else:
            others.append(date)
    return head + failed + others


def is_retryable_llm_error(error: str | None) -> bool:
    """Timeouts / transient upstream errors are retried for today only."""
    text = (error or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if "missing" in lowered and (
        API_KEY_ENV.lower() in lowered or API_BASE_ENV.lower() in lowered
    ):
        return False
    needles = (
        "timed out",
        "timeout",
        "temporar",
        "429",
        "500",
        "502",
        "503",
        "504",
        "connect",
        "reset",
        "unavailable",
        "read operation",
        "write operation",
        "connection aborted",
        "remote protocol",
        "ssl",
    )
    return any(needle in lowered for needle in needles)


def today_status_is_success(status: str | None) -> bool:
    """ok and empty are valid today outcomes. failed/skipped/missing are not."""
    return status in {"ok", "empty"}


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def article_list_time(article: dict[str, Any]) -> str:
    published = article.get("published_at")
    if isinstance(published, str) and published.strip():
        return published.strip()
    fetched = article.get("fetched_at")
    if isinstance(fetched, str) and fetched.strip():
        return fetched.strip()
    return ""


def article_shanghai_date(article: dict[str, Any]) -> str | None:
    dt = parse_iso_datetime(article_list_time(article))
    if dt is None:
        return None
    return dt.astimezone(SHANGHAI_TZ).date().isoformat()


def public_article(article: dict[str, Any]) -> dict[str, Any]:
    """Copy allowlisted fields only — never content_snapshot."""
    return {field: article.get(field) for field in DAILY_BRIEF_ARTICLE_FIELDS}


def articles_for_day(articles: list[dict[str, Any]], date: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for article in articles:
        if article.get("status") != "active":
            continue
        if article_shanghai_date(article) != date:
            continue
        out.append(public_article(article))
    return out


def truncate_x_text(text: str | None, max_len: int = X_TEXT_SNAPSHOT_MAX) -> str:
    clipped = re.sub(r"\s+", " ", (text or "").strip())
    if len(clipped) > max_len:
        return clipped[: max_len - 3] + "..."
    return clipped


def public_x_post(post: dict[str, Any]) -> dict[str, Any]:
    """Allowlisted x_posts fields only — never post_id / cookies / Authorization."""
    posted_at = post.get("posted_at")
    if not isinstance(posted_at, str):
        posted_at = ""
    return {
        "author": (post.get("author") or "").strip().lstrip("@"),
        "text_snapshot": truncate_x_text(post.get("text_snapshot")),
        "url": (post.get("url") or "").strip(),
        "posted_at": posted_at.strip(),
    }


def x_post_shanghai_date(post: dict[str, Any]) -> str | None:
    posted_at = post.get("posted_at")
    if not isinstance(posted_at, str):
        return None
    dt = parse_iso_datetime(posted_at)
    if dt is None:
        return None
    return dt.astimezone(SHANGHAI_TZ).date().isoformat()


def is_soft_x_post(post: dict[str, Any]) -> bool:
    """True for personality/promo X noise that should not enter the daily brief."""
    author = (post.get("author") or "").strip().lstrip("@").lower()
    if author in _SOFT_X_AUTHORS:
        return True
    text = (post.get("text_snapshot") or "").strip()
    if not text:
        return True
    if _SOFT_X_PROMO_RE.search(text) and not _HARD_NEWS_RE.search(text):
        return True
    return False


def x_posts_for_day(
    posts: list[dict[str, Any]],
    date: str,
    accounts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Active same-day X posts (Asia/Shanghai from posted_at), public fields only.

    Soft X (Tesla / elonmusk / promo) is dropped here so brief selection and
    `input_fingerprint` stay aligned. Wire accounts sort first.
    """
    allowed = {a.lstrip("@").lower() for a in (accounts or X_NEWS_ACCOUNTS)}
    out: list[dict[str, Any]] = []
    for post in posts or []:
        status = post.get("status")
        if status not in (None, "active"):
            continue
        author = (post.get("author") or "").strip().lstrip("@")
        if author.lower() not in allowed:
            continue
        if x_post_shanghai_date(post) != date:
            continue
        pub = public_x_post({**post, "author": author})
        if not pub["url"] and not pub["text_snapshot"]:
            continue
        if is_soft_x_post(pub):
            continue
        out.append(pub)
    out.sort(
        key=lambda p: (
            0 if (p.get("author") or "").strip().lstrip("@").lower() in _X_WIRE_AUTHORS else 1,
            p.get("posted_at") or "",
            p.get("url") or "",
            p.get("author") or "",
        )
    )
    return out


def daily_brief_fingerprint_input(
    articles: list[dict[str, Any]],
    date: str,
    x_posts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Shanghai-day selected set hashed by `input_fingerprint`.

    Includes RSS public articles and X public posts (author, truncated
    text_snapshot, url, posted_at). Same-day X add/remove/edit changes this.
    """
    return {
        "date": date,
        "articles": articles_for_day(articles, date),
        "x_posts": x_posts_for_day(x_posts or [], date),
    }


def input_fingerprint(
    articles: list[dict[str, Any]],
    x_posts: list[dict[str, Any]] | None = None,
) -> str:
    """Stable hash of selected RSS + X sets the daily brief is built from.

    RSS: url + title/summary/source (same fields as `_prompt_sections`).
    X: public selected set from `x_posts_for_day` / `daily_brief_fingerprint_input`.
    """
    article_rows = [
        {
            "url": article.get("url") or "",
            "title": article.get("title") or "",
            "summary": article.get("summary") or "",
            "source": article.get("source") or "",
        }
        for article in articles
    ]
    article_rows.sort(key=lambda row: row["url"])
    x_rows = [public_x_post(post) for post in (x_posts or [])]
    x_rows.sort(key=lambda row: (row["url"], row["posted_at"], row["author"]))
    blob = json.dumps(
        {"articles": article_rows, "v": BRIEF_CALIBRATION, "x_posts": x_rows},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def day_input_fingerprint(
    articles: list[dict[str, Any]],
    date: str,
    x_posts: list[dict[str, Any]] | None = None,
) -> str:
    selected = daily_brief_fingerprint_input(articles, date, x_posts)
    return input_fingerprint(selected["articles"], selected["x_posts"])


def is_x_section(section: dict[str, Any] | None) -> bool:
    if not isinstance(section, dict):
        return False
    topic_id = section.get("topic_id")
    if topic_id is not None and str(topic_id).strip() == X_SECTION_TOPIC_ID:
        return True
    if (section.get("title") or "").strip() == X_SECTION_TITLE:
        return True
    if section.get("x_posts"):
        return True
    return False


def links_from_x_posts(
    posts: list[dict[str, Any]], max_links: int = X_LINKS_MAX
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for post in posts:
        url = (post.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = truncate_x_text(post.get("text_snapshot"), 80) or url
        links.append(
            {
                "title": title,
                "url": url,
                "source": (post.get("author") or "").strip(),
            }
        )
        if len(links) >= max_links:
            break
    return links


def bullets_from_x_posts(
    posts: list[dict[str, Any]], max_bullets: int = BULLETS_MAX
) -> list[str]:
    """1–3 multi-account highlights, not one bullet per post."""
    if not posts:
        return []
    by_author: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        author = (post.get("author") or "").strip()
        by_author.setdefault(author, []).append(post)
    if len(by_author) == 1:
        combined = " ".join(
            truncate_x_text(p.get("text_snapshot")) for p in posts if p.get("text_snapshot")
        )
        extracted = extract_bullets(combined, max_bullets=max_bullets)
        if extracted:
            return extracted[:max_bullets]
    bullets: list[str] = []
    for author, group in by_author.items():
        clip = truncate_x_text(group[0].get("text_snapshot"), 160)
        if not clip:
            continue
        bullets.append(f"@{author}：{clip}" if author else clip)
        if len(bullets) >= max_bullets:
            break
    if bullets:
        return bullets[:max_bullets]
    authors = [a for a in by_author if a]
    if authors:
        names = "、".join(f"@{a}" for a in authors[:4])
        return [f"当日 {len(posts)} 条来自 {names}"]
    return []


def build_x_section(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not posts:
        return None
    bullets = bullets_from_x_posts(posts)
    links = links_from_x_posts(posts)
    if not bullets and not links:
        return None
    return {
        "topic_id": X_SECTION_TOPIC_ID,
        "title": X_SECTION_TITLE,
        "bullets": bullets,
        "links": links,
        "x_posts": posts,
    }


def public_x_section(
    section: dict[str, Any],
    llm_section: dict[str, Any] | None = None,
) -> dict[str, Any]:
    posts = section.get("x_posts") or []
    llm_section = llm_section if isinstance(llm_section, dict) else {}
    bullets = clip_bullets(llm_section.get("bullets") or section.get("bullets"))
    if not bullets:
        bullets = bullets_from_x_posts(posts)
    return {
        "topic_id": X_SECTION_TOPIC_ID,
        "title": X_SECTION_TITLE,
        "bullets": bullets[:BULLETS_MAX],
        "links": links_from_x_posts(posts)[:X_LINKS_MAX],
    }


def llm_x_section(llm_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(llm_payload, dict) or not isinstance(llm_payload.get("sections"), list):
        return None
    titled: dict[str, Any] | None = None
    for raw in llm_payload["sections"]:
        if not isinstance(raw, dict):
            continue
        topic_id = raw.get("topic_id")
        if topic_id is not None and str(topic_id).strip() == X_SECTION_TOPIC_ID:
            return raw
        if (raw.get("title") or "").strip() == X_SECTION_TITLE:
            titled = raw
    return titled


def source_category(source: str | None) -> str:
    return _SOURCE_CATEGORY.get((source or "").strip(), "")


def article_news_tier(article: dict[str, Any]) -> int:
    """0 = hard news, 1 = serious tech/finance archive, 2 = soft tech/other."""
    title = article.get("title") or ""
    summary = article.get("summary") or ""
    if _HARD_NEWS_RE.search(f"{title} {summary}"):
        return 0
    category = source_category(article.get("source"))
    if category.startswith(("国际", "综合")):
        return 0
    if category.startswith(("财经", "官方", "硬科技", "科学")):
        return 1
    return 2


def article_brief_weight(article: dict[str, Any]) -> int:
    category = source_category(article.get("source"))
    if category.startswith(("国际", "综合")):
        weight = 8
    elif category.startswith(("财经", "官方")):
        weight = 6
    elif category.startswith(("硬科技", "科学")):
        weight = 5
    elif category.startswith(("科技", "汽车")):
        weight = 2
    else:
        weight = 3
    title = article.get("title") or ""
    summary = article.get("summary") or ""
    if _HARD_NEWS_RE.search(f"{title} {summary}"):
        weight += 10
    return weight


def _order_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        articles,
        key=lambda article: (
            -article_brief_weight(article),
            article_list_time(article) or "",
            article.get("url") or "",
        ),
    )


def _preferred_title(articles: list[dict[str, Any]]) -> str:
    ordered = _order_articles(articles)
    title = (ordered[0].get("title") or "untitled").strip() if ordered else "untitled"
    return title[:80]


def _earliest_title(articles: list[dict[str, Any]]) -> str:
    return _preferred_title(articles)


def _article_story_text(article: dict[str, Any]) -> str:
    title = article.get("title") or ""
    summary = (article.get("summary") or "")[:80]
    return f"{title} {summary}".strip()


def story_tokens(text: str) -> set[str]:
    raw = text or ""
    low = raw.lower()
    tokens = {word for word in re.findall(r"[a-z]{4,}", low) if word not in _STORY_STOPWORDS}
    alt_forms: set[str] = set()
    for canonical, alts in _EVENT_ALIASES + _ENTITY_ALIASES:
        matched = canonical in tokens or canonical in low
        for alt in alts:
            alt_low = alt.lower()
            if alt in raw or alt_low in low:
                matched = True
            if alt.isascii():
                alt_forms.add(alt_low.replace(" ", ""))
        if matched:
            tokens.add(canonical)
    tokens -= alt_forms
    tokens -= _STORY_STOPWORDS
    return tokens


def stories_should_merge(
    articles_a: list[dict[str, Any]], articles_b: list[dict[str, Any]]
) -> bool:
    """Same-story merge for one Shanghai day. Does not widen the calendar window."""
    for left in articles_a:
        for right in articles_b:
            title_a = left.get("title") or ""
            title_b = right.get("title") or ""
            shared = story_tokens(_article_story_text(left)) & story_tokens(
                _article_story_text(right)
            )
            if len(shared) >= 2:
                return True
            similarity = jaccard_similarity(normalize_title(title_a), normalize_title(title_b))
            distinctive = {token for token in shared if token not in _GENERIC_EVENT_TOKENS}
            if distinctive and similarity >= _BRIEF_STORY_JACCARD:
                return True
    return False


def _group_tier(articles: list[dict[str, Any]]) -> int:
    return min((article_news_tier(article) for article in articles), default=2)


def _group_rank_key(articles: list[dict[str, Any]]) -> tuple:
    score = sum(article_brief_weight(article) for article in articles)
    n_sources = len({article.get("source") or "" for article in articles})
    earliest = min((article_list_time(article) or "9999") for article in articles)
    return (_group_tier(articles), -score, -n_sources, -len(articles), earliest)


def _synthetic_hard_topic_id(articles: list[dict[str, Any]]) -> str:
    url = (_order_articles(articles)[0].get("url") or "x") if articles else "x"
    return "hard-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _merge_story_groups(
    groups: list[tuple[str | None, list[dict[str, Any]]]],
) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """Greedy same-story merge across topic_id. Same-source pairs may merge."""
    if len(groups) < 2:
        return groups
    ordered = sorted(groups, key=lambda item: _group_rank_key(item[1]))
    merged: list[tuple[str | None, list[dict[str, Any]]]] = []
    for topic_id, articles in ordered:
        attached = False
        for index, (keep_id, keep_articles) in enumerate(merged):
            if stories_should_merge(keep_articles, articles):
                if _group_rank_key(articles) < _group_rank_key(keep_articles):
                    merged[index] = (topic_id, keep_articles + articles)
                else:
                    keep_articles.extend(articles)
                    merged[index] = (keep_id, keep_articles)
                attached = True
                break
        if not attached:
            merged.append((topic_id, list(articles)))
    return merged


def _allocate_section_groups(
    groups: list[tuple[str | None, list[dict[str, Any]]]],
    budget: int,
) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """Rank hard news first; reserve slots for archive tech when present."""
    if budget <= 0 or not groups:
        return []
    ranked = sorted(groups, key=lambda item: _group_rank_key(item[1]))
    hard = [item for item in ranked if _group_tier(item[1]) == 0]
    rest = [item for item in ranked if _group_tier(item[1]) != 0]
    reserved = min(HARD_SECTION_RESERVE, len(rest), budget)
    hard_budget = budget - reserved
    picked = hard[:hard_budget]
    picked.extend(rest[: budget - len(picked)])
    if len(picked) < budget:
        picked_ids = {id(item) for item in picked}
        picked.extend(item for item in hard[hard_budget:] if id(item) not in picked_ids)
    return picked[:budget]


def _build_section(topic_id: str | None, articles: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = _order_articles(articles)
    return {
        "topic_id": topic_id,
        "title": _preferred_title(ordered),
        "bullets": bullets_from_title_summary(ordered),
        "links": links_from_articles(ordered),
        "articles": ordered,
    }


def bullets_from_title_summary(
    articles: list[dict[str, Any]], max_bullets: int = BULLETS_MAX
) -> list[str]:
    """1–3 bullets from title + summary only. Never reads content_snapshot."""
    bullets: list[str] = []
    seen: set[str] = set()
    for article in articles:
        for piece in extract_bullets(article.get("summary"), max_bullets=max_bullets):
            if piece in seen:
                continue
            seen.add(piece)
            bullets.append(piece)
            if len(bullets) >= max_bullets:
                return bullets
    if bullets:
        return bullets[:max_bullets]
    for article in articles:
        title = (article.get("title") or "").strip()
        if title and not is_noise_bullet(title):
            return [title[:200]]
    return []


def links_from_articles(
    articles: list[dict[str, Any]], max_links: int = LINKS_MAX
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for article in _order_articles(articles):
        url = (article.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        links.append(
            {
                "title": (article.get("title") or "").strip() or url,
                "url": url,
                "source": (article.get("source") or "").strip(),
            }
        )
        if len(links) >= max_links:
            break
    return links


def group_sections(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group by topic_id, merge same-story clusters, rank hard news first.

    Untopic'd hard news becomes its own section (not buried in 「其它」).
    Soft untopic'd items remain at most one 「其它」 section, always last.
    """
    by_topic: dict[str, list[dict[str, Any]]] = {}
    untopic: list[dict[str, Any]] = []
    for article in articles:
        topic_id = article.get("topic_id")
        if isinstance(topic_id, str) and topic_id.strip():
            by_topic.setdefault(topic_id.strip(), []).append(article)
        else:
            untopic.append(article)

    groups: list[tuple[str | None, list[dict[str, Any]]]] = [
        (topic_id, group) for topic_id, group in by_topic.items()
    ]

    leftover_untopic: list[dict[str, Any]] = []
    for article in untopic:
        attached = False
        for _topic_id, group in groups:
            if stories_should_merge(group, [article]):
                group.append(article)
                attached = True
                break
        if not attached:
            leftover_untopic.append(article)

    groups = _merge_story_groups(groups)

    hard_untopic: list[dict[str, Any]] = []
    soft_other: list[dict[str, Any]] = []
    for article in leftover_untopic:
        if article_news_tier(article) == 0:
            hard_untopic.append(article)
        else:
            soft_other.append(article)

    hard_clusters: list[tuple[str | None, list[dict[str, Any]]]] = []
    for article in hard_untopic:
        placed = False
        for _topic_id, cluster in hard_clusters:
            if stories_should_merge(cluster, [article]):
                cluster.append(article)
                placed = True
                break
        if not placed:
            hard_clusters.append((_synthetic_hard_topic_id([article]), [article]))
    groups.extend(hard_clusters)

    other = soft_other
    topic_budget = SECTIONS_MAX - (1 if other else 0)
    selected = _allocate_section_groups(groups, max(0, topic_budget))

    sections: list[dict[str, Any]] = [
        _build_section(topic_id, group) for topic_id, group in selected
    ]
    if other:
        sections.append(_build_section(None, other))
        sections[-1]["title"] = OTHER_TITLE
    return [
        section for section in sections if section.get("bullets") or section.get("links")
    ][:SECTIONS_MAX]


def clip_lede(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:LEDE_MAX]


def clip_bullets(items: Any, max_n: int = BULLETS_MAX) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        if not text:
            continue
        if len(text) > 200:
            text = text[:197] + "..."
        out.append(text)
        if len(out) >= max_n:
            break
    return out


def public_section(section: dict[str, Any]) -> dict[str, Any]:
    topic_id = section.get("topic_id")
    if topic_id is not None:
        topic_id = str(topic_id).strip() or None
    title = (section.get("title") or "").strip() or OTHER_TITLE
    bullets = clip_bullets(section.get("bullets"))
    if not bullets:
        bullets = bullets_from_title_summary(section.get("articles") or [])
    links = section.get("links") or links_from_articles(section.get("articles") or [])
    if not isinstance(links, list):
        links = []
    cleaned_links: list[dict[str, str]] = []
    for link in links[:LINKS_MAX]:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "").strip()
        if not url:
            continue
        cleaned_links.append(
            {
                "title": str(link.get("title") or "").strip() or url,
                "url": url,
                "source": str(link.get("source") or "").strip(),
            }
        )
    return {
        "topic_id": topic_id,
        "title": title[:80],
        "bullets": bullets[:BULLETS_MAX],
        "links": cleaned_links[:LINKS_MAX],
    }


def empty_brief(date: str, *, now: datetime | None = None, model: str = "") -> dict[str, Any]:
    return {
        "date": date,
        "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "status": "empty",
        "model": model or "",
        "lede": "",
        "sections": [],
        "error": None,
    }


def failed_brief(
    date: str,
    *,
    error: str,
    now: datetime | None = None,
    model: str = "",
) -> dict[str, Any]:
    return {
        "date": date,
        "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "status": "failed",
        "model": model or "",
        "lede": "",
        "sections": [],
        "error": error,
    }


def redact_secrets(text: str, *secrets: str) -> str:
    """Strip secret values from logs/errors. Names are ok; values are not."""
    out = str(text or "")
    for secret in secrets:
        if secret:
            out = out.replace(secret, "***")
    out = re.sub(r"(?i)(bearer\s+)\S+", r"\1***", out)
    out = re.sub(r"(?i)(api[_-]?key\s*[=:]\s*)\S+", r"\1***", out)
    return out


def resolve_model(env: dict[str, str] | None = None) -> str:
    """LKEAP model id: env DAILY_BRIEF_MODEL if set, else deepseek/deepseek-flash."""
    source = env if env is not None else os.environ
    override = (source.get(MODEL_ENV) or "").strip()
    return override or DEFAULT_MODEL


def resolve_llm_config(
    env: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """Return live LLM config or None if key or base is missing (soft-fail)."""
    source = env if env is not None else os.environ
    key = (source.get(API_KEY_ENV) or "").strip()
    base_url = (source.get(API_BASE_ENV) or "").strip()
    if not key or not base_url:
        return None
    return {
        "api_key": key,
        "model": resolve_model(source),
        "base_url": base_url.rstrip("/"),
    }


def _prompt_sections(grouped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for section in grouped:
        if is_x_section(section):
            payload.append(
                {
                    "topic_id": X_SECTION_TOPIC_ID,
                    "title": X_SECTION_TITLE,
                    "x_posts": [
                        public_x_post(post) for post in (section.get("x_posts") or [])
                    ],
                }
            )
            continue
        payload.append(
            {
                "topic_id": section.get("topic_id"),
                "title": section.get("title"),
                "articles": [
                    {
                        "title": article.get("title"),
                        "summary": article.get("summary"),
                        "source": article.get("source"),
                        "url": article.get("url"),
                    }
                    for article in (section.get("articles") or [])
                ],
            }
        )
    return payload


def openai_complete(
    grouped: list[dict[str, Any]],
    *,
    api_key: str,
    model: str,
    base_url: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    import httpx

    messages = [
        {
            "role": "system",
            "content": (
                "You write a concise Chinese daily news brief. Reply with JSON only: "
                '{"lede":"...","sections":[{"topic_id":null,"title":"...","bullets":["..."]}]}'
                " Use ONLY the given titles and summaries for RSS; do not invent facts. "
                "Prioritize hard news (disasters, geopolitics, conflict, elections) over product "
                "launches and social chatter. Keep one section per story; do not split the same event. "
                f"lede ≤{LEDE_MAX} chars. ≤{SECTIONS_MAX} RSS sections, 1–{BULLETS_MAX} bullets each. "
                f"Keep the given topic_id values. Untopic'd soft RSS items stay in one section titled {OTHER_TITLE}. "
                f"If a section titled {X_SECTION_TITLE} is present, keep that exact title and "
                f'topic_id "{X_SECTION_TOPIC_ID}"; write 1–{BULLETS_MAX} bullets as multi-account '
                "highlights (not one bullet per post); use ONLY that section's author, "
                "text_snapshot, url, posted_at. Treat that X section as supplementary, not the lead, "
                "when RSS hard news is present. Do not merge X posts into RSS topic_id clusters."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"sections": _prompt_sections(grouped)}, ensure_ascii=False),
        },
    ]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": messages,
    }
    url = f"{base_url}/chat/completions"
    read_timeout = LLM_READ_TIMEOUT_S if timeout is None else float(timeout)
    client_timeout = httpx.Timeout(
        connect=LLM_CONNECT_TIMEOUT_S,
        read=read_timeout,
        write=LLM_WRITE_TIMEOUT_S,
        pool=LLM_POOL_TIMEOUT_S,
    )
    with httpx.Client(timeout=client_timeout) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"]
    parsed = _parse_llm_json(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON was not an object")
    return parsed


def _parse_llm_json(content: str) -> Any:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def merge_llm_sections(
    grouped: list[dict[str, Any]],
    llm_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_id: dict[str | None, dict[str, Any]] = {}
    if isinstance(llm_payload, dict) and isinstance(llm_payload.get("sections"), list):
        for raw in llm_payload["sections"]:
            if not isinstance(raw, dict) or is_x_section(raw):
                continue
            topic_id = raw.get("topic_id")
            if topic_id is not None:
                topic_id = str(topic_id).strip() or None
            by_id[topic_id] = raw
    merged: list[dict[str, Any]] = []
    for section in grouped:
        topic_id = section.get("topic_id")
        llm_section = by_id.get(topic_id, {})
        merged.append(
            public_section(
                {
                    "topic_id": topic_id,
                    "title": llm_section.get("title") or section.get("title"),
                    "bullets": llm_section.get("bullets") or section.get("bullets"),
                    "links": section.get("links"),
                    "articles": section.get("articles"),
                }
            )
        )
    return [s for s in merged if s["bullets"]][:SECTIONS_MAX]


def generate_daily_brief(
    articles: list[dict[str, Any]],
    date: str,
    *,
    x_posts: list[dict[str, Any]] | None = None,
    llm_fn: LlmFn | None = None,
    model: str = "",
    now: datetime | None = None,
    missing_config: bool = False,
) -> dict[str, Any]:
    """Build one daily brief. Never reads content_snapshot.

    empty: no active articles and no same-day X posts that Shanghai day
    failed: missing DAILY_BRIEF_API_KEY/BASE, model error, or unusable output
    ok: LLM returned a usable brief (RSS links from grouping; X links from x_posts)
    Same-day X posts become at most one 「X 动态」 section (omitted when none).
    """
    selected = daily_brief_fingerprint_input(articles, date, x_posts)
    day_articles = selected["articles"]
    day_x = selected["x_posts"]
    fingerprint = input_fingerprint(day_articles, day_x)

    def _with_fp(brief: dict[str, Any]) -> dict[str, Any]:
        brief["input_fingerprint"] = fingerprint
        return brief

    if not day_articles and not day_x:
        return _with_fp(empty_brief(date, now=now, model=model))

    if missing_config or llm_fn is None:
        return _with_fp(
            failed_brief(
                date,
                error=f"missing {API_KEY_ENV} or {API_BASE_ENV}",
                now=now,
                model=model,
            )
        )

    grouped = group_sections(day_articles)
    x_section = build_x_section(day_x)
    if not grouped and not x_section:
        return _with_fp(empty_brief(date, now=now, model=model))

    prompt_grouped = list(grouped)
    if x_section:
        prompt_grouped.append(x_section)

    try:
        llm_payload = llm_fn(prompt_grouped)
    except Exception as exc:
        return _with_fp(
            failed_brief(
                date, error=redact_secrets(str(exc)), now=now, model=model
            )
        )

    if not isinstance(llm_payload, dict):
        return _with_fp(
            failed_brief(date, error="LLM returned non-object JSON", now=now, model=model)
        )

    lede = clip_lede(llm_payload.get("lede"))
    sections = merge_llm_sections(grouped, llm_payload)
    if not sections and grouped:
        sections = [public_section(s) for s in grouped if s.get("bullets")][:SECTIONS_MAX]
    if x_section:
        x_pub = public_x_section(x_section, llm_x_section(llm_payload))
        if x_pub.get("bullets") or x_pub.get("links"):
            sections.append(x_pub)
    if not lede and not sections:
        return _with_fp(
            failed_brief(date, error="LLM returned empty brief", now=now, model=model)
        )
    if not lede:
        titles = [s["title"] for s in sections[:3] if s.get("title")]
        lede = clip_lede("；".join(titles))

    return _with_fp(
        {
            "date": date,
            "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
            "status": "ok",
            "model": model or resolve_model(),
            "lede": lede,
            "sections": sections,
            "error": None,
        }
    )


def make_llm_fn(config: dict[str, str]) -> LlmFn:
    def _fn(grouped: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            return openai_complete(
                grouped,
                api_key=config["api_key"],
                model=config["model"],
                base_url=config["base_url"],
            )
        except Exception as exc:
            raise RuntimeError(
                redact_secrets(str(exc), config.get("api_key") or "")
            ) from None

    return _fn


def assert_no_snapshot_leak(payload: Any) -> None:
    """Raise if a content_snapshot key appears anywhere in a JSON-able payload."""
    blob = json.dumps(payload, ensure_ascii=False)
    if "content_snapshot" in blob:
        raise ValueError("content_snapshot must not appear in daily brief payloads")

