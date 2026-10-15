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

try:
    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - tzdata missing on some images
    SHANGHAI_TZ = timezone(timedelta(hours=8))

LEDE_MAX = 80
SECTIONS_MAX = 8
BULLETS_MAX = 3
LINKS_MAX = 5
# Code default only (not a GitHub Secret). Live path uses Tencent LKEAP
# OpenAI-compatible POST {DAILY_BRIEF_API_BASE}/chat/completions.
# Boss-locked LKEAP model id — deepseek-v3 403s on this endpoint.
DEFAULT_MODEL = "deepseek/deepseek-flash"
MODEL_ENV = "DAILY_BRIEF_MODEL"
API_KEY_ENV = "DAILY_BRIEF_API_KEY"
API_BASE_ENV = "DAILY_BRIEF_API_BASE"

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

OTHER_TITLE = "其它"

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


def input_fingerprint(articles: list[dict[str, Any]]) -> str:
    """Stable hash of selected articles as fed into the LLM prompt grouping.

    Sorted by url; payload is url + title/summary/source (same fields as
    `_prompt_sections`). Same set the daily brief is built from.
    """
    rows = [
        {
            "url": article.get("url") or "",
            "title": article.get("title") or "",
            "summary": article.get("summary") or "",
            "source": article.get("source") or "",
        }
        for article in articles
    ]
    rows.sort(key=lambda row: row["url"])
    blob = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _earliest_title(articles: list[dict[str, Any]]) -> str:
    def key(article: dict[str, Any]) -> str:
        return article_list_time(article) or "9999"

    ordered = sorted(articles, key=key)
    title = (ordered[0].get("title") or "untitled").strip() if ordered else "untitled"
    return title[:80]


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
    for article in articles:
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
    """Group by topic_id; untopic'd articles become at most one 「其它」 section."""
    by_topic: dict[str, list[dict[str, Any]]] = {}
    other: list[dict[str, Any]] = []
    for article in articles:
        topic_id = article.get("topic_id")
        if isinstance(topic_id, str) and topic_id.strip():
            by_topic.setdefault(topic_id.strip(), []).append(article)
        else:
            other.append(article)

    ranked = sorted(
        by_topic.items(),
        key=lambda item: (
            -len(item[1]),
            min((article_list_time(a) or "9999") for a in item[1]),
        ),
    )
    topic_budget = SECTIONS_MAX - (1 if other else 0)
    sections: list[dict[str, Any]] = []
    for topic_id, group in ranked[: max(0, topic_budget)]:
        sections.append(
            {
                "topic_id": topic_id,
                "title": _earliest_title(group),
                "bullets": bullets_from_title_summary(group),
                "links": links_from_articles(group),
                "articles": group,
            }
        )
    if other:
        sections.append(
            {
                "topic_id": None,
                "title": OTHER_TITLE,
                "bullets": bullets_from_title_summary(other),
                "links": links_from_articles(other),
                "articles": other,
            }
        )
    return [s for s in sections if s.get("bullets") or s.get("links")][:SECTIONS_MAX]


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
    timeout: float = 45.0,
) -> dict[str, Any]:
    import httpx

    messages = [
        {
            "role": "system",
            "content": (
                "You write a concise Chinese daily news brief. Reply with JSON only: "
                '{"lede":"...","sections":[{"topic_id":null,"title":"...","bullets":["..."]}]}'
                " Use ONLY the given titles and summaries; do not invent facts. "
                f"lede ≤{LEDE_MAX} chars. ≤{SECTIONS_MAX} sections, 1–{BULLETS_MAX} bullets each. "
                f"Keep the given topic_id values. Untopic'd items stay in one section titled {OTHER_TITLE}."
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
    with httpx.Client(timeout=timeout) as client:
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
            if not isinstance(raw, dict):
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
    llm_fn: LlmFn | None = None,
    model: str = "",
    now: datetime | None = None,
    missing_config: bool = False,
) -> dict[str, Any]:
    """Build one daily brief. Never reads content_snapshot.

    empty: no active articles that Shanghai day
    failed: missing DAILY_BRIEF_API_KEY/BASE, model error, or unusable output
    ok: LLM returned a usable brief (links always from our grouping)
    """
    day_articles = articles_for_day(articles, date)
    fingerprint = input_fingerprint(day_articles)

    def _with_fp(brief: dict[str, Any]) -> dict[str, Any]:
        brief["input_fingerprint"] = fingerprint
        return brief

    if not day_articles:
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
    if not grouped:
        return _with_fp(empty_brief(date, now=now, model=model))

    try:
        llm_payload = llm_fn(grouped)
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
    if not lede and not sections:
        return _with_fp(
            failed_brief(date, error="LLM returned empty brief", now=now, model=model)
        )
    if not sections:
        sections = [public_section(s) for s in grouped if s.get("bullets")][:SECTIONS_MAX]
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

