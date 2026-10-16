"""Registry checks for RSS primary sources."""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from news_archive.fetch import RSS_HEADERS
from news_archive.sources import SOURCES

# CEO-approved EV / hard-tech RSS primaries (X Tesla/elonmusk is separate backlog).
_EV_HARDTECH_PRIMARY = {
    "electrek": {
        "name": "Electrek",
        "feed_url": "https://electrek.co/feed/",
        "category": "汽车·EV",
    },
    "insideevs": {
        "name": "InsideEVs",
        "feed_url": "https://insideevs.com/rss/news/all/",
        "category": "汽车·EV",
    },
    "verge_transport": {
        "name": "The Verge Transportation",
        "feed_url": "https://www.theverge.com/rss/transportation/index.xml",
        "category": "硬科技·出行",
    },
}

# CEO-approved international / hard-tech RSS primaries (distinct from bbc_zh_simp).
_INTL_HARDTECH_PRIMARY = {
    "scmp": {
        "name": "SCMP",
        "feed_url": "https://www.scmp.com/rss/2/feed",
        "category": "国际·亚太",
    },
    "mit_tr": {
        "name": "MIT Technology Review",
        "feed_url": "https://www.technologyreview.com/feed/",
        "category": "硬科技",
    },
    "bbc_world": {
        "name": "BBC World",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "国际",
    },
}

# CEO-approved Asia / tech RSS primaries (scmp_asia is distinct from Hong Kong scmp).
_ASIA_TECH_PRIMARY = {
    "scmp_asia": {
        "name": "SCMP Asia",
        "feed_url": "https://www.scmp.com/rss/3/feed",
        "category": "国际·亚太",
    },
    "solidot": {
        "name": "Solidot",
        "feed_url": "https://www.solidot.org/index.rss",
        "category": "科技",
    },
    "bbc_technology": {
        "name": "BBC Technology",
        "feed_url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "硬科技",
    },
}

# CEO-approved China / tech RSS primaries (scmp_china ≠ scmp/scmp_asia; nyt_technology ≠ nyt_world).
_CHINA_TECH_PRIMARY = {
    "scmp_china": {
        "name": "SCMP China",
        "feed_url": "https://www.scmp.com/rss/4/feed",
        "category": "国际·中国",
    },
    "nyt_technology": {
        "name": "NYT Technology",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "category": "硬科技",
    },
    "ifanr": {
        "name": "爱范儿",
        "feed_url": "https://www.ifanr.com/feed",
        "category": "科技",
    },
}

_EXPECTED_PRIMARY_COUNT = 20
_EXPECTED_CONTROL_COUNT = 1


def test_source_ids_unique():
    ids = [s.id for s in SOURCES]
    assert len(ids) == len(set(ids)), f"duplicate source ids: {ids}"


def test_source_counts():
    primaries = [s for s in SOURCES if s.role == "primary"]
    controls = [s for s in SOURCES if s.role == "control"]
    assert len(primaries) == _EXPECTED_PRIMARY_COUNT, (
        f"expected {_EXPECTED_PRIMARY_COUNT} primaries, got {len(primaries)}: "
        f"{[s.id for s in primaries]}"
    )
    assert len(controls) == _EXPECTED_CONTROL_COUNT, (
        f"expected {_EXPECTED_CONTROL_COUNT} control, got {len(controls)}: "
        f"{[s.id for s in controls]}"
    )
    assert len(SOURCES) == _EXPECTED_PRIMARY_COUNT + _EXPECTED_CONTROL_COUNT


def test_ev_hardtech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    for source_id, expected in _EV_HARDTECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_intl_hardtech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_zh_simp" in by_id
    assert by_id["bbc_world"].feed_url != by_id["bbc_zh_simp"].feed_url
    for source_id, expected in _INTL_HARDTECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_asia_tech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "scmp" in by_id
    assert "scmp_asia" in by_id
    assert by_id["scmp"].feed_url == "https://www.scmp.com/rss/2/feed"
    assert by_id["scmp_asia"].feed_url != by_id["scmp"].feed_url
    assert "bbc_technology" in by_id
    assert "bbc_world" in by_id
    assert by_id["bbc_technology"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_technology"].feed_url != by_id["bbc_zh_simp"].feed_url
    for source_id, expected in _ASIA_TECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_rss_fetch_sends_browser_user_agent():
    """Solidot 403s bare curl; live CI must send a browser UA on all RSS HTTP."""
    ua = RSS_HEADERS["User-Agent"]
    assert ua.startswith("Mozilla/5.0"), f"RSS User-Agent is not a browser UA: {ua!r}"
    assert "Chrome" in ua
    assert "news-archive/" not in ua


def test_china_tech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "scmp" in by_id
    assert "scmp_asia" in by_id
    assert "scmp_china" in by_id
    assert by_id["scmp"].feed_url == "https://www.scmp.com/rss/2/feed"
    assert by_id["scmp_asia"].feed_url == "https://www.scmp.com/rss/3/feed"
    assert by_id["scmp_china"].feed_url != by_id["scmp"].feed_url
    assert by_id["scmp_china"].feed_url != by_id["scmp_asia"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert by_id["nyt_world"].feed_url == "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    assert by_id["nyt_technology"].feed_url != by_id["nyt_world"].feed_url
    for source_id, expected in _CHINA_TECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_asia_tech_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _ASIA_TECH_PRIMARY:
        source = by_id[source_id]
        request = urllib.request.Request(source.feed_url, headers=RSS_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                status = resp.status
                body = resp.read()
        except urllib.error.HTTPError as exc:
            raise AssertionError(
                f"{source_id} {source.feed_url} HTTP {exc.code} with RSS_HEADERS"
            ) from exc
        assert status == 200, f"{source_id} HTTP {status}"
        assert body, f"{source_id} empty body"
        root = ET.fromstring(body)
        items = root.findall(".//item")
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        count = len(items) + len(entries)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"


def test_china_tech_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _CHINA_TECH_PRIMARY:
        source = by_id[source_id]
        request = urllib.request.Request(source.feed_url, headers=RSS_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                status = resp.status
                body = resp.read()
        except urllib.error.HTTPError as exc:
            raise AssertionError(
                f"{source_id} {source.feed_url} HTTP {exc.code} with RSS_HEADERS"
            ) from exc
        assert status == 200, f"{source_id} HTTP {status}"
        assert body, f"{source_id} empty body"
        root = ET.fromstring(body)
        items = root.findall(".//item")
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        count = len(items) + len(entries)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"


if __name__ == "__main__":
    test_source_ids_unique()
    test_source_counts()
    test_ev_hardtech_primaries_registered()
    test_intl_hardtech_primaries_registered()
    test_asia_tech_primaries_registered()
    test_china_tech_primaries_registered()
    test_rss_fetch_sends_browser_user_agent()
    test_asia_tech_feeds_live_http_200()
    test_china_tech_feeds_live_http_200()
    print("✓ source registry tests PASSED")
