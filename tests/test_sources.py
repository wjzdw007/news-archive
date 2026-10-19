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
# from X handle CBSNews. bbc_europe is batch10 (primary, not a backup).
# nikkei_asia stays unregistered (title+link only). abc_news is batch11.
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

# CEO-approved DW / RFI / BBC Europe RSS primaries (batch10).
# These three are the new adds. dw_en is DW English all-news RDF (dense
# ~100+; NEWS_SOURCE_CAP display stays 6 — no CAP code change). rfi_en
# is RFI English. bbc_europe ≠ bbc_world / bbc_asia / bbc_zh_simp (now a
# primary, not an unused backup). abc_news is batch11 (primary, not a
# backup). nikkei_asia stays unregistered (title+link only). npr_world
# is batch12 (primary, not an unused backup).
_DW_RFI_BBC_EUROPE_PRIMARY = {
    "dw_en": {
        "name": "Deutsche Welle (EN)",
        "feed_url": "https://rss.dw.com/rdf/rss-en-all",
        "category": "国际",
    },
    "rfi_en": {
        "name": "RFI English",
        "feed_url": "https://www.rfi.fr/en/rss",
        "category": "国际",
    },
    "bbc_europe": {
        "name": "BBC Europe",
        "feed_url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
        "category": "国际",
    },
}

# CEO-approved ABC News / BBC US & Canada / WIRED RSS primaries (batch11).
# These three are the new adds. abc_news is ABC top stories (now a
# primary, not an unused backup). bbc_us_canada ≠ bbc_world / bbc_asia /
# bbc_europe / bbc_zh_simp. wired is WIRED magazine RSS, distinct from
# verge / ars_technica. npr_world is batch12 (primary, not an unused
# backup). nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
_ABC_BBC_US_WIRED_PRIMARY = {
    "abc_news": {
        "name": "ABC News",
        "feed_url": "https://abcnews.go.com/abcnews/topstories",
        "category": "综合",
    },
    "bbc_us_canada": {
        "name": "BBC US & Canada",
        "feed_url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
        "category": "国际",
    },
    "wired": {
        "name": "WIRED",
        "feed_url": "https://www.wired.com/feed/rss",
        "category": "科技",
    },
}

# CEO-approved NPR World / Guardian US / BBC Middle East RSS primaries
# (batch12). These three are the new adds. npr_world ≠ npr_news (World
# topic feed vs NPR News). guardian_us ≠ guardian_world /
# guardian_technology. bbc_middle_east ≠ bbc_world / bbc_asia /
# bbc_europe / bbc_us_canada / bbc_zh_simp. bbc_africa / nyt_science
# are batch13 (primaries, not unused backups). nikkei_asia stays
# unregistered (title+link only). NEWS_SOURCE_CAP display stays 6 —
# no CAP code change.
_NPR_GUARDIAN_US_BBC_ME_PRIMARY = {
    "npr_world": {
        "name": "NPR World",
        "feed_url": "https://feeds.npr.org/1004/rss.xml",
        "category": "国际",
    },
    "guardian_us": {
        "name": "Guardian US",
        "feed_url": "https://www.theguardian.com/us-news/rss",
        "category": "国际",
    },
    "bbc_middle_east": {
        "name": "BBC Middle East",
        "feed_url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
        "category": "国际",
    },
}

# CEO-approved BBC Africa / NYT Science / Guardian Environment RSS
# primaries (batch13). These three are the new adds. bbc_africa ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_zh_simp. nyt_science ≠ nyt_world / nyt_technology / nyt_business
# / bbc_science. guardian_environment ≠ guardian_world /
# guardian_technology / guardian_us. bbc_latin_america / nyt_climate /
# guardian_business are batch14 (primaries, not unused backups).
# nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
_BBC_AFRICA_NYT_SCIENCE_GUARDIAN_ENV_PRIMARY = {
    "bbc_africa": {
        "name": "BBC Africa",
        "feed_url": "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
        "category": "国际",
    },
    "nyt_science": {
        "name": "NYT Science",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        "category": "科学",
    },
    "guardian_environment": {
        "name": "Guardian Environment",
        "feed_url": "https://www.theguardian.com/environment/rss",
        "category": "科学",
    },
}

