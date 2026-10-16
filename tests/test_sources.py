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

# CEO-approved business / tech RSS primaries
# (bbc_business ≠ bbc_world/bbc_technology/bbc_zh_simp; guardian_technology ≠ guardian_world).
_BIZ_TECH_PRIMARY = {
    "bbc_business": {
        "name": "BBC Business",
        "feed_url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "财经",
    },
    "guardian_technology": {
        "name": "Guardian Technology",
        "feed_url": "https://www.theguardian.com/uk/technology/rss",
        "category": "科技",
    },
    "ars_technica": {
        "name": "Ars Technica",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "硬科技",
    },
}

# CEO-approved business / science / tech RSS primaries
# (nyt_business ≠ nyt_world/nyt_technology; bbc_science ≠ bbc_world/bbc_technology/
# bbc_business/bbc_zh_simp; techcrunch is RSS id, distinct from X handle TechCrunch).
_BIZ_SCIENCE_TECH_PRIMARY = {
    "nyt_business": {
        "name": "NYT Business",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "category": "财经",
    },
    "bbc_science": {
        "name": "BBC Science",
        "feed_url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "category": "科学",
    },
    "techcrunch": {
        "name": "TechCrunch",
        "feed_url": "https://feeds.feedburner.com/TechCrunch",
        "category": "科技",
    },
}

# CEO-approved China / Asia / tech RSS primaries
# (economist_china is official China section, distinct from scmp_china;
# bbc_asia ≠ bbc_world/bbc_zh_simp/bbc_technology/bbc_business/bbc_science;
# verge is main-site RSS, distinct from verge_transport).
_CHINA_ASIA_TECH_PRIMARY = {
    "economist_china": {
        "name": "The Economist China",
        "feed_url": "https://www.economist.com/china/rss.xml",
        "category": "国际·中国",
    },
    "bbc_asia": {
        "name": "BBC Asia",
        "feed_url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        "category": "国际·亚太",
    },
    "verge": {
        "name": "The Verge",
        "feed_url": "https://www.theverge.com/rss/index.xml",
        "category": "科技",
    },
}

# CEO-approved Axios / NPR / Japan Times RSS primaries (batch8).
# These three are the new adds. Existing nyt_world / guardian_world stay
# as original P0 ids (distinct from nyt_business / nyt_technology and
# guardian_technology). axios uses api.axios.com/feed/ (not
# www.axios.com/feeds/feed.rss). npr_news is an RSS id, distinct from
# X handle NPR. japan_times is distinct from scmp_asia / bbc_asia.
# nikkei_asia is not registered (title+link only). sky_world is batch9.
_AXIOS_NPR_JAPAN_PRIMARY = {
    "axios": {
        "name": "Axios",
        "feed_url": "https://api.axios.com/feed/",
        "category": "综合",
    },
    "npr_news": {
        "name": "NPR News",
        "feed_url": "https://feeds.npr.org/1001/rss.xml",
        "category": "综合",
    },
    "japan_times": {
        "name": "Japan Times",
        "feed_url": "https://www.japantimes.co.jp/feed/",
        "category": "国际·亚太",
    },
}

# CEO-approved Sky / Le Monde / CBS RSS primaries (batch9).
# These three are the new adds. sky_world is distinct from bbc_world;
# lemonde is a new FR front-page feed; cbs_news is an RSS id, distinct
# from X handle CBSNews. bbc_europe is not registered (no backup).
# nikkei_asia stays unregistered (title+link only).
_SKY_LEMONDE_CBS_PRIMARY = {
    "sky_world": {
        "name": "Sky News World",
        "feed_url": "https://feeds.skynews.com/feeds/rss/world.xml",
        "category": "国际",
    },
    "lemonde": {
        "name": "Le Monde",
        "feed_url": "https://www.lemonde.fr/rss/une.xml",
        "category": "国际",
    },
    "cbs_news": {
        "name": "CBS News",
        "feed_url": "https://www.cbsnews.com/latest/rss/main",
        "category": "综合",
    },
}

_EXPECTED_PRIMARY_COUNT = 35
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


