"""Per-source (or host) alternate article URLs for enrich.

When the primary GET hits 403 / 429 / timeout / empty body, try a small
ordered list of same-site entry points (AMP / mobile / www variants)
before counting that article as a hard soft-fail.

Add a new hard source by appending to SOURCE_ALTERNATES (and optionally
HOST_ALTERNATES). Do not expand this list in the fetch loop itself.
Cap is MAX_ALTERNATES_PER_ARTICLE so one article cannot drain the run budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse, urlunparse

MAX_ALTERNATES_PER_ARTICLE = 2

# Spend another GET on an alternate only for these primary/prior outcomes.
RETRYABLE_FOR_ALTERNATES = frozenset({"403", "429", "timeout", "empty_body"})


class AlternateStrategy(Protocol):
    def apply(self, url: str) -> str | None:
        """Return one alternate URL, or None when this strategy does not apply."""


def _parts(url: str):
    return urlparse(url)


def _rebuild(parsed, *, netloc: str | None = None, path: str | None = None) -> str:
    return urlunparse(
        (
            parsed.scheme,
            netloc if netloc is not None else parsed.netloc,
            path if path is not None else parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


@dataclass(frozen=True)
class AmpHtmlSuffix:
    """`/a/b.html` → `/a/b.amp.html`. Non-.html paths fall back to `/amp` prefix."""

    def apply(self, url: str) -> str | None:
        parsed = _parts(url)
        path = parsed.path or ""
        if path.endswith(".amp.html"):
            return None
        if path.endswith(".html"):
            new_path = path[: -len(".html")] + ".amp.html"
            return _rebuild(parsed, path=new_path)
        return AmpPathPrefix().apply(url)


@dataclass(frozen=True)
class AmpPathPrefix:
    """`https://host/story/x` → `https://host/amp/story/x`."""

    def apply(self, url: str) -> str | None:
        parsed = _parts(url)
        path = parsed.path or ""
        if not path or path == "/":
            return None
        if path == "/amp" or path.startswith("/amp/"):
            return None
        new_path = "/amp" + (path if path.startswith("/") else f"/{path}")
        return _rebuild(parsed, path=new_path)


@dataclass(frozen=True)
class AlternateHost:
    """Swap host when the current netloc is in `from_hosts` (or any host if empty)."""

    host: str
    from_hosts: frozenset[str] = frozenset()

    def apply(self, url: str) -> str | None:
        parsed = _parts(url)
        current = (parsed.netloc or "").lower()
        target = self.host.lower()
        if not current or current == target:
            return None
        if self.from_hosts and current not in {h.lower() for h in self.from_hosts}:
            return None
        return _rebuild(parsed, netloc=self.host)


# Ordered strategies per source id. First applicable distinct URL wins slots.
SOURCE_ALTERNATES: dict[str, tuple[AlternateStrategy, ...]] = {
    "nyt_world": (
        AmpHtmlSuffix(),
        AlternateHost(
            "mobile.nytimes.com",
            from_hosts=frozenset({"www.nytimes.com", "nytimes.com"}),
        ),
    ),
    "ftchinese": (
        AlternateHost(
            "m.ftchinese.com",
            from_hosts=frozenset({"www.ftchinese.com", "ftchinese.com"}),
        ),
        AmpPathPrefix(),
    ),
}

# Host fallback when `source` is missing/unknown but the URL is a known hard host.
HOST_ALTERNATES: dict[str, str] = {
    "www.nytimes.com": "nyt_world",
    "nytimes.com": "nyt_world",
    "mobile.nytimes.com": "nyt_world",
    "www.ftchinese.com": "ftchinese",
    "ftchinese.com": "ftchinese",
    "m.ftchinese.com": "ftchinese",
}


def _source_key(source: str, url: str) -> str | None:
    if source in SOURCE_ALTERNATES:
        return source
    host = (urlparse(url).netloc or "").lower()
    if host in HOST_ALTERNATES:
        return HOST_ALTERNATES[host]
    if host.startswith("www.") and host[4:] in HOST_ALTERNATES:
        return HOST_ALTERNATES[host[4:]]
    return None


def alternate_urls_for(*, url: str, source: str) -> list[str]:
    """Up to MAX_ALTERNATES_PER_ARTICLE distinct http(s) URLs, never including `url`."""
    key = _source_key(source, url)
    if key is None:
        return []
    strategies = SOURCE_ALTERNATES.get(key) or ()
    seen = {url}
    out: list[str] = []
    for strategy in strategies:
        alt = strategy.apply(url)
        if not alt or alt in seen:
            continue
        parsed = urlparse(alt)
        if parsed.scheme not in ("http", "https"):
            continue
        seen.add(alt)
        out.append(alt)
        if len(out) >= MAX_ALTERNATES_PER_ARTICLE:
            break
    return out