# CEO-approved BBC Latin America / NYT Climate / Guardian Business RSS
# primaries (batch14). These three are the new adds. bbc_latin_america ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_zh_simp. nyt_climate ≠ nyt_world / nyt_technology /
# nyt_business / nyt_science. guardian_business ≠ guardian_world /
# guardian_technology / guardian_us / guardian_environment and is
# distinct from bbc_business / nyt_business. bbc_health / nyt_health /
# straitstimes_world are batch15 (primaries, not unused backups).
# nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
# nyt_climate may have occasional empty description; #43 thin-skip
# handles that (no title-fill).
_BBC_LATAM_NYT_CLIMATE_GUARDIAN_BIZ_PRIMARY = {
    "bbc_latin_america": {
        "name": "BBC Latin America",
        "feed_url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
        "category": "国际",
    },
    "nyt_climate": {
        "name": "NYT Climate",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",
        "category": "科学",
    },
    "guardian_business": {
        "name": "Guardian Business",
        "feed_url": "https://www.theguardian.com/uk/business/rss",
        "category": "财经",
    },
}

# CEO-approved BBC Health / NYT Health / Straits Times World RSS
# primaries (batch15). These three are the new adds. bbc_health ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_zh_simp.
# nyt_health ≠ nyt_world / nyt_technology / nyt_business / nyt_science /
# nyt_climate. straitstimes_world is a new World feed, distinct from
# bbc_world / guardian_world / nyt_world / sky_world / japan_times.
# guardian_science / bbc_china / guardian_australia are batch16
# (primaries, not unused backups). nikkei_asia stays
# unregistered (title+link only). NEWS_SOURCE_CAP display stays 6 —
# no CAP code change. No X this batch.
_BBC_HEALTH_NYT_HEALTH_ST_WORLD_PRIMARY = {
    "bbc_health": {
        "name": "BBC Health",
        "feed_url": "https://feeds.bbci.co.uk/news/health/rss.xml",
        "category": "科学",
    },
    "nyt_health": {
        "name": "NYT Health",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
        "category": "科学",
    },
    "straitstimes_world": {
        "name": "Straits Times World",
        "feed_url": "https://www.straitstimes.com/news/world/rss.xml",
        "category": "国际",
    },
}

# CEO-approved Guardian Science / BBC China / Guardian Australia RSS
# primaries (batch16). These three are the new adds. guardian_science ≠
# bbc_science / nyt_science / guardian_environment / guardian_world /
# guardian_technology / guardian_us / guardian_business. bbc_china ≠
# bbc_world / bbc_asia / bbc_zh_simp / scmp_china / economist_china.
# guardian_australia ≠ guardian_world / guardian_us / guardian_science
# / japan_times / bbc_asia. bbc_education / guardian_americas /
# nyt_education are batch17 (primaries, not unused backups).
# nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
_GUARDIAN_SCIENCE_BBC_CHINA_GUARDIAN_AU_PRIMARY = {
    "guardian_science": {
        "name": "Guardian Science",
        "feed_url": "https://www.theguardian.com/science/rss",
        "category": "科学",
    },
    "bbc_china": {
        "name": "BBC China",
        "feed_url": "https://feeds.bbci.co.uk/news/world/asia/china/rss.xml",
        "category": "国际·中国",
    },
    "guardian_australia": {
        "name": "Guardian Australia",
        "feed_url": "https://www.theguardian.com/australia-news/rss",
        "category": "国际",
    },
}

# CEO-approved BBC Education / Guardian Americas / NYT Education RSS
# primaries (batch17). These three are the new adds. bbc_education ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health / bbc_china /
# bbc_zh_simp. guardian_americas ≠ guardian_world / guardian_us /
# guardian_science / guardian_australia / guardian_technology /
# guardian_business / guardian_environment / bbc_latin_america /
# bbc_us_canada. nyt_education ≠ nyt_world / nyt_technology /
# nyt_business / nyt_science / nyt_climate / nyt_health.
# guardian_uk / guardian_europe / nyt_politics are batch18
# (primaries, not unused backups). nikkei_asia stays
# unregistered (title+link only). NEWS_SOURCE_CAP display stays 6 —
# no CAP code change. No X this batch.
_BBC_EDU_GUARDIAN_AMERICAS_NYT_EDU_PRIMARY = {
    "bbc_education": {
        "name": "BBC Education",
        "feed_url": "https://feeds.bbci.co.uk/news/education/rss.xml",
        "category": "综合",
    },
    "guardian_americas": {
        "name": "Guardian Americas",
        "feed_url": "https://www.theguardian.com/world/americas/rss",
        "category": "国际",
    },
    "nyt_education": {
        "name": "NYT Education",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml",
        "category": "综合",
    },
}

