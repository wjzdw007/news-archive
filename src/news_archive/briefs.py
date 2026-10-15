"""P2 minimal multi-source topic briefs via rule extraction (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Footer / nav / ads — must never enter bullets (product reject samples).
_FOOTER_NOISE = re.compile(
    r"(?i)\b("
    r"continue reading|read more|advertisement|subscribe now|sign up for|"
    r"cookie (policy|settings)|all rights reserved|terms of (use|service)"
    r")\b"
)

# Image caption / credit lead-ins (NYT-style reject sample).
_CAPTION_NOISE = re.compile(
    r"(?i)("
    r"^a photo (provided|shows|courtesy)|"
    r"^(photo|image|getty|reuters|ap|afp)\b|"
    r"\bphoto provided by\b|"
    r"\bshows president\b|"
    r"\bvisiting the .+ region\b|"  # e.g. Putin visiting the Sakhalin region…
    r"\bin this (file )?photo\b|"
    r"\bvia getty images\b"
    r")"
)


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_noise_bullet(text: str) -> bool:
    """True for caption / footer / nav lines that must not enter bullets."""
    t = text.strip()
    if not t:
        return True
    if _FOOTER_NOISE.search(t):
        return True
    if _CAPTION_NOISE.search(t):
        return True
    # Caption fragment after bad sentence split ("Putin visiting Sakhalin…")
    if re.search(r"(?i)^[A-Z][a-z]+ visiting the .+ in .+ (in )?(january|february|march|april|may|june|july|august|september|october|november|december)\b", t):
        return True
    return False


def extract_bullets(text: str | None, max_bullets: int = 3) -> list[str]:
    """Extract 1–3 short bullets; drop caption/footer noise; never invent facts."""
    if not text:
        return []
    clean = _strip_html(text)
    if not clean:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s*", clean)
    bullets: list[str] = []
    for part in parts:
        part = part.strip()
        if len(part) < 8:
            continue
        if is_noise_bullet(part):
            continue
        if len(part) > 200:
            part = part[:197] + "..."
        bullets.append(part)
        if len(bullets) >= max_bullets:
            break
    return bullets[:max_bullets]


def bullets_for_article(article: dict[str, Any], max_bullets: int = 3) -> list[str]:
    """Prefer snapshot, then summary; if filtered empty, fall back to title once.

    Never pad with caption/footer lines.
    """
    for field in ("content_snapshot", "summary"):
        bullets = extract_bullets(article.get(field), max_bullets=max_bullets)
        if bullets:
            return bullets
    title = (article.get("title") or "").strip()
    if title and not is_noise_bullet(title):
        return [title[:200]]
    return []


def _earliest_title(articles: list[dict[str, Any]]) -> str:
    def key(a: dict[str, Any]) -> str:
        return a.get("published_at") or "9999"

    ordered = sorted(articles, key=key)
    title = (ordered[0].get("title") or "untitled").strip()
    return title[:80]


def build_brief_for_topic(
    topic_id: str,
    articles: list[dict[str, Any]],
    *,
    force_fail: bool = False,
) -> dict[str, Any]:
    """Build one ok/failed brief dict for a multi-source topic."""
    now = datetime.now(timezone.utc).isoformat()
    if force_fail:
        return {
            "topic_id": topic_id,
            "title": _earliest_title(articles) if articles else "untitled",
            "sources": [],
            "article_urls": [a["url"] for a in articles],
            "generated_at": now,
            "model": "rules-v2",
            "status": "failed",
            "error": "forced failure for test",
        }

    by_source: dict[str, dict[str, Any]] = {}
    for a in sorted(articles, key=lambda x: x.get("published_at") or ""):
        src = a.get("source") or "unknown"
        if src in by_source:
            continue
        by_source[src] = {
            "source": src,
            "url": a["url"],
            "title": a.get("title") or "",
            "bullets": bullets_for_article(a),
        }

    sources = list(by_source.values())
    has_useful = any(s.get("bullets") for s in sources)
    return {
        "topic_id": topic_id,
        "title": _earliest_title(articles),
        "sources": sources,
        "article_urls": [a["url"] for a in articles],
        "generated_at": now,
        "model": "rules-v2",
        "status": "ok" if has_useful else "failed",
        "error": None if has_useful else "no usable bullets after noise filter",
    }


def topics_needing_briefs(
    articles_by_topic: dict[str, list[dict[str, Any]]],
    existing: dict[str, dict[str, Any]],
) -> list[str]:
    """Return topic_ids that need a new/updated brief."""
    need: list[str] = []
    for topic_id, arts in articles_by_topic.items():
        active = [a for a in arts if a.get("status") == "active"]
        sources = {a.get("source") for a in active}
        if len(sources) < 2:
            continue
        prev = existing.get(topic_id)
        if prev is None:
            need.append(topic_id)
            continue
        if prev.get("model") != "rules-v2":
            need.append(topic_id)
            continue
        prev_urls = set(prev.get("article_urls") or [])
        cur_urls = {a["url"] for a in active}
        if cur_urls - prev_urls:
            need.append(topic_id)
        elif prev.get("status") == "failed":
            need.append(topic_id)
    return need


def group_active_by_topic(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for a in articles:
        tid = a.get("topic_id")
        if not tid:
            continue
        out.setdefault(tid, []).append(a)
    return out