def test_biz_tech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_technology" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_business" in by_id
    assert by_id["bbc_business"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_business"].feed_url != by_id["bbc_technology"].feed_url
    assert by_id["bbc_business"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_technology"].feed_url != by_id["guardian_world"].feed_url
    for source_id, expected in _BIZ_TECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_biz_science_tech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert by_id["nyt_world"].feed_url == "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    assert by_id["nyt_technology"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
    )
    assert by_id["nyt_business"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_business"].feed_url != by_id["nyt_technology"].feed_url
    assert "bbc_world" in by_id
    assert "bbc_technology" in by_id
    assert "bbc_business" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_science" in by_id
    assert by_id["bbc_science"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_science"].feed_url != by_id["bbc_technology"].feed_url
    assert by_id["bbc_science"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["bbc_science"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "techcrunch" in by_id
    assert by_id["techcrunch"].id == "techcrunch"
    for source_id, expected in _BIZ_SCIENCE_TECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_china_asia_tech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "scmp_china" in by_id
    assert "economist_china" in by_id
    assert by_id["scmp_china"].feed_url == "https://www.scmp.com/rss/4/feed"
    assert by_id["economist_china"].feed_url != by_id["scmp_china"].feed_url
    assert "bbc_world" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_technology" in by_id
    assert "bbc_business" in by_id
    assert "bbc_science" in by_id
    assert "bbc_asia" in by_id
    assert by_id["bbc_asia"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_asia"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_asia"].feed_url != by_id["bbc_technology"].feed_url
    assert by_id["bbc_asia"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["bbc_asia"].feed_url != by_id["bbc_science"].feed_url
    assert "verge_transport" in by_id
    assert "verge" in by_id
    assert by_id["verge_transport"].feed_url == (
        "https://www.theverge.com/rss/transportation/index.xml"
    )
    assert by_id["verge"].feed_url != by_id["verge_transport"].feed_url
    for source_id, expected in _CHINA_ASIA_TECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_axios_npr_japan_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    # Existing original-P0 ids stay; they are not this batch's adds.
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_world"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_world"].feed_url != by_id["nyt_business"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_world"].feed_url != by_id["guardian_technology"].feed_url
    assert "axios" in by_id
    assert by_id["axios"].feed_url == "https://api.axios.com/feed/"
    assert by_id["axios"].feed_url != "https://www.axios.com/feeds/feed.rss"
    assert "npr_news" in by_id
    assert by_id["npr_news"].id == "npr_news"
    assert "scmp_asia" in by_id
    assert "bbc_asia" in by_id
    assert "japan_times" in by_id
    assert by_id["japan_times"].feed_url != by_id["scmp_asia"].feed_url
    assert by_id["japan_times"].feed_url != by_id["bbc_asia"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _AXIOS_NPR_JAPAN_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_sky_lemonde_cbs_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "sky_world" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["sky_world"].feed_url != by_id["bbc_world"].feed_url
    assert "lemonde" in by_id
    assert by_id["lemonde"].feed_url == "https://www.lemonde.fr/rss/une.xml"
    assert "cbs_news" in by_id
    assert by_id["cbs_news"].id == "cbs_news"
    # No backup Europe feed; this batch is RSS-only (X CBSNews/SkyNews untouched).
    assert "bbc_europe" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _SKY_LEMONDE_CBS_PRIMARY.items():
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


def test_biz_tech_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BIZ_TECH_PRIMARY:
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


def test_biz_science_tech_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BIZ_SCIENCE_TECH_PRIMARY:
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


def test_china_asia_tech_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _CHINA_ASIA_TECH_PRIMARY:
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


def test_axios_npr_japan_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _AXIOS_NPR_JAPAN_PRIMARY:
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
        if source_id == "japan_times":
            # #43 thin-skip: empty description would insert 0. Product lock
            # requires non-empty RSS description/summary on this feed.
            nonempty = 0
            for item in items:
                desc = (item.findtext("description") or "").strip()
                if desc:
                    nonempty += 1
            assert nonempty == len(items), (
                f"japan_times empty description: {len(items) - nonempty}/{len(items)}"
            )


def test_sky_lemonde_cbs_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _SKY_LEMONDE_CBS_PRIMARY:
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
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            desc = (item.findtext("description") or "").strip()
            if desc:
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


if __name__ == "__main__":
    test_source_ids_unique()
    test_source_counts()
    test_ev_hardtech_primaries_registered()
    test_intl_hardtech_primaries_registered()
    test_asia_tech_primaries_registered()
    test_china_tech_primaries_registered()
    test_biz_tech_primaries_registered()
    test_biz_science_tech_primaries_registered()
    test_china_asia_tech_primaries_registered()
    test_axios_npr_japan_primaries_registered()
    test_sky_lemonde_cbs_primaries_registered()
    test_rss_fetch_sends_browser_user_agent()
    test_asia_tech_feeds_live_http_200()
    test_china_tech_feeds_live_http_200()
    test_biz_tech_feeds_live_http_200()
    test_biz_science_tech_feeds_live_http_200()
    test_china_asia_tech_feeds_live_http_200()
    test_axios_npr_japan_feeds_live_http_200()
    test_sky_lemonde_cbs_feeds_live_http_200()
    print("✓ source registry tests PASSED")