# CEO-approved Guardian UK / Guardian Europe / NYT Politics RSS
# primaries (batch18). These three are the new adds. guardian_uk ≠
# guardian_world / guardian_us / guardian_americas / guardian_science /
# guardian_australia / guardian_technology / guardian_business /
# guardian_environment. guardian_europe ≠ guardian_world / guardian_uk /
# guardian_us / guardian_americas / guardian_science /
# guardian_australia / guardian_technology / guardian_business /
# guardian_environment / bbc_europe. nyt_politics ≠ nyt_world /
# nyt_technology / nyt_business / nyt_science / nyt_climate /
# nyt_health / nyt_education. bbc_uk / nyt_us / guardian_global_dev
# are batch19 (primaries, not unused backups). nikkei_asia stays
# unregistered (title+link only). NEWS_SOURCE_CAP display stays 6 —
# no CAP code change. No X this batch.
_GUARDIAN_UK_EUROPE_NYT_POLITICS_PRIMARY = {
    "guardian_uk": {
        "name": "Guardian UK",
        "feed_url": "https://www.theguardian.com/uk-news/rss",
        "category": "国际",
    },
    "guardian_europe": {
        "name": "Guardian Europe",
        "feed_url": "https://www.theguardian.com/world/europe-news/rss",
        "category": "国际",
    },
    "nyt_politics": {
        "name": "NYT Politics",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "category": "综合",
    },
}

# CEO-approved BBC UK / NYT US / Guardian Global Development RSS
# primaries (batch19). These three are the new adds. bbc_uk ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health / bbc_china /
# bbc_zh_simp / bbc_education. nyt_us ≠ nyt_world / nyt_technology /
# nyt_business / nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics. guardian_global_dev ≠ guardian_world / guardian_uk /
# guardian_us / guardian_americas / guardian_science /
# guardian_australia / guardian_technology / guardian_business /
# guardian_environment / guardian_europe. bbc_politics / nyt_europe /
# nyt_world_asia are batch20 (primaries, not unused backups).
# nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
_BBC_UK_NYT_US_GUARDIAN_GLOBAL_DEV_PRIMARY = {
    "bbc_uk": {
        "name": "BBC UK",
        "feed_url": "https://feeds.bbci.co.uk/news/uk/rss.xml",
        "category": "国际",
    },
    "nyt_us": {
        "name": "NYT US",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "category": "国际",
    },
    "guardian_global_dev": {
        "name": "Guardian Global Development",
        "feed_url": "https://www.theguardian.com/global-development/rss",
        "category": "国际",
    },
}

# CEO-approved BBC Politics / NYT Europe / NYT World Asia RSS
# primaries (batch20). These three are the new adds. bbc_politics ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health / bbc_china /
# bbc_zh_simp / bbc_education / bbc_uk. nyt_europe ≠ nyt_world /
# nyt_technology / nyt_business / nyt_science / nyt_climate /
# nyt_health / nyt_education / nyt_politics / nyt_us / bbc_europe /
# guardian_europe. nyt_world_asia ≠ nyt_world / nyt_europe / nyt_us /
# nyt_technology / nyt_business / nyt_science / nyt_climate /
# nyt_health / nyt_education / nyt_politics / bbc_asia / scmp_asia.
# guardian_law / guardian_society stay unregistered (unused backups;
# all three CEO-lock primaries passed smoke). nikkei_asia stays
# unregistered (title+link only). NEWS_SOURCE_CAP display stays 6 —
# no CAP code change. No X this batch.
_BBC_POLITICS_NYT_EUROPE_NYT_WORLD_ASIA_PRIMARY = {
    "bbc_politics": {
        "name": "BBC Politics",
        "feed_url": "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "category": "综合",
    },
    "nyt_europe": {
        "name": "NYT Europe",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml",
        "category": "国际",
    },
    "nyt_world_asia": {
        "name": "NYT World Asia",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml",
        "category": "国际·亚太",
    },
}

