"""X account list for news job (separate from AI-signal job)."""

from __future__ import annotations

# News first-cut accounts (product draft; CEO may trim). AI-signal job handles stay out.
# Ops: the Cookie login account must Follow these handles so HomeLatestTimeline /
# following can see them. Not a code secret; fetch path is unchanged.
X_NEWS_ACCOUNTS: list[str] = [
    "BBCChinese",
    "Reuters",
    "FT",
    "TechCrunch",
    "Tesla",
    "elonmusk",
    "AP",
]
