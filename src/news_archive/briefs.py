"""P2 minimal multi-source topic briefs via rule extraction (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_bullets(text: str | None, max_bullets: int = 3) -> list[str]:
    """Extract 1–3 short bullets from snapshot/summary; never invent facts."""
    if not text:
        return []
    clean = _strip_html(text)
    if not clean:
        return []
    # Split on sentence boundaries (CJK + Latin)
    parts = re.split(r"(?<=[。！？.!?])\s*", clean)
    bullets: list[str] = []
    for part in parts:
        part = part.strip()
        if len(part) < 8:
            continue
        if len(part) > 200:
            part = part[:197] + "..."
        bullets.append(part)
        if len(bullets) >= max_bullets:
            break
    if not bullets and clean:
        bullets.append(clean[:200] + ("..." if len(clean) > 200 else ""))
    return bullets[:max_bullets]


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
            "model": "rules-v1",
            "status": "failed",
            "error": "forced failure for test",
        }

    # One block per source (first article by published_at per source)
    by_source: dict[str, dict[str, Any]] = {}
    for a in sorted(articles, key=lambda x: x.get("published_at") or ""):
        src = a.get("source") or "unknown"
        if src in by_source:
            continue
        body = a.get("content_snapshot") or a.get("summary")
        by_source[src] = {
            "source": src,
            "url": a["url"],
            "title": a.get("title") or "",
            "bullets": extract_bullets(body),
        }

    sources = list(by_source.values())
    return {
        "topic_id": topic_id,
        "title": _earliest_title(articles),
        "sources": sources,
        "article_urls": [a["url"] for a in articles],
        "generated_at": now,
        "model": "rules-v1",
        "status": "ok",
        "error": None,
    }


def topics_needing_briefs(
    articles_by_topic: dict[str, list[dict[str, Any]]],
    existing: dict[str, dict[str, Any]],
) -> list[str]:
    """Return topic_ids that need a new/updated brief.

    Rules: ≥2 distinct sources among active articles; skip single-source;
    generate if no brief or article set grew vs last brief's article_urls.
    """
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
        prev_urls = set(prev.get("article_urls") or [])
        cur_urls = {a["url"] for a in active}
        if not cur_urls.issubset(prev_urls) or cur_urls != prev_urls:
            # New article(s) since last brief
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
