"""Stable article schema for AI-friendly archival."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["active", "gone"]


@dataclass(frozen=True)
class Article:
    title: str
    published_at: str | None  # ISO-8601 when available
    url: str
    summary: str | None
    source: str  # source id
    fetched_at: str  # ISO-8601 UTC
    content_snapshot: str | None  # RSS body snapshot for offline read
    status: Status = "active"

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
