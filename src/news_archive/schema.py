"""Stable article schema for AI-friendly archival."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["active", "gone"]

# Public Pages / validate contract: summary is at most 280 Unicode chars.
PUBLIC_SUMMARY_MAX = 280


def title_as_summary(title: str | None) -> str | None:
    """Trimmed title used when RSS description is empty. Never exceeds 280 chars."""
    if title is None:
        return None
    text = str(title).strip()
    if not text:
        return None
    if len(text) > PUBLIC_SUMMARY_MAX:
        return text[:PUBLIC_SUMMARY_MAX]
    return text


@dataclass(frozen=True)
class Article:
    title: str
    published_at: str | None  # ISO-8601 when available
    url: str
    summary: str | None
    source: str  # source id
    fetched_at: str  # ISO-8601 UTC
    content_snapshot: str | None  # private body snapshot; never exported to Pages
    status: Status = "active"
    topic_id: str | None = None  # UUID for clustering same-event articles

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def required_fields() -> tuple[str, ...]:
        return (
            "title",
            "published_at",
            "url",
            "summary",
            "source",
            "fetched_at",
            "content_snapshot",
            "status",
        )