_EXPECTED_PRIMARY_COUNT = 68
_EXPECTED_CONTROL_COUNT = 1

# RSS 1.0 / RDF (dw_en) and Atom fallbacks for live XML probes.
_RSS10_ITEM = "{http://purl.org/rss/1.0/}item"
_RSS10_DESC = "{http://purl.org/rss/1.0/}description"
_ATOM_ENTRY = "{http://www.w3.org/2005/Atom}entry"
_ATOM_SUMMARY = "{http://www.w3.org/2005/Atom}summary"


def _feed_items(root: ET.Element) -> list[ET.Element]:
    items = root.findall(".//item")
    if items:
        return items
    rdf_items = root.findall(f".//{_RSS10_ITEM}")
    if rdf_items:
        return rdf_items
    return root.findall(f".//{_ATOM_ENTRY}")


def _item_description(item: ET.Element) -> str:
    return (
        (item.findtext("description") or "").strip()
        or (item.findtext(_RSS10_DESC) or "").strip()
        or (item.findtext("summary") or "").strip()
        or (item.findtext(_ATOM_SUMMARY) or "").strip()
    )


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
    # This batch is RSS-only (X CBSNews/SkyNews untouched). Unused backups stay out.
    assert "nikkei_asia" not in by_id
    for source_id, expected in _SKY_LEMONDE_CBS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_dw_rfi_bbc_europe_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_europe" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_europe"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_europe"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_europe"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "dw_en" in by_id
    assert by_id["dw_en"].feed_url == "https://rss.dw.com/rdf/rss-en-all"
    assert "rfi_en" in by_id
    assert by_id["rfi_en"].feed_url == "https://www.rfi.fr/en/rss"
    # Unused backup / title+link-only feeds stay unregistered.
    assert "nikkei_asia" not in by_id
    for source_id, expected in _DW_RFI_BBC_EUROPE_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_abc_bbc_us_wired_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_us_canada" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_us_canada"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_us_canada"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_us_canada"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_us_canada"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "abc_news" in by_id
    assert by_id["abc_news"].feed_url == "https://abcnews.go.com/abcnews/topstories"
    assert "wired" in by_id
    assert by_id["wired"].feed_url == "https://www.wired.com/feed/rss"
    assert "verge" in by_id
    assert "ars_technica" in by_id
    assert by_id["wired"].feed_url != by_id["verge"].feed_url
    assert by_id["wired"].feed_url != by_id["ars_technica"].feed_url
    # Unused backup / title+link-only feeds stay unregistered.
    assert "nikkei_asia" not in by_id
    for source_id, expected in _ABC_BBC_US_WIRED_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_npr_guardian_us_bbc_me_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "npr_news" in by_id
    assert "npr_world" in by_id
    assert by_id["npr_news"].feed_url == "https://feeds.npr.org/1001/rss.xml"
    assert by_id["npr_world"].feed_url != by_id["npr_news"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_us"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_us"].feed_url != by_id["guardian_technology"].feed_url
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_middle_east" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_middle_east"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_middle_east"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_middle_east"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_middle_east"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_middle_east"].feed_url != by_id["bbc_zh_simp"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _NPR_GUARDIAN_US_BBC_ME_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_africa_nyt_science_guardian_env_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_africa" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_africa"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_africa"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_africa"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_africa"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_africa"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_africa"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "bbc_science" in by_id
    assert "nyt_science" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_science"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_science"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_science"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_science"].feed_url != by_id["bbc_science"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_environment"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_environment"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_environment"].feed_url != by_id["guardian_us"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_AFRICA_NYT_SCIENCE_GUARDIAN_ENV_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_latam_nyt_climate_guardian_biz_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_latin_america" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_latin_america"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_climate"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_climate"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_climate"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_climate"].feed_url != by_id["nyt_science"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "bbc_business" in by_id
    assert "nyt_business" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_business"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_business"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_business"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_business"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_business"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["guardian_business"].feed_url != by_id["nyt_business"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_LATAM_NYT_CLIMATE_GUARDIAN_BIZ_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_health_nyt_health_st_world_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_science" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_health" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_health"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_health"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_health"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_health"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_health"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_health"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_health"].feed_url != by_id["nyt_climate"].feed_url
    assert "bbc_world" in by_id
    assert "guardian_world" in by_id
    assert "nyt_world" in by_id
    assert "sky_world" in by_id
    assert "japan_times" in by_id
    assert "straitstimes_world" in by_id
    assert by_id["straitstimes_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["straitstimes_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["straitstimes_world"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["straitstimes_world"].feed_url != by_id["sky_world"].feed_url
    assert by_id["straitstimes_world"].feed_url != by_id["japan_times"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_HEALTH_NYT_HEALTH_ST_WORLD_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_guardian_science_bbc_china_guardian_au_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_science" in by_id
    assert "nyt_science" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert by_id["guardian_science"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_science"].feed_url != by_id["guardian_business"].feed_url
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_zh_simp" in by_id
    assert "scmp_china" in by_id
    assert "economist_china" in by_id
    assert "bbc_china" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_china"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_china"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_china"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_china"].feed_url != by_id["scmp_china"].feed_url
    assert by_id["bbc_china"].feed_url != by_id["economist_china"].feed_url
    assert "guardian_australia" in by_id
    assert "japan_times" in by_id
    assert by_id["guardian_australia"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_australia"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_australia"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_australia"].feed_url != by_id["japan_times"].feed_url
    assert by_id["guardian_australia"].feed_url != by_id["bbc_asia"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _GUARDIAN_SCIENCE_BBC_CHINA_GUARDIAN_AU_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_edu_guardian_americas_nyt_edu_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_science" in by_id
    assert "bbc_health" in by_id
    assert "bbc_china" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_education" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_education"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_education"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_us" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_business" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_americas" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_americas"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["guardian_americas"].feed_url != by_id["bbc_us_canada"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert "nyt_education" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_education"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_education"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_education"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_education"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_education"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_education"].feed_url != by_id["nyt_health"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_EDU_GUARDIAN_AMERICAS_NYT_EDU_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_guardian_uk_europe_nyt_politics_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "guardian_world" in by_id
    assert "guardian_us" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_business" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_uk" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_uk"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_uk"].feed_url != by_id["guardian_environment"].feed_url
    assert "guardian_europe" in by_id
    assert "bbc_europe" in by_id
    assert by_id["guardian_europe"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_europe"].feed_url != by_id["bbc_europe"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert "nyt_education" in by_id
    assert "nyt_politics" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_politics"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_politics"].feed_url != by_id["nyt_education"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _GUARDIAN_UK_EUROPE_NYT_POLITICS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_uk_nyt_us_guardian_global_dev_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_science" in by_id
    assert "bbc_health" in by_id
    assert "bbc_china" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_education" in by_id
    assert "bbc_uk" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_uk"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_uk"].feed_url != by_id["bbc_education"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert "nyt_education" in by_id
    assert "nyt_politics" in by_id
    assert "nyt_us" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_us"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_us"].feed_url != by_id["nyt_politics"].feed_url
    assert "guardian_world" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_us" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_business" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_global_dev"].feed_url != by_id["guardian_europe"].feed_url
    # Title+link-only Nikkei RSS is not registered (would skip-insert under #43).
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_UK_NYT_US_GUARDIAN_GLOBAL_DEV_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_politics_nyt_europe_nyt_world_asia_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_science" in by_id
    assert "bbc_health" in by_id
    assert "bbc_china" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_education" in by_id
    assert "bbc_uk" in by_id
    assert "bbc_politics" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_politics"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_politics"].feed_url != by_id["bbc_uk"].feed_url
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_business" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert "nyt_education" in by_id
    assert "nyt_politics" in by_id
    assert "nyt_us" in by_id
    assert "nyt_europe" in by_id
    assert "bbc_europe" in by_id
    assert "guardian_europe" in by_id
    assert by_id["nyt_world"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    )
    assert by_id["nyt_europe"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["nyt_europe"].feed_url != by_id["guardian_europe"].feed_url
    assert "nyt_world_asia" in by_id
    assert "scmp_asia" in by_id
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["nyt_world_asia"].feed_url != by_id["scmp_asia"].feed_url
    # Unused backups / title+link-only feeds stay unregistered.
    assert "guardian_law" not in by_id
    assert "guardian_society" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_POLITICS_NYT_EUROPE_NYT_WORLD_ASIA_PRIMARY.items():
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


def test_dw_rfi_bbc_europe_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _DW_RFI_BBC_EUROPE_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_abc_bbc_us_wired_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _ABC_BBC_US_WIRED_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_npr_guardian_us_bbc_me_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NPR_GUARDIAN_US_BBC_ME_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bbc_africa_nyt_science_guardian_env_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_AFRICA_NYT_SCIENCE_GUARDIAN_ENV_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bbc_latam_nyt_climate_guardian_biz_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_LATAM_NYT_CLIMATE_GUARDIAN_BIZ_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        if source_id == "nyt_climate":
            # Occasional empty description is expected; #43 thin-skip
            # drops those items. Do not title-fill.
            assert nonempty > 0, f"{source_id} all descriptions empty"
        else:
            assert nonempty == len(items), (
                f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
            )


def test_bbc_health_nyt_health_st_world_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_HEALTH_NYT_HEALTH_ST_WORLD_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_guardian_science_bbc_china_guardian_au_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _GUARDIAN_SCIENCE_BBC_CHINA_GUARDIAN_AU_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bbc_edu_guardian_americas_nyt_edu_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_EDU_GUARDIAN_AMERICAS_NYT_EDU_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_guardian_uk_europe_nyt_politics_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _GUARDIAN_UK_EUROPE_NYT_POLITICS_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bbc_uk_nyt_us_guardian_global_dev_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_UK_NYT_US_GUARDIAN_GLOBAL_DEV_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bbc_politics_nyt_europe_nyt_world_asia_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_POLITICS_NYT_EUROPE_NYT_WORLD_ASIA_PRIMARY:
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
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        for i, item in enumerate(items):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            published = (
                (item.findtext("pubDate") or "").strip()
                or (item.findtext("published") or "").strip()
                or (item.findtext("updated") or "").strip()
            )
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product lock
        # requires non-empty RSS description/summary on these feeds.
        nonempty = 0
        for item in items:
            if _item_description(item):
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
    test_dw_rfi_bbc_europe_primaries_registered()
    test_abc_bbc_us_wired_primaries_registered()
    test_npr_guardian_us_bbc_me_primaries_registered()
    test_bbc_africa_nyt_science_guardian_env_primaries_registered()
    test_bbc_latam_nyt_climate_guardian_biz_primaries_registered()
    test_bbc_health_nyt_health_st_world_primaries_registered()
    test_guardian_science_bbc_china_guardian_au_primaries_registered()
    test_bbc_edu_guardian_americas_nyt_edu_primaries_registered()
    test_guardian_uk_europe_nyt_politics_primaries_registered()
    test_bbc_uk_nyt_us_guardian_global_dev_primaries_registered()
    test_bbc_politics_nyt_europe_nyt_world_asia_primaries_registered()
    test_rss_fetch_sends_browser_user_agent()
    test_asia_tech_feeds_live_http_200()
    test_china_tech_feeds_live_http_200()
    test_biz_tech_feeds_live_http_200()
    test_biz_science_tech_feeds_live_http_200()
    test_china_asia_tech_feeds_live_http_200()
    test_axios_npr_japan_feeds_live_http_200()
    test_sky_lemonde_cbs_feeds_live_http_200()
    test_dw_rfi_bbc_europe_feeds_live_http_200()
    test_abc_bbc_us_wired_feeds_live_http_200()
    test_npr_guardian_us_bbc_me_feeds_live_http_200()
    test_bbc_africa_nyt_science_guardian_env_feeds_live_http_200()
    test_bbc_latam_nyt_climate_guardian_biz_feeds_live_http_200()
    test_bbc_health_nyt_health_st_world_feeds_live_http_200()
    test_guardian_science_bbc_china_guardian_au_feeds_live_http_200()
    test_bbc_edu_guardian_americas_nyt_edu_feeds_live_http_200()
    test_guardian_uk_europe_nyt_politics_feeds_live_http_200()
    test_bbc_uk_nyt_us_guardian_global_dev_feeds_live_http_200()
    test_bbc_politics_nyt_europe_nyt_world_asia_feeds_live_http_200()
    print("✓ source registry tests PASSED")
