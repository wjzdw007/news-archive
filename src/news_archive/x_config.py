"""X account lists: news job + 科技/AI topic (same x-fetch workflow)."""

from __future__ import annotations

# News first-cut accounts (product draft; CEO may trim).
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
    "WSJ",
    "BBCWorld",
    "NPR",
    "nytimes",
    "TheEconomist",
    "SCMPNews",
    "Bloomberg",
    "WIRED",
    "AFP",
    "CNBC",
    "AJEnglish",
    "Nature",
    "SkyNews",
    "ABC",
    "CBSNews",
    "axios",
    "NikkeiAsia",
    "politico",
]

# CEO-approved 科技/AI primaries (same x-fetch + existing Bearer/cookies).
# Displayed on the 科技/AI 专题 page. Not a new RSS CAP batch.
X_AI_PRIMARY_ACCOUNTS: list[str] = [
    "OpenAI",
    "AnthropicAI",
    "xai",
    "elonmusk",
    "GoogleDeepMind",
    "AIatMeta",
    "nvidia",
    "huggingface",
    "karpathy",
    "sama",
    "demishassabis",
    "ylecun",
]

# Used on the 科技/AI page only when primaries have no usable in-window posts.
# Still fetched so the DB has them if a primary goes dark.
X_AI_BACKUP_ACCOUNTS: list[str] = [
    "AndrewYNg",
    "miramurati",
    "gdb",
    "MistralAI",
    "cohere",
]


def x_fetch_accounts() -> list[str]:
    """Union of news + AI primary + AI backup, case-insensitive, first casing wins."""
    seen: set[str] = set()
    out: list[str] = []
    for author in (
        X_NEWS_ACCOUNTS + X_AI_PRIMARY_ACCOUNTS + X_AI_BACKUP_ACCOUNTS
    ):
        key = author.lstrip("@").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(author)
    return out
