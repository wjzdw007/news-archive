"""Registry checks for RSS primary sources."""

from __future__ import annotations

import gzip
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
# guardian_law are batch20 (primaries, not unused backups).
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

# CEO-approved BBC Politics / NYT Europe / Guardian Law RSS
# primaries (batch20). bbc_politics / nyt_europe stay as-is.
# guardian_law replaces nyt_world_asia after daily-fetch RED
# (AsiaPacific feed fetched items already in DB — url dedupe,
# insert 0). bbc_politics ≠ bbc_world / bbc_asia / bbc_europe /
# bbc_us_canada / bbc_middle_east / bbc_africa /
# bbc_latin_america / bbc_science / bbc_health / bbc_china /
# bbc_zh_simp / bbc_education / bbc_uk. nyt_europe ≠ nyt_world /
# nyt_technology / nyt_business / nyt_science / nyt_climate /
# nyt_health / nyt_education / nyt_politics / nyt_us / bbc_europe /
# guardian_europe. guardian_law ≠ guardian_world / guardian_uk /
# guardian_us / guardian_americas / guardian_science /
# guardian_australia / guardian_technology / guardian_business /
# guardian_environment / guardian_europe / guardian_global_dev.
# nyt_world_asia is unregistered (replaced). guardian_society /
# bbc_scotland / guardian_cities are batch21 (primaries, not unused
# backups). nikkei_asia stays unregistered (title+link only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
_BBC_POLITICS_NYT_EUROPE_GUARDIAN_LAW_PRIMARY = {
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
    "guardian_law": {
        "name": "Guardian Law",
        "feed_url": "https://www.theguardian.com/law/rss",
        "category": "综合",
    },
}

# CEO-approved Guardian Society / BBC Scotland / Guardian Cities RSS
# primaries (batch21). These three are the new adds. guardian_society ≠
# guardian_world / guardian_uk / guardian_us / guardian_americas /
# guardian_science / guardian_australia / guardian_technology /
# guardian_business / guardian_environment / guardian_europe /
# guardian_global_dev / guardian_law. bbc_scotland ≠ bbc_world /
# bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health /
# bbc_china / bbc_zh_simp / bbc_education / bbc_uk / bbc_politics.
# guardian_cities ≠ guardian_world / guardian_uk / guardian_us /
# guardian_americas / guardian_science / guardian_australia /
# guardian_technology / guardian_business / guardian_environment /
# guardian_europe / guardian_global_dev / guardian_law /
# guardian_society. guardian_world_africa / guardian_politics /
# bbc_wales are batch22 (primaries, not unused backups).
# nikkei_asia stays unregistered (title+link only).
# nyt_world_asia stays unregistered (replaced in batch20).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change. No X this batch.
_GUARDIAN_SOCIETY_BBC_SCOTLAND_GUARDIAN_CITIES_PRIMARY = {
    "guardian_society": {
        "name": "Guardian Society",
        "feed_url": "https://www.theguardian.com/society/rss",
        "category": "综合",
    },
    "bbc_scotland": {
        "name": "BBC Scotland",
        "feed_url": "https://feeds.bbci.co.uk/news/scotland/rss.xml",
        "category": "综合",
    },
    "guardian_cities": {
        "name": "Guardian Cities",
        "feed_url": "https://www.theguardian.com/cities/rss",
        "category": "综合",
    },
}

# CEO-approved Guardian World Africa / Guardian Politics / BBC Wales RSS
# primaries (batch22). These three are the new adds. guardian_world_africa ≠
# guardian_world / guardian_uk / guardian_us / guardian_americas /
# guardian_science / guardian_australia / guardian_technology /
# guardian_business / guardian_environment / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / bbc_africa. guardian_politics ≠ guardian_world /
# guardian_uk / guardian_us / guardian_americas / guardian_science /
# guardian_australia / guardian_technology / guardian_business /
# guardian_environment / guardian_europe / guardian_global_dev /
# guardian_law / guardian_society / guardian_cities /
# guardian_world_africa / bbc_politics / nyt_politics. bbc_wales ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health /
# bbc_china / bbc_zh_simp / bbc_education / bbc_uk / bbc_politics /
# bbc_scotland. bbc_england / nyt_upshot / france24_en are batch23
# (primaries, not unused backups). nikkei_asia stays unregistered
# (title+link only). nyt_world_asia stays unregistered (replaced in
# batch20). NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_GUARDIAN_WORLD_AFRICA_GUARDIAN_POLITICS_BBC_WALES_PRIMARY = {
    "guardian_world_africa": {
        "name": "Guardian World Africa",
        "feed_url": "https://www.theguardian.com/world/africa/rss",
        "category": "国际",
    },
    "guardian_politics": {
        "name": "Guardian Politics",
        "feed_url": "https://www.theguardian.com/politics/rss",
        "category": "综合",
    },
    "bbc_wales": {
        "name": "BBC Wales",
        "feed_url": "https://feeds.bbci.co.uk/news/wales/rss.xml",
        "category": "综合",
    },
}

# CEO-approved BBC England / NYT The Upshot / France 24 English RSS
# primaries (batch23). These three are the new adds. bbc_england ≠
# bbc_world / bbc_asia / bbc_europe / bbc_us_canada / bbc_middle_east /
# bbc_africa / bbc_latin_america / bbc_science / bbc_health /
# bbc_china / bbc_zh_simp / bbc_education / bbc_uk / bbc_politics /
# bbc_scotland / bbc_wales. nyt_upshot ≠ nyt_world / nyt_technology /
# nyt_business / nyt_science / nyt_climate / nyt_health /
# nyt_education / nyt_politics / nyt_us / nyt_europe. france24_en
# uses official English Europe RSS (https://www.france24.com/en/europe/rss)
# because locked https://www.france24.com/en/rss (and /en/world/rss,
# which redirects to /en/rss) has empty descriptions on live-blog
# items. bbc_northern_ireland / guardian_middle_east / euronews are
# batch24 (primaries, not unused backups). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays unregistered
# (replaced in batch20). NEWS_SOURCE_CAP display stays 6 — no CAP
# code change. No X this batch.
_BBC_ENGLAND_NYT_UPSHOT_FRANCE24_EN_PRIMARY = {
    "bbc_england": {
        "name": "BBC England",
        "feed_url": "https://feeds.bbci.co.uk/news/england/rss.xml",
        "category": "综合",
    },
    "nyt_upshot": {
        "name": "NYT The Upshot",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Upshot.xml",
        "category": "综合",
    },
    "france24_en": {
        "name": "France 24 English",
        "feed_url": "https://www.france24.com/en/europe/rss",
        "category": "国际",
    },
}

# CEO-approved BBC Northern Ireland / Guardian Middle East / Euronews
# English RSS primaries (batch24). These three are the new adds.
# bbc_northern_ireland ≠ bbc_world / bbc_asia / bbc_europe /
# bbc_us_canada / bbc_middle_east / bbc_africa / bbc_latin_america /
# bbc_science / bbc_health / bbc_china / bbc_zh_simp / bbc_education /
# bbc_uk / bbc_politics / bbc_scotland / bbc_wales / bbc_england.
# guardian_middle_east ≠ guardian_world / guardian_uk / guardian_us /
# guardian_americas / guardian_science / guardian_australia /
# guardian_technology / guardian_business / guardian_environment /
# guardian_europe / guardian_global_dev / guardian_law /
# guardian_society / guardian_cities / guardian_world_africa /
# guardian_politics / bbc_middle_east. euronews uses locked official
# English theme RSS https://www.euronews.com/rss?level=theme&name=news
# (also live-probed https://www.euronews.com/rss; both HTTP 200 with
# non-empty descriptions — locked URL kept). nyt_africa / smh_world /
# nbc_world are batch25 (primaries, not unused backups). nikkei_asia
# stays unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). NEWS_SOURCE_CAP display stays
# 6 — no CAP code change. No X this batch.
_BBC_NI_GUARDIAN_ME_EURONEWS_PRIMARY = {
    "bbc_northern_ireland": {
        "name": "BBC Northern Ireland",
        "feed_url": "https://feeds.bbci.co.uk/news/northern_ireland/rss.xml",
        "category": "综合",
    },
    "guardian_middle_east": {
        "name": "Guardian Middle East",
        "feed_url": "https://www.theguardian.com/world/middleeast/rss",
        "category": "国际",
    },
    "euronews": {
        "name": "Euronews English",
        "feed_url": "https://www.euronews.com/rss?level=theme&name=news",
        "category": "国际",
    },
}

# CEO-approved NYT Africa / SMH World / NBC News World RSS primaries
# (batch25). These three are the new adds. nyt_africa ≠ nyt_world /
# nyt_technology / nyt_business / nyt_science / nyt_climate /
# nyt_health / nyt_education / nyt_politics / nyt_us / nyt_europe /
# nyt_upshot (Africa.xml is a distinct NYT World subsection; live
# probe vs public DB was 9/20 already present via nyt_world/nyt_science
# and 11/20 unique — not the batch20 nyt_world_asia inserted0 case).
# smh_world uses official SMH RSS dir https://www.smh.com.au/rss/world.xml
# (https://www.smh.com.au/rssheadlines/world/article/rss.xml redirects
# to the same URL). nbc_world uses locked
# https://feeds.nbcnews.com/nbcnews/public/world (official alternate
# https://feeds.nbcnews.com/feeds/worldnews redirects to the same URL).
# csmonitor_world / latimes_world / hindu_international are batch26
# (primaries, promoted from unused backups / new). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays unregistered
# (replaced in batch20). NEWS_SOURCE_CAP display stays 6 — no CAP
# code change. No X this batch.
_NYT_AFRICA_SMH_WORLD_NBC_WORLD_PRIMARY = {
    "nyt_africa": {
        "name": "NYT Africa",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml",
        "category": "国际",
    },
    "smh_world": {
        "name": "Sydney Morning Herald World",
        "feed_url": "https://www.smh.com.au/rss/world.xml",
        "category": "国际",
    },
    "nbc_world": {
        "name": "NBC News World",
        "feed_url": "https://feeds.nbcnews.com/nbcnews/public/world",
        "category": "国际",
    },
}

# CEO-approved Christian Science Monitor World / LA Times World /
# The Hindu International RSS primaries (batch26). These three are
# the new adds. csmonitor_world and latimes_world were unused
# backups in batch25 and are now promoted (they were not already
# registered). hindu_international is a new source family using the
# official international section RSS on thehindu.com/rssfeeds
# (locked URL kept: 1/60 empty <description/> is occasional, not a
# high empty-desc rate; no other official same-outlet international
# section is 0-empty — france24 swap not used). cbc_world /
# cna_asia / elpais_en are batch27 (primaries, promoted from unused
# backups / new). nikkei_asia stays unregistered
# (title+link only). nyt_world_asia stays unregistered (replaced in
# batch20). NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_CSMONITOR_LATIMES_HINDU_PRIMARY = {
    "csmonitor_world": {
        "name": "Christian Science Monitor World",
        "feed_url": "https://rss.csmonitor.com/feeds/world",
        "category": "国际",
    },
    "latimes_world": {
        "name": "LA Times World",
        "feed_url": "https://www.latimes.com/world-nation/rss2.0.xml",
        "category": "国际",
    },
    "hindu_international": {
        "name": "The Hindu International",
        "feed_url": "https://www.thehindu.com/news/international/feeder/default.rss",
        "category": "国际",
    },
}

# CEO-approved CBC World / Channel NewsAsia Asia / El País English RSS
# primaries (batch27). These three are the new adds. cbc_world and
# cna_asia were unused backups in batch26 and are now promoted (they
# were not already registered). elpais_en is a new source family
# using the official English portada MRSS on feeds.elpais.com
# (locked URL kept: 0 empty descriptions). cna_asia keeps the locked
# official Asia category feed from channelnewsasia.com/rss
# (category=6511): 2/20 empty <description/> is occasional, not a
# high empty-desc rate; official same-outlet World is 4/20 empty,
# Latest 12/20, Business 17/20 — no Asia-section 0-empty swap
# (france24 pattern not used; Singapore 0-empty is a different
# section). yonhap / anadolu_world / trt_world are batch28
# (primaries; trt_world replaced independent_world after
# daily-fetch inserted=0). cbs_world / france24_asia /
# guardian_media are batch39. nikkei_asia
# stays unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). independent_world stays
# unregistered (replaced in batch28). NEWS_SOURCE_CAP display
# stays 6 — no CAP code change. No X this batch.
_CBC_CNA_ELPAIS_PRIMARY = {
    "cbc_world": {
        "name": "CBC World",
        "feed_url": "https://www.cbc.ca/webfeed/rss/rss-world",
        "category": "国际",
    },
    "cna_asia": {
        "name": "Channel NewsAsia Asia",
        "feed_url": (
            "https://www.channelnewsasia.com/api/v1/rss-outbound-feed"
            "?_format=xml&category=6511"
        ),
        "category": "国际",
    },
    "elpais_en": {
        "name": "El País English",
        "feed_url": (
            "https://feeds.elpais.com/mrss-s/pages/ep/site/"
            "english.elpais.com/portada"
        ),
        "category": "国际",
    },
}

# CEO-approved Yonhap English / Anadolu Agency World / TRT World
# RSS primaries (batch28). yonhap / anadolu_world stay as-is.
# trt_world replaces independent_world after daily-fetch RED
# (Independent World fetch error → inserted=0 / 0 rows in DB;
# CEO knife + thin-source rule). yonhap was an unused backup in
# batch27 and is now promoted (it was not already registered).
# anadolu_world is a new source family. Locked Yonhap English
# all-news URL on en.yna.co.kr/RSS kept: 0 empty descriptions
# (8/100 URGENT / almanac items use stub "(END)" / "Oct. 21"
# text, not empty; #43 thin-skip does not apply). Locked Anadolu
# official English World category RSS kept: 0 empty descriptions.
# Locked official TRT World RSS https://www.trtworld.com/feed/rss.xml
# kept: HTTP 200 / 100 items / 0 empty descriptions (relative
# <link>/<guid> `/article/...` resolved against the feed URL at
# ingest; no france24 URL swap — empty-desc is 0). 
# independent_world is unregistered (replaced). semafor /
# france24_americas / middleeasteye are batch29 (primaries;
# france24_americas / middleeasteye replaced france24_asia /
# al_monitor after daily-fetch inserted=0). cbs_world /
# france24_asia / guardian_media are batch39.
# nikkei_asia stays unregistered (title+link only).
# nyt_world_asia stays unregistered (replaced in batch20).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_YONHAP_ANADOLU_TRT_PRIMARY = {
    "yonhap": {
        "name": "Yonhap English",
        "feed_url": "https://en.yna.co.kr/RSS/news.xml",
        "category": "国际",
    },
    "anadolu_world": {
        "name": "Anadolu Agency World",
        "feed_url": "https://www.aa.com.tr/en/rss/default?cat=world",
        "category": "国际",
    },
    "trt_world": {
        "name": "TRT World",
        "feed_url": "https://www.trtworld.com/feed/rss.xml",
        "category": "国际",
    },
}

# CEO-approved Semafor / France 24 Americas / Middle East Eye RSS
# primaries (batch29). semafor stays live (daily-fetch inserted
# 30/30). france24_americas / middleeasteye replace
# france24_asia / al_monitor after daily-fetch #91 RED
# (france24_asia fetched 0 / inserted 0; al_monitor RSS
# soft-fail HTTP 403 → inserted 0; CEO knife + thin-source
# rule). france24_americas was an unused backup in #75 and is
# now promoted as a primary (it was not already registered;
# official English Americas RSS, distinct from france24_en
# Europe). middleeasteye was an unused backup in #75 and is
# now promoted (new source family; official
# https://www.middleeasteye.net/rss). Locked Semafor official
# https://www.semafor.com/rss.xml kept unchanged. Locked
# official France 24 Americas
# https://www.france24.com/en/americas/rss (no france24
# empty-desc URL swap — empty-desc is 0). Locked official
# Middle East Eye https://www.middleeasteye.net/rss.
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot).
# independent_world stays unregistered (replaced in batch28;
# 429). cbs_world / france24_asia / guardian_media
# are batch39. nikkei / indian_express stay
# unregistered (empty desc — product skipped). nikkei_asia
# stays unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). NEWS_SOURCE_CAP display
# stays 6 — no CAP code change. No X this batch.
_SEMAFOR_FRANCE24_AMERICAS_MIDDLEEASTEYE_PRIMARY = {
    "semafor": {
        "name": "Semafor",
        "feed_url": "https://www.semafor.com/rss.xml",
        "category": "国际",
    },
    "france24_americas": {
        "name": "France 24 Americas",
        "feed_url": "https://www.france24.com/en/americas/rss",
        "category": "国际",
    },
    "middleeasteye": {
        "name": "Middle East Eye",
        "feed_url": "https://www.middleeasteye.net/rss",
        "category": "国际",
    },
}

# CEO-approved SCMP Business / RFI Asia-Pacific / The Conversation
# RSS primaries (batch30). These three are the new adds.
# scmp_business is a same-outlet SCMP section distinct from
# existing scmp=/rss/2 Hong Kong, scmp_asia=/rss/3, scmp_china=
# /rss/4. Locked official scmp.com/rss Business section
# https://www.scmp.com/rss/92/feed (channel title "Business -
# South China Morning Post"). rfi_asia is a same-outlet RFI
# English Asia section distinct from existing rfi_en=
# https://www.rfi.fr/en/rss. Preferred
# https://www.rfi.fr/en/asia-pacific/rss is HTTP 200 but
# redirects 1:1 to https://www.rfi.fr/en/international/rss
# ("World news and headlines - RFI"; same dump as
# /en/europe|/en/americas|/en/middle-east) — not an
# Asia-Pacific section (not empty, not 403; section-identity
# failure). Official same-outlet English Asia alternate:
# https://www.rfi.fr/en/tag/asia/rss (channel title "Asia:
# news, podcasts, videos and analysis - RFI"; 0 overlap with
# rfi_en / international). French /fr/asie-pacifique/rss
# exists but is a different language than rfi_en / the
# preferred English URL — not used. theconversation is a new
# source family. Locked official
# https://theconversation.com/articles.atom (feed title
# "English – The Conversation"; official global/us/au/uk
# edition atoms also 200 / 0 empty-desc — pick one official
# id only; preferred articles.atom kept). forbes_innovation
# is batch33 (promoted from unused backup).
# propublica is batch32 (promoted from unused backup).
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot).
# independent_world stays unregistered (replaced in batch28;
# 429). cbs_world / france24_asia / guardian_media
# are batch39. nikkei / indian_express stay
# unregistered (empty desc — product skipped). nikkei_asia
# stays unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). NEWS_SOURCE_CAP display
# stays 6 — no CAP code change. No X this batch.
_SCMP_BUSINESS_RFI_ASIA_THECONVERSATION_PRIMARY = {
    "scmp_business": {
        "name": "SCMP Business",
        "feed_url": "https://www.scmp.com/rss/92/feed",
        "category": "财经",
    },
    "rfi_asia": {
        "name": "RFI Asia-Pacific",
        "feed_url": "https://www.rfi.fr/en/tag/asia/rss",
        "category": "国际·亚太",
    },
    "theconversation": {
        "name": "The Conversation",
        "feed_url": "https://theconversation.com/articles.atom",
        "category": "综合",
    },
}

# CEO-approved NYT Arts / Guardian Sport / The Intercept RSS
# primaries (batch31). These three are the new adds.
# nyt_arts is a same-outlet NYT section distinct from existing
# nyt_world / nyt_technology / nyt_business / nyt_science /
# nyt_climate / nyt_health / nyt_education / nyt_politics /
# nyt_us / nyt_europe / nyt_upshot / nyt_africa. Locked
# official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml
# (channel title "NYT > Arts"). guardian_sport is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east. Locked
# official guardian_* pattern
# https://www.theguardian.com/sport/rss (channel title
# "Sport | The Guardian"; geo edition may land on
# /us/sport/rss — same sport section, not a swap).
# intercept is a new source family. Locked official
# https://theintercept.com/feed/ (channel title
# "The Intercept"; preferred live HTTP 200 / 0 empty-desc
# — one official id only). nyt_opinion / guardian_film
# are batch32 (promoted from unused backups).
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot). independent_world stays unregistered
# (replaced in batch28; 429). cbs_world / france24_asia /
# guardian_media are batch39.
# nikkei / indian_express stay unregistered (empty desc
# — product skipped). nikkei_asia stays unregistered
# (title+link only). nyt_world_asia stays unregistered
# (replaced in batch20). sky_tech / restofworld /
# ars_science stay unregistered (not this batch).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_NYT_ARTS_GUARDIAN_SPORT_INTERCEPT_PRIMARY = {
    "nyt_arts": {
        "name": "NYT Arts",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",
        "category": "综合",
    },
    "guardian_sport": {
        "name": "Guardian Sport",
        "feed_url": "https://www.theguardian.com/sport/rss",
        "category": "综合",
    },
    "intercept": {
        "name": "The Intercept",
        "feed_url": "https://theintercept.com/feed/",
        "category": "综合",
    },
}

# CEO-approved NYT Opinion / Guardian Film / ProPublica RSS
# primaries (batch32). These three are the new adds.
# nyt_opinion is a same-outlet NYT section distinct from
# existing nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts. Locked official nyt_* feed
# pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml
# (channel title "NYT > Opinion"). guardian_film is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport. Locked official guardian_* pattern
# https://www.theguardian.com/film/rss (channel title
# "Film | The Guardian"; geo edition may land on
# /us/film/rss — same film section, not a swap).
# propublica was an unused backup in batch30 and is now
# promoted as a primary (it was not already registered;
# new source family). Locked official
# https://www.propublica.org/feeds/propublica/main
# (channel title "ProPublica"; preferred live HTTP 200 /
# 0 empty-desc — one official id only).
# forbes_innovation / dw_world / rfi_americas are
# batch33 (promoted from unused backups).
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot). independent_world stays unregistered
# (replaced in batch28; 429). cbs_world / france24_asia /
# guardian_media are batch39.
# nikkei / indian_express stay unregistered (empty desc
# — product skipped). nikkei_asia stays unregistered
# (title+link only). nyt_world_asia stays unregistered
# (replaced in batch20). sky_tech / restofworld /
# ars_science / thehill / politico stay unregistered
# (not this batch; politico is X-handle only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_NYT_OPINION_GUARDIAN_FILM_PROPUBLICA_PRIMARY = {
    "nyt_opinion": {
        "name": "NYT Opinion",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml",
        "category": "综合",
    },
    "guardian_film": {
        "name": "Guardian Film",
        "feed_url": "https://www.theguardian.com/film/rss",
        "category": "综合",
    },
    "propublica": {
        "name": "ProPublica",
        "feed_url": "https://www.propublica.org/feeds/propublica/main",
        "category": "综合",
    },
}

# CEO-approved Forbes Innovation / DW World / RFI Americas RSS
# primaries (batch33). These three are the new adds.
# forbes_innovation was an unused backup in batch30 / batch32
# and is now promoted as a primary (it was not already
# registered; new source family). Locked official
# https://www.forbes.com/innovation/feed/ (trailing slash;
# channel title "Forbes - Innovation"; /feed without slash
# also 200 / same body — preferred trailing slash kept).
# dw_world is a same-outlet DW English World RDF section
# distinct from existing dw_en=rss-en-all. Locked official
# product rdf-en-world
# https://rss.dw.com/rdf/rss-en-world (channel title
# "World | Deutsche Welle"). Atom
# https://rss.dw.com/atom/rss-en-world also 200 / 0
# empty-desc — pick one official id only; preferred RDF
# kept. rfi_americas is a same-outlet RFI English Americas
# section distinct from existing rfi_en=
# https://www.rfi.fr/en/rss and rfi_asia=
# https://www.rfi.fr/en/tag/asia/rss. Preferred
# https://www.rfi.fr/en/americas/rss is HTTP 200 but
# redirects 1:1 to https://www.rfi.fr/en/international/rss
# ("World news and headlines - RFI"; same dump as
# /en/europe|/en/asia-pacific|/en/middle-east) — not an
# Americas section (not empty, not 403; section-identity
# failure, same class as rfi_asia). Preferred tag
# https://www.rfi.fr/en/tag/americas/rss is HTTP 404.
# Official same-outlet English Americas alternate (match
# rfi_asia /en/tag/asia/rss):
# https://www.rfi.fr/en/tag/latin-america/rss (channel
# title "Latin America: news, podcasts, videos and
# analysis - RFI"). French /fr/amériques/rss exists but
# is a different language than rfi_en / the preferred
# English URL — not used. nyt_movies / guardian_music /
# guardian_stage are batch34 (promoted from unused
# backups). nyt_books / guardian_books / npr_arts are
# batch35 (promoted from unused backups).
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot). independent_world stays
# unregistered (replaced in batch28; 429). cbs_world /
# france24_asia / guardian_media are batch39. nikkei /
# indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP display stays 6 — no CAP code
# change. No X this batch.
_FORBES_INNOVATION_DW_WORLD_RFI_AMERICAS_PRIMARY = {
    "forbes_innovation": {
        "name": "Forbes Innovation",
        "feed_url": "https://www.forbes.com/innovation/feed/",
        "category": "科技",
    },
    "dw_world": {
        "name": "Deutsche Welle World",
        "feed_url": "https://rss.dw.com/rdf/rss-en-world",
        "category": "国际",
    },
    "rfi_americas": {
        "name": "RFI Americas",
        "feed_url": "https://www.rfi.fr/en/tag/latin-america/rss",
        "category": "国际·美洲",
    },
}

# CEO-approved NYT Movies / Guardian Music / Guardian Stage RSS
# primaries (batch34). These three are the new adds.
# nyt_movies is a same-outlet NYT section distinct from
# existing nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts / nyt_opinion. Locked official
# nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml
# (channel title "NYT > Movies"). guardian_music is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film. Locked official
# guardian_* pattern
# https://www.theguardian.com/music/rss (channel title
# "Music | The Guardian"; /us/music/rss is 404 — not a
# geo-edition swap). guardian_stage is a same-outlet
# Guardian section distinct from existing guardian_*
# including guardian_music / guardian_film /
# guardian_sport. Locked official guardian_* pattern
# https://www.theguardian.com/stage/rss (channel title
# "Stage | The Guardian"; /us/stage/rss is 404 — not a
# geo-edition swap). nyt_books / guardian_books /
# npr_arts are batch35 (promoted from unused
# backups). france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in batch29;
# not a live CAP slot). independent_world stays
# unregistered (replaced in batch28; 429). cbs_world /
# france24_asia / guardian_media are batch39. nikkei /
# indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico /
# abc_intl / sunday_review stay unregistered (not this
# batch; politico is X-handle only). NEWS_SOURCE_CAP
# display stays 6 — no CAP code change. No X this batch.
_NYT_MOVIES_GUARDIAN_MUSIC_GUARDIAN_STAGE_PRIMARY = {
    "nyt_movies": {
        "name": "NYT Movies",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml",
        "category": "综合",
    },
    "guardian_music": {
        "name": "Guardian Music",
        "feed_url": "https://www.theguardian.com/music/rss",
        "category": "综合",
    },
    "guardian_stage": {
        "name": "Guardian Stage",
        "feed_url": "https://www.theguardian.com/stage/rss",
        "category": "综合",
    },
}

# CEO-approved NYT Books / Guardian Books / NPR Arts RSS
# primaries (batch35). These three are the new adds.
# nyt_books is a same-outlet NYT section distinct from
# existing nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts / nyt_opinion / nyt_movies.
# Locked official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Books.xml
# (channel title "NYT > Books"). guardian_books is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film / guardian_music /
# guardian_stage. Locked official guardian_* pattern
# https://www.theguardian.com/books/rss (channel title
# "Books | The Guardian"; /us/books/rss is 404 — not a
# geo-edition swap). npr_arts is a same-outlet NPR topic
# distinct from existing npr_news (1001) / npr_world
# (1004). Locked official npr_* feed pattern
# https://feeds.npr.org/1008/rss.xml (channel title
# "NPR Topics: Culture"; product 200/10/0 — on the ≥10
# thin-source floor, still registered as live).
# nyt_food / guardian_tv / npr_science are batch36
# (promoted from unused backups). nyt_travel /
# guardian_fashion / nyt_economy are batch37
# (nyt_economy hard-swapped in for npr_business).
# nyt_realestate / guardian_lifeandstyle /
# bbc_entertainment are batch38.
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in
# batch29; not a live CAP slot). independent_world stays
# unregistered (replaced in batch28; 429). cbs_world /
# france24_asia / guardian_media are batch39. nikkei /
# indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico /
# abc_intl / sunday_review / nyt_sports stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP
# display stays 6 — no CAP code change. No X this batch.
_NYT_BOOKS_GUARDIAN_BOOKS_NPR_ARTS_PRIMARY = {
    "nyt_books": {
        "name": "NYT Books",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml",
        "category": "综合",
    },
    "guardian_books": {
        "name": "Guardian Books",
        "feed_url": "https://www.theguardian.com/books/rss",
        "category": "综合",
    },
    "npr_arts": {
        "name": "NPR Arts",
        "feed_url": "https://feeds.npr.org/1008/rss.xml",
        "category": "综合",
    },
}

# CEO-approved NYT Food / Guardian TV / NPR Science RSS
# primaries (batch36). These three are the new adds.
# nyt_food is a same-outlet NYT section distinct from
# existing nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts / nyt_opinion / nyt_movies /
# nyt_books. Locked official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml
# (channel title "NYT > Food"). Dining.xml and Food.xml
# are both 404 — do not use those. guardian_tv is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film / guardian_music /
# guardian_stage / guardian_books. Locked official
# guardian_* pattern
# https://www.theguardian.com/tv-and-radio/rss (channel
# title "TV and radio | The Guardian"). npr_science is a
# same-outlet NPR topic distinct from existing npr_news
# (1001) / npr_world (1004) / npr_arts (1008). Locked
# official npr_* feed pattern
# https://feeds.npr.org/1007/rss.xml (channel title
# "NPR Topics: Science"; product 200/10/0 — on the ≥10
# thin-source floor, still registered as live). npr_arts
# stays in the registry (batch35 closed with it as
# thin-source observe, not swapped). nyt_travel /
# guardian_fashion / nyt_economy are batch37
# (nyt_economy hard-swapped in for npr_business).
# nyt_realestate / guardian_lifeandstyle /
# bbc_entertainment are batch38.
# Unused backups list is empty this batch — do not
# invent next ids / do not register unused live-diff
# backups (cnbc_top / bloomberg_markets /
# guardian_economics).
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in
# batch29; not a live CAP slot). independent_world stays
# unregistered (replaced in batch28; 429). cbs_world /
# france24_asia / guardian_media are batch39. nikkei /
# indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico /
# abc_intl / sunday_review / nyt_sports stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP
# display stays 6 — no CAP code change. No X this batch.
_NYT_FOOD_GUARDIAN_TV_NPR_SCIENCE_PRIMARY = {
    "nyt_food": {
        "name": "NYT Food",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml",
        "category": "综合",
    },
    "guardian_tv": {
        "name": "Guardian TV",
        "feed_url": "https://www.theguardian.com/tv-and-radio/rss",
        "category": "综合",
    },
    "npr_science": {
        "name": "NPR Science",
        "feed_url": "https://feeds.npr.org/1007/rss.xml",
        "category": "科学",
    },
}

# CEO-approved NYT Travel / Guardian Fashion RSS primaries
# (batch37) plus batch37 thin-source HARD SWAP: npr_business
# (NPR 1006) removed because public fetch count <5; nyt_economy
# registered in its place. nyt_travel / guardian_fashion stay
# unchanged. nyt_travel is a same-outlet NYT section distinct
# from existing nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts / nyt_opinion / nyt_movies /
# nyt_books / nyt_food / nyt_economy. Locked official nyt_*
# feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml
# (channel title "NYT > Travel"). TravelGuide.xml and
# Escapes.xml are both 404 — do not use those.
# guardian_fashion is a same-outlet Guardian section
# distinct from existing guardian_world /
# guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film / guardian_music /
# guardian_stage / guardian_books / guardian_tv.
# Locked official guardian_* pattern
# https://www.theguardian.com/fashion/rss (channel
# title "Fashion | The Guardian"; /uk/fashion/rss and
# /us/fashion/rss are 404 — not a geo-edition swap).
# nyt_economy is a same-outlet NYT section distinct from
# existing nyt_business (Business.xml) / nyt_travel /
# nyt_world and the rest of the nyt_* set. Locked official
# nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml
# (channel title "NYT > Business > Economy"). Live-diff
# winner: HTTP 200 / ≥10 items — do not fall through to
# unused backups cnbc_top / bloomberg_markets /
# guardian_economics (not registered). npr_business stays
# unregistered (hard-swapped; not a live CAP slot; not a
# backup). Unused backups list is empty this batch — do
# not invent next ids / do not register unused backups.
# nyt_realestate / guardian_lifeandstyle /
# bbc_entertainment are batch38.
# france24_asia is batch39 (CEO knife re-add).
# al_monitor stays unregistered (replaced in
# batch29; not a live CAP slot). independent_world stays
# unregistered (replaced in batch28; 429). cbs_world /
# france24_asia / guardian_media are batch39. nikkei /
# indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico /
# abc_intl / sunday_review / nyt_sports stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP
# display stays 6 — no CAP code change. No X this batch.
_NYT_TRAVEL_GUARDIAN_FASHION_NYT_ECONOMY_PRIMARY = {
    "nyt_travel": {
        "name": "NYT Travel",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml",
        "category": "综合",
    },
    "guardian_fashion": {
        "name": "Guardian Fashion",
        "feed_url": "https://www.theguardian.com/fashion/rss",
        "category": "综合",
    },
    "nyt_economy": {
        "name": "NYT Economy",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
        "category": "财经",
    },
}

# CEO-approved NYT Real Estate / Guardian Lifestyle / BBC
# Entertainment RSS primaries (batch38). These three are
# the new adds. nyt_realestate is a same-outlet NYT section
# distinct from existing nyt_world / nyt_technology /
# nyt_business / nyt_science / nyt_climate / nyt_health /
# nyt_education / nyt_politics / nyt_us / nyt_europe /
# nyt_upshot / nyt_africa / nyt_arts / nyt_opinion /
# nyt_movies / nyt_books / nyt_food / nyt_travel /
# nyt_economy. Locked official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml
# (channel title "NYT > Real Estate"). HomeandGarden.xml
# is 404 — do not use that. guardian_lifeandstyle is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film / guardian_music /
# guardian_stage / guardian_books / guardian_tv /
# guardian_fashion. Locked official guardian_* pattern
# https://www.theguardian.com/lifeandstyle/rss (channel
# title "Lifestyle | The Guardian"). /uk/lifeandstyle/rss
# and /us/lifeandstyle/rss are geo-edition variants —
# not a swap; lock the section root. bbc_entertainment
# is a same-outlet BBC topic distinct from existing
# bbc_zh_simp / bbc_world / bbc_technology / bbc_business /
# bbc_science / bbc_asia / bbc_europe / bbc_us_canada /
# bbc_middle_east / bbc_africa / bbc_latin_america /
# bbc_health / bbc_china / bbc_education / bbc_uk /
# bbc_politics / bbc_scotland / bbc_wales / bbc_england /
# bbc_northern_ireland. Locked official bbc_* feed
# pattern
# https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml
# (channel title "BBC News"; entertainment/rss.xml,
# culture/rss.xml, and bbc.com/culture/feed.xml are 404
# — do not use those). Live-diff winner on all three
# primaries: HTTP 200 / ≥10 items — do not fall through
# to unused backups (not registered this batch).
# nyt_travel / guardian_fashion / nyt_economy stay
# registered (batch37 closed; nyt_economy thin-observe
# kept). cbs_world / france24_asia / guardian_media
# are batch39 (CEO knife re-add after live-diff ≥10).
# Unused backups were probed only — do not register
# unused backups. al_monitor stays unregistered
# (replaced in batch29; not a live CAP slot; not
# registered as a backup). independent_world stays
# unregistered (replaced in batch28; 429). nikkei /
# indian_express stay unregistered (empty desc —
# product skipped). nikkei_asia stays unregistered
# (title+link only). nyt_world_asia stays unregistered
# (replaced in batch20). sky_tech / restofworld /
# ars_science / thehill / politico / abc_intl /
# sunday_review / nyt_sports stay unregistered (not
# this batch; politico is X-handle only).
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch.
_NYT_REALESTATE_GUARDIAN_LIFEANDSTYLE_BBC_ENTERTAINMENT_PRIMARY = {
    "nyt_realestate": {
        "name": "NYT Real Estate",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml",
        "category": "综合",
    },
    "guardian_lifeandstyle": {
        "name": "Guardian Lifestyle",
        "feed_url": "https://www.theguardian.com/lifeandstyle/rss",
        "category": "综合",
    },
    "bbc_entertainment": {
        "name": "BBC Entertainment",
        "feed_url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "category": "综合",
    },
}

# CEO-approved CBS World / France 24 Asia RSS primaries
# (batch39) plus batch39 thin-source HARD SWAP:
# guardian_media removed because public insert count <5
# (insert=4 after #87); cnbc_top registered in its place.
# cbs_world (5–9 observe) and france24_asia stay
# registered and unchanged. cbs_world is a same-outlet
# CBS section distinct from existing cbs_news. Locked
# official cbs_* feed pattern
# https://www.cbsnews.com/latest/rss/world (channel
# title "World - CBSNews.com"). world-news is 406 —
# do not use that. france24_asia is a same-outlet
# France 24 English section distinct from existing
# france24_en (europe) / france24_americas. Locked
# official france24_* pattern
# https://www.france24.com/en/asia-pacific/rss
# (channel title "News from Asia-Pacific - Latest
# headlines and news reports - France 24"). /en/asia/rss
# is 404 — do not use that. /en/rss is the locked-away
# front page (batch23). cnbc_top is CNBC US Top News
# and Analysis (channel title "US Top News and
# Analysis"). Locked official CNBC RSS id 100003114
# https://www.cnbc.com/id/100003114/device/rss/rss.html
# Live-diff winner: HTTP 200 / ≥10 items — first
# healthy backup on the ladder. bloomberg_markets /
# guardian_economics stay unregistered (cnbc_top won;
# not existing guardian_business uk/business).
# guardian_media stays unregistered (hard-swapped;
# not a live CAP slot; not a backup). nyt_realestate /
# guardian_lifeandstyle / bbc_entertainment stay
# registered (batch38 closed; bbc_entertainment
# thin-observe kept). al_monitor stays unregistered
# (replaced in batch29; not a live CAP slot; not
# registered as a backup). independent_world stays
# unregistered (replaced in batch28; 429).
# npr_business stays unregistered (hard-swapped in
# batch37). nikkei / indian_express stay unregistered
# (empty desc — product skipped). nikkei_asia stays
# unregistered (title+link only). nyt_world_asia stays
# unregistered (replaced in batch20). sky_tech /
# restofworld / ars_science / thehill / politico /
# abc_intl / sunday_review / nyt_sports stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP display stays 6 — no CAP
# code change. No X this batch. No LLM this batch.
# bloomberg_markets / guardian_opinion / nyt_magazine
# are batch40 (guardian_opinion hard-swapped in for
# guardian_economics after public insert=1 <5).
# france24_middle_east / nyt_personaltech /
# france24_africa are batch41.
_CBS_WORLD_FRANCE24_ASIA_CNBC_TOP_PRIMARY = {
    "cbs_world": {
        "name": "CBS News World",
        "feed_url": "https://www.cbsnews.com/latest/rss/world",
        "category": "国际",
    },
    "france24_asia": {
        "name": "France 24 Asia-Pacific",
        "feed_url": "https://www.france24.com/en/asia-pacific/rss",
        "category": "国际",
    },
    "cnbc_top": {
        "name": "CNBC Top News",
        "feed_url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "category": "财经",
    },
}

# CEO-approved Bloomberg Markets / Guardian Opinion / NYT
# Magazine RSS primaries (batch40 after thin-source hard
# swap). bloomberg_markets and nyt_magazine stay
# registered (batch40 closed adds). guardian_economics
# is removed (public insert=1 <5 hard-swap threshold)
# and is not a live CAP slot / not registered as a
# backup. guardian_opinion won the backup ladder
# live-diff and is now registered as a primary.
# bloomberg_markets is Bloomberg Markets news RSS,
# distinct from existing cnbc_top / nyt_economy /
# nyt_business / bbc_business / guardian_business /
# scmp_business. Locked official Bloomberg Markets feed
# https://feeds.bloomberg.com/markets/news.rss (channel
# title "Bloomberg Markets"). guardian_opinion is a
# same-outlet Guardian section distinct from existing
# guardian_world / guardian_technology / guardian_us /
# guardian_environment / guardian_business /
# guardian_science / guardian_australia /
# guardian_americas / guardian_uk / guardian_europe /
# guardian_global_dev / guardian_law / guardian_society /
# guardian_cities / guardian_world_africa /
# guardian_politics / guardian_middle_east /
# guardian_sport / guardian_film / guardian_music /
# guardian_stage / guardian_books / guardian_tv /
# guardian_fashion / guardian_lifeandstyle, and from
# same-outlet nyt_opinion. Locked official guardian_*
# pattern https://www.theguardian.com/commentisfree/rss
# (channel title "Opinion | The Guardian").
# /opinion/rss and /uk/commentisfree/rss are not this
# feed — do not use those. nyt_magazine is a same-outlet
# NYT section distinct from existing nyt_world /
# nyt_technology / nyt_business / nyt_science /
# nyt_climate / nyt_health / nyt_education /
# nyt_politics / nyt_us / nyt_europe / nyt_upshot /
# nyt_africa / nyt_arts / nyt_opinion / nyt_movies /
# nyt_books / nyt_food / nyt_travel / nyt_economy /
# nyt_realestate. Locked official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/Magazine.xml
# (channel title "NYT > The New York Times Magazine").
# Live-diff winner: guardian_opinion HTTP 200 / ≥10
# nonempty items — do not fall through to unused
# batch40 backups (those ids are now batch41
# primaries). cbs_world / france24_asia / cnbc_top
# stay registered (batch39 closed; cbs_world observe
# kept). nyt_realestate / guardian_lifeandstyle /
# bbc_entertainment stay registered (batch38 closed).
# guardian_media stays unregistered (hard-swapped in
# batch39). npr_business stays unregistered
# (hard-swapped in batch37). al_monitor stays
# unregistered (replaced in batch29; not a live CAP
# slot; not registered as a backup).
# independent_world stays unregistered (replaced in
# batch28; 429). nikkei / indian_express stay
# unregistered (empty desc — product skipped).
# nikkei_asia stays unregistered (title+link only).
# nyt_world_asia stays unregistered (replaced in
# batch20). sky_tech / restofworld / ars_science /
# thehill / politico / abc_intl / sunday_review stay
# unregistered (not this batch; politico is X-handle
# only). france24_middle_east / nyt_personaltech /
# france24_africa are batch41 (CEO knife; live-diff
# winners). Unused batch41 backups reuters_world /
# nyt_sports / guardian_food stay unregistered.
# NEWS_SOURCE_CAP display stays 6 — no CAP code change.
# No X this batch. No LLM this batch.
_BLOOMBERG_MARKETS_GUARDIAN_OPINION_NYT_MAGAZINE_PRIMARY = {
    "bloomberg_markets": {
        "name": "Bloomberg Markets",
        "feed_url": "https://feeds.bloomberg.com/markets/news.rss",
        "category": "财经",
    },
    "guardian_opinion": {
        "name": "Guardian Opinion",
        "feed_url": "https://www.theguardian.com/commentisfree/rss",
        "category": "综合",
    },
    "nyt_magazine": {
        "name": "NYT Magazine",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/Magazine.xml",
        "category": "综合",
    },
}

# CEO-approved France 24 Middle East / NYT Personal
# Technology / France 24 Africa RSS primaries (batch41).
# These three are the new adds. france24_middle_east is
# a same-outlet France 24 English section distinct from
# existing france24_en (europe) / france24_americas /
# france24_asia. Locked official france24_* pattern
# https://www.france24.com/en/middle-east/rss (channel
# title "Latest news from the Middle East, daily
# international news reports - France 24").
# /en/middleeast/rss is 404 — do not use that. /en/rss
# is the locked-away front page (batch23). Distinct
# from bbc_middle_east / guardian_middle_east /
# middleeasteye. nyt_personaltech is a same-outlet NYT
# Technology subsection distinct from existing
# nyt_world / nyt_technology / nyt_business /
# nyt_science / nyt_climate / nyt_health /
# nyt_education / nyt_politics / nyt_us / nyt_europe /
# nyt_upshot / nyt_africa / nyt_arts / nyt_opinion /
# nyt_movies / nyt_books / nyt_food / nyt_travel /
# nyt_economy / nyt_realestate / nyt_magazine. Locked
# official nyt_* feed pattern
# https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml
# (channel title "NYT > Technology > Personal Tech").
# PersonalTechnology.xml is 404 — do not use that.
# france24_africa is a same-outlet France 24 English
# section distinct from france24_en / france24_americas
# / france24_asia / france24_middle_east. Locked
# official france24_* pattern
# https://www.france24.com/en/africa/rss (channel title
# "Breaking news from AFRICA, Maghreb and Sub-Saharan
# Africa - France 24"). /en/africa/rss.xml is 403 —
# do not use that. Distinct from bbc_africa /
# nyt_africa / guardian_world_africa. Live-diff winner
# on all three primaries: HTTP 200 / ≥10 nonempty
# items — do not fall through to unused backups
# reuters_world / nyt_sports / guardian_food (probed
# only; not registered). reuters_world official public
# RSS is dead (feeds.reuters.com NXDOMAIN; reuters.com
# /world/rss and /rssFeed/worldNews HTTP 401) — do not
# invent a Google News proxy. nyt_sports Sports.xml is
# HTTP 200 but 0 items. guardian_food is healthy
# (theguardian.com/food/rss; /uk/food/rss is 404) but
# unused because primaries won. bloomberg_markets /
# guardian_opinion / nyt_magazine stay registered
# (batch40 closed; guardian_opinion hard-swap kept).
# cbs_world / france24_asia / cnbc_top stay registered
# (batch39 closed; cbs_world observe kept).
# guardian_economics stays unregistered (hard-swapped
# in batch40). guardian_media stays unregistered
# (hard-swapped in batch39). npr_business stays
# unregistered (hard-swapped in batch37). al_monitor
# stays unregistered (replaced in batch29; not a live
# CAP slot; not registered as a backup).
# independent_world stays unregistered (replaced in
# batch28; 429). nikkei / indian_express stay
# unregistered (empty desc — product skipped).
# nikkei_asia stays unregistered (title+link only).
# nyt_world_asia stays unregistered (replaced in
# batch20). sky_tech / restofworld / ars_science /
# thehill / politico / abc_intl / sunday_review stay
# unregistered (not this batch; politico is X-handle
# only). NEWS_SOURCE_CAP display stays 6 — no CAP
# code change. No X this batch. No LLM this batch.
_FRANCE24_MIDDLE_EAST_NYT_PERSONALTECH_FRANCE24_AFRICA_PRIMARY = {
    "france24_middle_east": {
        "name": "France 24 Middle East",
        "feed_url": "https://www.france24.com/en/middle-east/rss",
        "category": "国际",
    },
    "nyt_personaltech": {
        "name": "NYT Personal Technology",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml",
        "category": "硬科技",
    },
    "france24_africa": {
        "name": "France 24 Africa",
        "feed_url": "https://www.france24.com/en/africa/rss",
        "category": "国际",
    },
}

_EXPECTED_PRIMARY_COUNT = 131
_EXPECTED_CONTROL_COUNT = 1

# RSS 1.0 / RDF (dw_en / dw_world) and Atom fallbacks for live XML probes.
_RSS10_ITEM = "{http://purl.org/rss/1.0/}item"
_RSS10_DESC = "{http://purl.org/rss/1.0/}description"
_RSS10_TITLE = "{http://purl.org/rss/1.0/}title"
_RSS10_LINK = "{http://purl.org/rss/1.0/}link"
_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ATOM_ENTRY = f"{_ATOM_NS}entry"
_ATOM_SUMMARY = f"{_ATOM_NS}summary"
_ATOM_CONTENT = f"{_ATOM_NS}content"
_ATOM_TITLE = f"{_ATOM_NS}title"
_ATOM_LINK = f"{_ATOM_NS}link"
_ATOM_PUBLISHED = f"{_ATOM_NS}published"
_ATOM_UPDATED = f"{_ATOM_NS}updated"
_ATOM_ID = f"{_ATOM_NS}id"


def _decode_feed_body(body: bytes) -> bytes:
    """Independent (and some CDNs) return gzip even to urllib."""
    if body[:2] == b"\x1f\x8b":
        return gzip.decompress(body)
    return body


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
        or (item.findtext(_ATOM_CONTENT) or "").strip()
    )


def _item_title(item: ET.Element) -> str:
    return (
        (item.findtext("title") or "").strip()
        or (item.findtext(_RSS10_TITLE) or "").strip()
        or (item.findtext(_ATOM_TITLE) or "").strip()
    )


def _item_link(item: ET.Element) -> str:
    text = (
        (item.findtext("link") or "").strip()
        or (item.findtext(_RSS10_LINK) or "").strip()
    )
    if text:
        return text
    alternate = ""
    first_href = ""
    for el in [*item.findall("link"), *item.findall(_ATOM_LINK)]:
        href = (el.get("href") or "").strip() or (el.text or "").strip()
        if not href:
            continue
        if not first_href:
            first_href = href
        rel = el.get("rel") or "alternate"
        if rel == "alternate":
            alternate = href
            break
    if alternate or first_href:
        return alternate or first_href
    return (item.findtext("guid") or item.findtext(_ATOM_ID) or "").strip()


def _item_published(item: ET.Element) -> str:
    return (
        (item.findtext("pubDate") or "").strip()
        or (item.findtext("published") or "").strip()
        or (item.findtext("updated") or "").strip()
        or (item.findtext(_DC_DATE) or "").strip()
        or (item.findtext(_ATOM_PUBLISHED) or "").strip()
        or (item.findtext(_ATOM_UPDATED) or "").strip()
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


def test_bbc_politics_nyt_europe_guardian_law_primaries_registered():
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
    assert "guardian_law" in by_id
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
    assert by_id["guardian_law"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_law"].feed_url != by_id["guardian_global_dev"].feed_url
    # Replaced / title+link-only feeds stay unregistered.
    # guardian_society is batch21 (primary, not an unused backup).
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_POLITICS_NYT_EUROPE_GUARDIAN_LAW_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_guardian_society_bbc_scotland_guardian_cities_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
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
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_society"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_society"].feed_url != by_id["guardian_law"].feed_url
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
    assert "bbc_scotland" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_uk"].feed_url
    assert by_id["bbc_scotland"].feed_url != by_id["bbc_politics"].feed_url
    assert "guardian_cities" in by_id
    assert by_id["guardian_cities"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_cities"].feed_url != by_id["guardian_society"].feed_url
    # Replaced / title+link-only feeds stay unregistered.
    # guardian_world_africa / guardian_politics / bbc_wales are batch22
    # (primaries, not unused backups).
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _GUARDIAN_SOCIETY_BBC_SCOTLAND_GUARDIAN_CITIES_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_guardian_world_africa_guardian_politics_bbc_wales_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
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
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_world_africa"].feed_url != by_id["guardian_cities"].feed_url
    assert "bbc_africa" in by_id
    assert by_id["guardian_world_africa"].feed_url != by_id["bbc_africa"].feed_url
    assert "guardian_politics" in by_id
    assert by_id["guardian_politics"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["guardian_world_africa"].feed_url
    assert "bbc_politics" in by_id
    assert "nyt_politics" in by_id
    assert by_id["guardian_politics"].feed_url != by_id["bbc_politics"].feed_url
    assert by_id["guardian_politics"].feed_url != by_id["nyt_politics"].feed_url
    assert "bbc_world" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_science" in by_id
    assert "bbc_health" in by_id
    assert "bbc_china" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_education" in by_id
    assert "bbc_uk" in by_id
    assert "bbc_scotland" in by_id
    assert "bbc_wales" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_wales"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_uk"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_politics"].feed_url
    assert by_id["bbc_wales"].feed_url != by_id["bbc_scotland"].feed_url
    # Replaced / title+link-only feeds stay unregistered.
    # bbc_england / nyt_upshot / france24_en are batch23 (primaries,
    # not unused backups).
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _GUARDIAN_WORLD_AFRICA_GUARDIAN_POLITICS_BBC_WALES_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_england_nyt_upshot_france24_en_primaries_registered():
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
    assert "bbc_scotland" in by_id
    assert "bbc_wales" in by_id
    assert "bbc_england" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_england"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_uk"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_politics"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_scotland"].feed_url
    assert by_id["bbc_england"].feed_url != by_id["bbc_wales"].feed_url
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
    assert "nyt_upshot" in by_id
    assert by_id["nyt_world"].feed_url == "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_upshot"].feed_url != by_id["nyt_europe"].feed_url
    assert "france24_en" in by_id
    assert by_id["france24_en"].feed_url == "https://www.france24.com/en/europe/rss"
    assert by_id["france24_en"].feed_url != "https://www.france24.com/en/rss"
    # Replaced / title+link-only feeds stay unregistered.
    # bbc_northern_ireland / guardian_middle_east / euronews are
    # batch24 (primaries, not unused backups).
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_ENGLAND_NYT_UPSHOT_FRANCE24_EN_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bbc_ni_guardian_me_euronews_primaries_registered():
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
    assert "bbc_scotland" in by_id
    assert "bbc_wales" in by_id
    assert "bbc_england" in by_id
    assert "bbc_northern_ireland" in by_id
    assert by_id["bbc_world"].feed_url == "https://feeds.bbci.co.uk/news/world/rss.xml"
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_uk"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_politics"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_scotland"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_wales"].feed_url
    assert by_id["bbc_northern_ireland"].feed_url != by_id["bbc_england"].feed_url
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
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert by_id["guardian_world"].feed_url == "https://www.theguardian.com/world/rss"
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_middle_east"].feed_url != by_id["bbc_middle_east"].feed_url
    assert "euronews" in by_id
    assert by_id["euronews"].feed_url == "https://www.euronews.com/rss?level=theme&name=news"
    assert by_id["euronews"].feed_url != "https://www.euronews.com/rss"
    assert "france24_en" in by_id
    assert by_id["euronews"].feed_url != by_id["france24_en"].feed_url
    # nyt_africa / smh_world / nbc_world are batch25 (primaries, not
    # unused backups). Replaced / title+link-only feeds stay unregistered.
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _BBC_NI_GUARDIAN_ME_EURONEWS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_africa_smh_world_nbc_world_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert by_id["nyt_world"].feed_url == "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    assert by_id["nyt_africa"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_africa"].feed_url != by_id["nyt_upshot"].feed_url
    assert "smh_world" in by_id
    assert by_id["smh_world"].feed_url == "https://www.smh.com.au/rss/world.xml"
    assert by_id["smh_world"].feed_url != (
        "https://www.smh.com.au/rssheadlines/world/article/rss.xml"
    )
    assert "nbc_world" in by_id
    assert by_id["nbc_world"].feed_url == "https://feeds.nbcnews.com/nbcnews/public/world"
    assert by_id["nbc_world"].feed_url != "https://feeds.nbcnews.com/feeds/worldnews"
    assert "straitstimes_world" in by_id
    assert by_id["smh_world"].feed_url != by_id["straitstimes_world"].feed_url
    assert by_id["nbc_world"].feed_url != by_id["straitstimes_world"].feed_url
    # csmonitor_world / latimes_world / hindu_international are
    # batch26 (primaries, not unused backups). Replaced /
    # title+link-only feeds stay unregistered.
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _NYT_AFRICA_SMH_WORLD_NBC_WORLD_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_csmonitor_latimes_hindu_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "csmonitor_world" in by_id
    assert by_id["csmonitor_world"].feed_url == "https://rss.csmonitor.com/feeds/world"
    assert "latimes_world" in by_id
    assert by_id["latimes_world"].feed_url == "https://www.latimes.com/world-nation/rss2.0.xml"
    assert "hindu_international" in by_id
    assert by_id["hindu_international"].feed_url == (
        "https://www.thehindu.com/news/international/feeder/default.rss"
    )
    assert "guardian_world" in by_id
    assert "bbc_world" in by_id
    assert "nyt_world" in by_id
    assert "aljazeera" in by_id
    assert "straitstimes_world" in by_id
    assert "smh_world" in by_id
    assert "nbc_world" in by_id
    assert by_id["csmonitor_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["csmonitor_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["csmonitor_world"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["latimes_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["latimes_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["latimes_world"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["latimes_world"].feed_url != by_id["nbc_world"].feed_url
    assert by_id["hindu_international"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["hindu_international"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["hindu_international"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["hindu_international"].feed_url != by_id["straitstimes_world"].feed_url
    assert by_id["hindu_international"].feed_url != by_id["smh_world"].feed_url
    assert by_id["csmonitor_world"].feed_url != by_id["latimes_world"].feed_url
    assert by_id["csmonitor_world"].feed_url != by_id["hindu_international"].feed_url
    assert by_id["latimes_world"].feed_url != by_id["hindu_international"].feed_url
    # cbc_world / cna_asia / elpais_en are batch27 (primaries, not
    # unused backups). Replaced / title+link-only feeds stay
    # unregistered.
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _CSMONITOR_LATIMES_HINDU_PRIMARY.items():
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


def test_bbc_politics_nyt_europe_guardian_law_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_POLITICS_NYT_EUROPE_GUARDIAN_LAW_PRIMARY:
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


def test_guardian_society_bbc_scotland_guardian_cities_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _GUARDIAN_SOCIETY_BBC_SCOTLAND_GUARDIAN_CITIES_PRIMARY:
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


def test_guardian_world_africa_guardian_politics_bbc_wales_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _GUARDIAN_WORLD_AFRICA_GUARDIAN_POLITICS_BBC_WALES_PRIMARY:
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


def test_bbc_england_nyt_upshot_france24_en_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_ENGLAND_NYT_UPSHOT_FRANCE24_EN_PRIMARY:
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


def test_bbc_ni_guardian_me_euronews_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BBC_NI_GUARDIAN_ME_EURONEWS_PRIMARY:
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


def test_nyt_africa_smh_world_nbc_world_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_AFRICA_SMH_WORLD_NBC_WORLD_PRIMARY:
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


def test_csmonitor_latimes_hindu_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _CSMONITOR_LATIMES_HINDU_PRIMARY:
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
        if source_id == "hindu_international":
            # Locked official International RSS has occasional empty
            # <description/> (~1/60 newsletter-style item). No other
            # official same-outlet international section is 0-empty.
            # Empty rate is not high; france24 swap not used. #43
            # thin-skip drops those items (no title-fill).
            empty = len(items) - nonempty
            assert nonempty > 0, f"{source_id} all descriptions empty"
            assert empty * 10 <= len(items), (
                f"{source_id} empty description: {empty}/{len(items)}"
            )
        else:
            assert nonempty == len(items), (
                f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
            )


def test_cbc_cna_elpais_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "cbc_world" in by_id
    assert by_id["cbc_world"].feed_url == "https://www.cbc.ca/webfeed/rss/rss-world"
    assert "cna_asia" in by_id
    assert by_id["cna_asia"].feed_url == (
        "https://www.channelnewsasia.com/api/v1/rss-outbound-feed"
        "?_format=xml&category=6511"
    )
    assert "elpais_en" in by_id
    assert by_id["elpais_en"].feed_url == (
        "https://feeds.elpais.com/mrss-s/pages/ep/site/"
        "english.elpais.com/portada"
    )
    assert "guardian_world" in by_id
    assert "bbc_world" in by_id
    assert "nyt_world" in by_id
    assert "aljazeera" in by_id
    assert "straitstimes_world" in by_id
    assert "smh_world" in by_id
    assert "nbc_world" in by_id
    assert "csmonitor_world" in by_id
    assert "latimes_world" in by_id
    assert "hindu_international" in by_id
    assert "cbs_news" in by_id
    assert by_id["cbc_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["cbc_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["cbc_world"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["cbc_world"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["cna_asia"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["cna_asia"].feed_url != by_id["scmp_asia"].feed_url
    assert by_id["cna_asia"].feed_url != by_id["straitstimes_world"].feed_url
    assert by_id["cna_asia"].feed_url != by_id["japan_times"].feed_url
    assert by_id["elpais_en"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["elpais_en"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["elpais_en"].feed_url != by_id["france24_en"].feed_url
    assert by_id["elpais_en"].feed_url != by_id["lemonde"].feed_url
    assert by_id["elpais_en"].feed_url != by_id["euronews"].feed_url
    assert by_id["cbc_world"].feed_url != by_id["cna_asia"].feed_url
    assert by_id["cbc_world"].feed_url != by_id["elpais_en"].feed_url
    assert by_id["cna_asia"].feed_url != by_id["elpais_en"].feed_url
    # yonhap / anadolu_world / trt_world are batch28 (primaries;
    # trt_world replaced independent_world after daily-fetch
    # inserted=0). semafor / france24_americas / middleeasteye
    # are batch29 (primaries; france24_americas / middleeasteye
    # replaced france24_asia / al_monitor after daily-fetch
    # inserted=0). Unused backups / replaced / title+link-only
    # feeds stay unregistered.
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _CBC_CNA_ELPAIS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_cbc_cna_elpais_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _CBC_CNA_ELPAIS_PRIMARY:
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
        if source_id == "cna_asia":
            # Locked official Asia RSS has occasional empty
            # <description/> (~2/20 wire-style items). No official
            # same-outlet Asia section is 0-empty (World 4/20,
            # Latest 12/20, Business 17/20). Empty rate is not high;
            # france24 swap not used. #43 thin-skip drops those
            # items (no title-fill).
            empty = len(items) - nonempty
            assert nonempty > 0, f"{source_id} all descriptions empty"
            assert empty * 10 <= len(items), (
                f"{source_id} empty description: {empty}/{len(items)}"
            )
        else:
            assert nonempty == len(items), (
                f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
            )


def test_yonhap_anadolu_trt_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "yonhap" in by_id
    assert by_id["yonhap"].feed_url == "https://en.yna.co.kr/RSS/news.xml"
    assert "anadolu_world" in by_id
    assert by_id["anadolu_world"].feed_url == (
        "https://www.aa.com.tr/en/rss/default?cat=world"
    )
    assert "trt_world" in by_id
    assert by_id["trt_world"].feed_url == "https://www.trtworld.com/feed/rss.xml"
    assert "guardian_world" in by_id
    assert "bbc_world" in by_id
    assert "nyt_world" in by_id
    assert "aljazeera" in by_id
    assert "straitstimes_world" in by_id
    assert "smh_world" in by_id
    assert "nbc_world" in by_id
    assert "csmonitor_world" in by_id
    assert "latimes_world" in by_id
    assert "hindu_international" in by_id
    assert "cbc_world" in by_id
    assert "cna_asia" in by_id
    assert "elpais_en" in by_id
    assert "cbs_news" in by_id
    assert "japan_times" in by_id
    assert by_id["yonhap"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["yonhap"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["yonhap"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["yonhap"].feed_url != by_id["japan_times"].feed_url
    assert by_id["yonhap"].feed_url != by_id["cna_asia"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["aljazeera"].feed_url
    assert by_id["trt_world"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["trt_world"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["trt_world"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["trt_world"].feed_url != by_id["aljazeera"].feed_url
    assert by_id["trt_world"].feed_url != by_id["anadolu_world"].feed_url
    assert by_id["yonhap"].feed_url != by_id["anadolu_world"].feed_url
    assert by_id["yonhap"].feed_url != by_id["trt_world"].feed_url
    assert by_id["anadolu_world"].feed_url != by_id["trt_world"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # independent_world is the daily-fetch RED slot — do not keep live.
    # cbs_world / france24_asia / guardian_media are batch39.
    # al_monitor stays unregistered (replaced in batch29; not a live CAP slot).
    # nikkei / indian_express stay unregistered (empty desc — product skipped).
    # semafor / france24_americas / middleeasteye are batch29 (primaries).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _YONHAP_ANADOLU_TRT_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_yonhap_anadolu_trt_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _YONHAP_ANADOLU_TRT_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
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


def test_semafor_france24_americas_middleeasteye_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "semafor" in by_id
    assert by_id["semafor"].feed_url == "https://www.semafor.com/rss.xml"
    assert "france24_americas" in by_id
    assert by_id["france24_americas"].feed_url == (
        "https://www.france24.com/en/americas/rss"
    )
    assert "middleeasteye" in by_id
    assert by_id["middleeasteye"].feed_url == "https://www.middleeasteye.net/rss"
    assert "france24_en" in by_id
    assert "guardian_world" in by_id
    assert "guardian_americas" in by_id
    assert "bbc_world" in by_id
    assert "nyt_world" in by_id
    assert "aljazeera" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_middle_east" in by_id
    assert "guardian_middle_east" in by_id
    assert "cna_asia" in by_id
    assert "trt_world" in by_id
    assert "yonhap" in by_id
    assert "anadolu_world" in by_id
    assert "axios" in by_id
    assert by_id["semafor"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["semafor"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["semafor"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["semafor"].feed_url != by_id["axios"].feed_url
    assert by_id["semafor"].feed_url != by_id["trt_world"].feed_url
    assert by_id["france24_americas"].feed_url != by_id["france24_en"].feed_url
    assert by_id["france24_americas"].feed_url != "https://www.france24.com/en/rss"
    assert by_id["france24_americas"].feed_url != (
        "https://www.france24.com/en/europe/rss"
    )
    assert by_id["france24_americas"].feed_url != (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert by_id["france24_americas"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["france24_americas"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["france24_americas"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["middleeasteye"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["middleeasteye"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["middleeasteye"].feed_url != by_id["aljazeera"].feed_url
    assert by_id["middleeasteye"].feed_url != by_id["trt_world"].feed_url
    assert by_id["middleeasteye"].feed_url != by_id["anadolu_world"].feed_url
    assert by_id["semafor"].feed_url != by_id["france24_americas"].feed_url
    assert by_id["semafor"].feed_url != by_id["middleeasteye"].feed_url
    assert by_id["france24_americas"].feed_url != by_id["middleeasteye"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # al_monitor stays unregistered (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not keep live.
    # cbs_world / france24_asia / guardian_media are batch39.
    # nikkei / indian_express are empty-desc — product skipped.
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _SEMAFOR_FRANCE24_AMERICAS_MIDDLEEASTEYE_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_semafor_france24_americas_middleeasteye_feeds_live_http_200():
    """Hit the three live feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _SEMAFOR_FRANCE24_AMERICAS_MIDDLEEASTEYE_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
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


def test_scmp_business_rfi_asia_theconversation_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "scmp_business" in by_id
    assert by_id["scmp_business"].feed_url == "https://www.scmp.com/rss/92/feed"
    assert "rfi_asia" in by_id
    assert by_id["rfi_asia"].feed_url == "https://www.rfi.fr/en/tag/asia/rss"
    assert "theconversation" in by_id
    assert by_id["theconversation"].feed_url == (
        "https://theconversation.com/articles.atom"
    )
    assert "scmp" in by_id
    assert "scmp_asia" in by_id
    assert "scmp_china" in by_id
    assert "rfi_en" in by_id
    assert "bbc_asia" in by_id
    assert "japan_times" in by_id
    assert "cna_asia" in by_id
    assert "semafor" in by_id
    assert "france24_americas" in by_id
    assert "middleeasteye" in by_id
    assert "guardian_business" in by_id
    assert "bbc_business" in by_id
    assert "nyt_business" in by_id
    assert by_id["scmp_business"].feed_url != by_id["scmp"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["scmp_asia"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["scmp_china"].feed_url
    assert by_id["scmp_business"].feed_url != "https://www.scmp.com/rss/2/feed"
    assert by_id["scmp_business"].feed_url != "https://www.scmp.com/rss/3/feed"
    assert by_id["scmp_business"].feed_url != "https://www.scmp.com/rss/4/feed"
    assert by_id["scmp_business"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["rfi_asia"].feed_url != by_id["rfi_en"].feed_url
    assert by_id["rfi_asia"].feed_url != "https://www.rfi.fr/en/rss"
    assert by_id["rfi_asia"].feed_url != "https://www.rfi.fr/en/asia-pacific/rss"
    assert by_id["rfi_asia"].feed_url != "https://www.rfi.fr/en/international/rss"
    assert by_id["rfi_asia"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["rfi_asia"].feed_url != by_id["scmp_asia"].feed_url
    assert by_id["rfi_asia"].feed_url != by_id["japan_times"].feed_url
    assert by_id["rfi_asia"].feed_url != by_id["cna_asia"].feed_url
    assert by_id["theconversation"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["theconversation"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["theconversation"].feed_url != by_id["mit_tr"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["rfi_asia"].feed_url
    assert by_id["scmp_business"].feed_url != by_id["theconversation"].feed_url
    assert by_id["rfi_asia"].feed_url != by_id["theconversation"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # forbes_innovation is batch33 (promoted from unused backup).
    # propublica is batch32 (promoted from unused backup).
    # al_monitor stays unregistered (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not keep live.
    # cbs_world / france24_asia / guardian_media are batch39.
    # nikkei / indian_express are empty-desc — product skipped.
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    for source_id, expected in _SCMP_BUSINESS_RFI_ASIA_THECONVERSATION_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_scmp_business_rfi_asia_theconversation_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _SCMP_BUSINESS_RFI_ASIA_THECONVERSATION_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # Atom (theconversation) uses namespaced title / link@href /
        # published; RSS 2.0 (scmp_business / rfi_asia) uses the
        # un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_arts_guardian_sport_intercept_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_arts" in by_id
    assert by_id["nyt_arts"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml"
    )
    assert "guardian_sport" in by_id
    assert by_id["guardian_sport"].feed_url == (
        "https://www.theguardian.com/sport/rss"
    )
    assert "intercept" in by_id
    assert by_id["intercept"].feed_url == "https://theintercept.com/feed/"
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "scmp_business" in by_id
    assert "rfi_asia" in by_id
    assert "theconversation" in by_id
    assert by_id["nyt_arts"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_arts"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml"
    )
    assert by_id["guardian_sport"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_sport"].feed_url != "https://www.theguardian.com/film/rss"
    assert by_id["intercept"].feed_url != by_id["theconversation"].feed_url
    assert by_id["intercept"].feed_url != by_id["semafor"].feed_url
    assert by_id["intercept"].feed_url != by_id["axios"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["nyt_arts"].feed_url != by_id["intercept"].feed_url
    assert by_id["guardian_sport"].feed_url != by_id["intercept"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # nyt_opinion / guardian_film are batch32 (promoted from unused
    # backups). cbs_world / france24_asia / guardian_media are
    # batch39. al_monitor stays unregistered (replaced in
    # batch29; not a live CAP slot). independent_world is the
    # daily-fetch RED slot — do not keep live. nikkei /
    # indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science are not this batch.
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    for source_id, expected in _NYT_ARTS_GUARDIAN_SPORT_INTERCEPT_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_arts_guardian_sport_intercept_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_ARTS_GUARDIAN_SPORT_INTERCEPT_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_arts / guardian_sport / intercept) uses the
        # un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_opinion_guardian_film_propublica_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_opinion" in by_id
    assert by_id["nyt_opinion"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml"
    )
    assert "guardian_film" in by_id
    assert by_id["guardian_film"].feed_url == (
        "https://www.theguardian.com/film/rss"
    )
    assert "propublica" in by_id
    assert by_id["propublica"].feed_url == (
        "https://www.propublica.org/feeds/propublica/main"
    )
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "intercept" in by_id
    assert "rfi_en" in by_id
    assert "rfi_asia" in by_id
    assert "dw_en" in by_id
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["propublica"].feed_url != by_id["intercept"].feed_url
    assert by_id["propublica"].feed_url != by_id["theconversation"].feed_url
    assert by_id["propublica"].feed_url != by_id["semafor"].feed_url
    assert by_id["propublica"].feed_url != by_id["axios"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["nyt_opinion"].feed_url != by_id["propublica"].feed_url
    assert by_id["guardian_film"].feed_url != by_id["propublica"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # forbes_innovation / dw_world / rfi_americas are batch33
    # (promoted from unused backups). cbs_world / france24_asia /
    # guardian_media are batch39. al_monitor stays unregistered
    # (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not
    # keep live. nikkei / indian_express are empty-desc —
    # product skipped. sky_tech / restofworld / ars_science /
    # thehill / politico are not this batch (politico is
    # X-handle only).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    for source_id, expected in _NYT_OPINION_GUARDIAN_FILM_PROPUBLICA_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_opinion_guardian_film_propublica_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_OPINION_GUARDIAN_FILM_PROPUBLICA_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_opinion / guardian_film / propublica) uses the
        # un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_forbes_innovation_dw_world_rfi_americas_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "forbes_innovation" in by_id
    assert by_id["forbes_innovation"].feed_url == (
        "https://www.forbes.com/innovation/feed/"
    )
    assert "dw_world" in by_id
    assert by_id["dw_world"].feed_url == "https://rss.dw.com/rdf/rss-en-world"
    assert "rfi_americas" in by_id
    assert by_id["rfi_americas"].feed_url == (
        "https://www.rfi.fr/en/tag/latin-america/rss"
    )
    assert "dw_en" in by_id
    assert "rfi_en" in by_id
    assert "rfi_asia" in by_id
    assert "nyt_opinion" in by_id
    assert "guardian_film" in by_id
    assert "propublica" in by_id
    assert "wired" in by_id
    assert "mit_tr" in by_id
    assert "bbc_latin_america" in by_id
    assert "guardian_americas" in by_id
    assert "france24_americas" in by_id
    assert by_id["forbes_innovation"].feed_url != (
        "https://www.forbes.com/innovation/feed"
    )
    assert by_id["dw_world"].feed_url != by_id["dw_en"].feed_url
    assert by_id["dw_world"].feed_url != "https://rss.dw.com/rdf/rss-en-all"
    assert by_id["dw_world"].feed_url != "https://rss.dw.com/atom/rss-en-world"
    assert by_id["rfi_americas"].feed_url != by_id["rfi_en"].feed_url
    assert by_id["rfi_americas"].feed_url != by_id["rfi_asia"].feed_url
    assert by_id["rfi_americas"].feed_url != "https://www.rfi.fr/en/rss"
    assert by_id["rfi_americas"].feed_url != "https://www.rfi.fr/en/americas/rss"
    assert by_id["rfi_americas"].feed_url != "https://www.rfi.fr/en/international/rss"
    assert by_id["rfi_americas"].feed_url != "https://www.rfi.fr/en/tag/americas/rss"
    assert by_id["rfi_americas"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["rfi_americas"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["rfi_americas"].feed_url != by_id["france24_americas"].feed_url
    assert by_id["forbes_innovation"].feed_url != by_id["wired"].feed_url
    assert by_id["forbes_innovation"].feed_url != by_id["mit_tr"].feed_url
    assert by_id["forbes_innovation"].feed_url != by_id["dw_world"].feed_url
    assert by_id["forbes_innovation"].feed_url != by_id["rfi_americas"].feed_url
    assert by_id["dw_world"].feed_url != by_id["rfi_americas"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # nyt_movies / guardian_music / guardian_stage are batch34
    # (promoted from unused backups). nyt_books /
    # guardian_books / npr_arts are batch35 (promoted from
    # unused backups). cbs_world / france24_asia /
    # guardian_media are batch39. al_monitor stays
    # unregistered (replaced in batch29; not a live CAP
    # slot). independent_world is the daily-fetch RED
    # slot — do not keep live. nikkei / indian_express are
    # empty-desc — product skipped. sky_tech /
    # restofworld / ars_science / thehill / politico are
    # not this batch (politico is X-handle only).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    for source_id, expected in _FORBES_INNOVATION_DW_WORLD_RFI_AMERICAS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_forbes_innovation_dw_world_rfi_americas_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _FORBES_INNOVATION_DW_WORLD_RFI_AMERICAS_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (forbes_innovation / rfi_americas) uses the
        # un-namespaced element text. RSS 1.0 / RDF (dw_world)
        # uses the rss-1.0 title / link plus dc:date.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_movies_guardian_music_guardian_stage_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_movies" in by_id
    assert by_id["nyt_movies"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml"
    )
    assert "guardian_music" in by_id
    assert by_id["guardian_music"].feed_url == (
        "https://www.theguardian.com/music/rss"
    )
    assert "guardian_stage" in by_id
    assert by_id["guardian_stage"].feed_url == (
        "https://www.theguardian.com/stage/rss"
    )
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "forbes_innovation" in by_id
    assert "dw_world" in by_id
    assert "rfi_americas" in by_id
    assert by_id["nyt_movies"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_movies"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/MoviesAndTV.xml"
    )
    assert by_id["nyt_movies"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Television.xml"
    )
    assert by_id["nyt_movies"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml"
    )
    assert by_id["guardian_music"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_music"].feed_url != "https://www.theguardian.com/us/music/rss"
    assert by_id["guardian_music"].feed_url != "https://www.theguardian.com/books/rss"
    assert by_id["guardian_stage"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_stage"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_stage"].feed_url != "https://www.theguardian.com/us/stage/rss"
    assert by_id["nyt_movies"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["nyt_movies"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_music"].feed_url != by_id["guardian_stage"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # nyt_books / guardian_books / npr_arts are batch35 (promoted
    # from unused backups). cbs_world / france24_asia /
    # guardian_media are batch39. al_monitor stays unregistered
    # (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not
    # keep live. nikkei / indian_express are empty-desc —
    # product skipped. sky_tech / restofworld / ars_science /
    # thehill / politico / abc_intl / sunday_review are not
    # this batch (politico is X-handle only).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    for source_id, expected in _NYT_MOVIES_GUARDIAN_MUSIC_GUARDIAN_STAGE_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_movies_guardian_music_guardian_stage_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_MOVIES_GUARDIAN_MUSIC_GUARDIAN_STAGE_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_movies / guardian_music / guardian_stage)
        # uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_books_guardian_books_npr_arts_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_books" in by_id
    assert by_id["nyt_books"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml"
    )
    assert "guardian_books" in by_id
    assert by_id["guardian_books"].feed_url == (
        "https://www.theguardian.com/books/rss"
    )
    assert "npr_arts" in by_id
    assert by_id["npr_arts"].feed_url == "https://feeds.npr.org/1008/rss.xml"
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "nyt_movies" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "guardian_music" in by_id
    assert "guardian_stage" in by_id
    assert "npr_news" in by_id
    assert "npr_world" in by_id
    assert by_id["npr_news"].feed_url == "https://feeds.npr.org/1001/rss.xml"
    assert by_id["npr_world"].feed_url == "https://feeds.npr.org/1004/rss.xml"
    assert by_id["nyt_books"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_books"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Dining.xml"
    )
    assert by_id["nyt_books"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Food.xml"
    )
    assert by_id["guardian_books"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_books"].feed_url != (
        "https://www.theguardian.com/us/books/rss"
    )
    assert by_id["guardian_books"].feed_url != (
        "https://www.theguardian.com/tv-and-radio/rss"
    )
    assert by_id["npr_arts"].feed_url != by_id["npr_news"].feed_url
    assert by_id["npr_arts"].feed_url != by_id["npr_world"].feed_url
    assert by_id["npr_arts"].feed_url != "https://feeds.npr.org/1007/rss.xml"
    assert by_id["npr_arts"].feed_url != "https://feeds.npr.org/1048/rss.xml"
    assert by_id["nyt_books"].feed_url != by_id["guardian_books"].feed_url
    assert by_id["nyt_books"].feed_url != by_id["npr_arts"].feed_url
    assert by_id["guardian_books"].feed_url != by_id["npr_arts"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # nyt_food / guardian_tv / npr_science are batch36 (promoted
    # from unused backups). nyt_travel / guardian_fashion /
    # nyt_economy are batch37 (nyt_economy hard-swapped in for
    # npr_business). nyt_realestate / guardian_lifeandstyle /
    # bbc_entertainment are batch38.
    # Unused backups list is empty this batch.
    # al_monitor stays unregistered (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not keep live.
    # cbs_world / france24_asia / guardian_media are batch39.
    # nikkei / indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science / thehill / politico /
    # abc_intl / sunday_review / nyt_sports
    # are not this batch (politico is X-handle only).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in _NYT_BOOKS_GUARDIAN_BOOKS_NPR_ARTS_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_books_guardian_books_npr_arts_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_BOOKS_GUARDIAN_BOOKS_NPR_ARTS_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_books / guardian_books / npr_arts)
        # uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_food_guardian_tv_npr_science_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_food" in by_id
    assert by_id["nyt_food"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml"
    )
    assert "guardian_tv" in by_id
    assert by_id["guardian_tv"].feed_url == (
        "https://www.theguardian.com/tv-and-radio/rss"
    )
    assert "npr_science" in by_id
    assert by_id["npr_science"].feed_url == "https://feeds.npr.org/1007/rss.xml"
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "nyt_movies" in by_id
    assert "nyt_books" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "guardian_music" in by_id
    assert "guardian_stage" in by_id
    assert "guardian_books" in by_id
    assert "npr_news" in by_id
    assert "npr_world" in by_id
    assert "npr_arts" in by_id
    assert by_id["npr_news"].feed_url == "https://feeds.npr.org/1001/rss.xml"
    assert by_id["npr_world"].feed_url == "https://feeds.npr.org/1004/rss.xml"
    assert by_id["npr_arts"].feed_url == "https://feeds.npr.org/1008/rss.xml"
    assert by_id["nyt_food"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_food"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Dining.xml"
    )
    assert by_id["nyt_food"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Food.xml"
    )
    assert by_id["nyt_food"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml"
    )
    assert by_id["guardian_tv"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["guardian_books"].feed_url
    assert by_id["guardian_tv"].feed_url != (
        "https://www.theguardian.com/us/tv-and-radio/rss"
    )
    assert by_id["guardian_tv"].feed_url != (
        "https://www.theguardian.com/fashion/rss"
    )
    assert by_id["npr_science"].feed_url != by_id["npr_news"].feed_url
    assert by_id["npr_science"].feed_url != by_id["npr_world"].feed_url
    assert by_id["npr_science"].feed_url != by_id["npr_arts"].feed_url
    assert by_id["npr_science"].feed_url != "https://feeds.npr.org/1006/rss.xml"
    assert by_id["npr_science"].feed_url != "https://feeds.npr.org/1048/rss.xml"
    assert by_id["nyt_food"].feed_url != by_id["guardian_tv"].feed_url
    assert by_id["nyt_food"].feed_url != by_id["npr_science"].feed_url
    assert by_id["guardian_tv"].feed_url != by_id["npr_science"].feed_url
    # Unused backups / replaced / title+link-only feeds stay unregistered.
    # nyt_travel / guardian_fashion / nyt_economy are batch37
    # (nyt_economy hard-swapped in for npr_business).
    # nyt_realestate / guardian_lifeandstyle /
    # bbc_entertainment are batch38. Unused backups list
    # is empty this batch — mention only the
    # still-unregistered replaced / empty-desc / not-this-batch ids.
    # al_monitor stays unregistered (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not keep live.
    # cbs_world / france24_asia / guardian_media are batch39.
    # nikkei / indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science / thehill / politico /
    # abc_intl / sunday_review / nyt_sports
    # are not this batch (politico is X-handle only).
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in _NYT_FOOD_GUARDIAN_TV_NPR_SCIENCE_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_food_guardian_tv_npr_science_feeds_live_http_200():
    """Hit the three new feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_FOOD_GUARDIAN_TV_NPR_SCIENCE_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_food / guardian_tv / npr_science)
        # uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
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


def test_nyt_travel_guardian_fashion_nyt_economy_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_travel" in by_id
    assert by_id["nyt_travel"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml"
    )
    assert "guardian_fashion" in by_id
    assert by_id["guardian_fashion"].feed_url == (
        "https://www.theguardian.com/fashion/rss"
    )
    assert "nyt_economy" in by_id
    assert by_id["nyt_economy"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"
    )
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "nyt_movies" in by_id
    assert "nyt_books" in by_id
    assert "nyt_food" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "guardian_music" in by_id
    assert "guardian_stage" in by_id
    assert "guardian_books" in by_id
    assert "guardian_tv" in by_id
    assert "npr_news" in by_id
    assert "npr_world" in by_id
    assert "npr_arts" in by_id
    assert "npr_science" in by_id
    assert by_id["npr_news"].feed_url == "https://feeds.npr.org/1001/rss.xml"
    assert by_id["npr_world"].feed_url == "https://feeds.npr.org/1004/rss.xml"
    assert by_id["npr_arts"].feed_url == "https://feeds.npr.org/1008/rss.xml"
    assert by_id["npr_science"].feed_url == "https://feeds.npr.org/1007/rss.xml"
    assert by_id["nyt_travel"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_food"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["nyt_travel"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/TravelGuide.xml"
    )
    assert by_id["nyt_travel"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Escapes.xml"
    )
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_books"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["guardian_tv"].feed_url
    assert by_id["guardian_fashion"].feed_url != (
        "https://www.theguardian.com/uk/fashion/rss"
    )
    assert by_id["guardian_fashion"].feed_url != (
        "https://www.theguardian.com/us/fashion/rss"
    )
    assert by_id["nyt_economy"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_food"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["nyt_travel"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["nyt_economy"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["nyt_economy"].feed_url != "https://feeds.npr.org/1006/rss.xml"
    assert by_id["nyt_economy"].feed_url != "https://feeds.npr.org/1017/rss.xml"
    assert by_id["nyt_travel"].feed_url != by_id["guardian_fashion"].feed_url
    assert by_id["nyt_travel"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["guardian_fashion"].feed_url != by_id["nyt_economy"].feed_url
    # Unused backups list is empty this batch. Replaced /
    # title+link-only / empty-desc / not-this-batch feeds stay
    # unregistered. npr_business was hard-swapped out — do not
    # keep live and do not register as a backup. cnbc_top is
    # now registered (batch39 hard-swap of guardian_media).
    # bloomberg_markets / guardian_opinion / nyt_magazine
    # are batch40 (guardian_opinion hard-swapped in for
    # guardian_economics after public insert=1 <5).
    # france24_middle_east / nyt_personaltech /
    # france24_africa are batch41. Unused batch41 backups
    # reuters_world / nyt_sports / guardian_food stay
    # unregistered. nyt_realestate /
    # guardian_lifeandstyle / bbc_entertainment are
    # batch38. cbs_world / france24_asia / cnbc_top are
    # batch39.
    # al_monitor stays unregistered (replaced in batch29;
    # not a live CAP slot). independent_world is the
    # daily-fetch RED slot — do not keep live. nikkei /
    # indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science / thehill /
    # politico / abc_intl / sunday_review / nyt_sports
    # are not this batch (politico is X-handle only).
    assert "npr_business" not in by_id
    assert "guardian_media" not in by_id
    assert "guardian_economics" not in by_id
    assert "reuters_world" not in by_id
    assert "guardian_food" not in by_id
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in _NYT_TRAVEL_GUARDIAN_FASHION_NYT_ECONOMY_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_travel_guardian_fashion_nyt_economy_feeds_live_http_200():
    """Hit the three batch37 feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_TRAVEL_GUARDIAN_FASHION_NYT_ECONOMY_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_travel / guardian_fashion / nyt_economy)
        # uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0.
        # nyt_travel / guardian_fashion stay 100% nonempty.
        # nyt_economy Economy.xml includes occasional NYT
        # liveblog "Here's the latest." items with empty
        # description; those skip insert. Require enough
        # insertable items to stay above the ≥10 floor.
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        if source_id == "nyt_economy":
            assert nonempty >= 10, (
                f"{source_id} insertable descriptions below floor: "
                f"{nonempty}/{len(items)}"
            )
        else:
            assert nonempty == len(items), (
                f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
            )


def test_nyt_realestate_guardian_lifeandstyle_bbc_entertainment_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "nyt_realestate" in by_id
    assert by_id["nyt_realestate"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml"
    )
    assert "guardian_lifeandstyle" in by_id
    assert by_id["guardian_lifeandstyle"].feed_url == (
        "https://www.theguardian.com/lifeandstyle/rss"
    )
    assert "bbc_entertainment" in by_id
    assert by_id["bbc_entertainment"].feed_url == (
        "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"
    )
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
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "nyt_movies" in by_id
    assert "nyt_books" in by_id
    assert "nyt_food" in by_id
    assert "nyt_travel" in by_id
    assert "nyt_economy" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_business" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "guardian_music" in by_id
    assert "guardian_stage" in by_id
    assert "guardian_books" in by_id
    assert "guardian_tv" in by_id
    assert "guardian_fashion" in by_id
    assert "bbc_zh_simp" in by_id
    assert "bbc_world" in by_id
    assert "bbc_technology" in by_id
    assert "bbc_business" in by_id
    assert "bbc_science" in by_id
    assert "bbc_asia" in by_id
    assert "bbc_europe" in by_id
    assert "bbc_us_canada" in by_id
    assert "bbc_middle_east" in by_id
    assert "bbc_africa" in by_id
    assert "bbc_latin_america" in by_id
    assert "bbc_health" in by_id
    assert "bbc_china" in by_id
    assert "bbc_education" in by_id
    assert "bbc_uk" in by_id
    assert "bbc_politics" in by_id
    assert "bbc_scotland" in by_id
    assert "bbc_wales" in by_id
    assert "bbc_england" in by_id
    assert "bbc_northern_ireland" in by_id
    assert by_id["nyt_travel"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml"
    )
    assert by_id["guardian_fashion"].feed_url == (
        "https://www.theguardian.com/fashion/rss"
    )
    assert by_id["nyt_economy"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"
    )
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_food"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_travel"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["nyt_realestate"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/HomeandGarden.xml"
    )
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_books"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_tv"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["guardian_fashion"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != (
        "https://www.theguardian.com/uk/lifeandstyle/rss"
    )
    assert by_id["guardian_lifeandstyle"].feed_url != (
        "https://www.theguardian.com/us/lifeandstyle/rss"
    )
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_zh_simp"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_world"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_technology"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_science"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_asia"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_europe"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_us_canada"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_latin_america"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_health"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_china"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_education"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_uk"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_politics"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_scotland"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_wales"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_england"].feed_url
    assert by_id["bbc_entertainment"].feed_url != by_id["bbc_northern_ireland"].feed_url
    assert by_id["bbc_entertainment"].feed_url != (
        "https://feeds.bbci.co.uk/news/entertainment/rss.xml"
    )
    assert by_id["bbc_entertainment"].feed_url != (
        "https://feeds.bbci.co.uk/news/culture/rss.xml"
    )
    assert by_id["bbc_entertainment"].feed_url != (
        "https://www.bbc.com/culture/feed.xml"
    )
    assert by_id["nyt_realestate"].feed_url != by_id["guardian_lifeandstyle"].feed_url
    assert by_id["nyt_realestate"].feed_url != by_id["bbc_entertainment"].feed_url
    assert by_id["guardian_lifeandstyle"].feed_url != by_id["bbc_entertainment"].feed_url
    # Unused backups / replaced / title+link-only / empty-desc /
    # not-this-batch feeds stay unregistered. cbs_world /
    # france24_asia / cnbc_top are batch39 (cnbc_top
    # hard-swapped in for guardian_media after public
    # insert=4 <5). bloomberg_markets / guardian_opinion /
    # nyt_magazine are batch40 (guardian_opinion
    # hard-swapped in for guardian_economics after public
    # insert=1 <5). france24_middle_east /
    # nyt_personaltech / france24_africa are batch41.
    # Unused batch41 backups reuters_world / nyt_sports /
    # guardian_food stay unregistered. npr_business was
    # hard-swapped out in batch37 — do not keep live and do
    # not register as a backup. al_monitor stays
    # unregistered (replaced in batch29; not a live CAP
    # slot). independent_world is the daily-fetch RED slot
    # — do not keep live. nikkei / indian_express are
    # empty-desc — product skipped. sky_tech / restofworld /
    # ars_science / thehill / politico / abc_intl /
    # sunday_review / nyt_sports are not this batch
    # (politico is X-handle only).
    assert "npr_business" not in by_id
    assert "guardian_media" not in by_id
    assert "guardian_economics" not in by_id
    assert "reuters_world" not in by_id
    assert "guardian_food" not in by_id
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in (
        _NYT_REALESTATE_GUARDIAN_LIFEANDSTYLE_BBC_ENTERTAINMENT_PRIMARY.items()
    ):
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_nyt_realestate_guardian_lifeandstyle_bbc_entertainment_feeds_live_http_200():
    """Hit the three batch38 feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _NYT_REALESTATE_GUARDIAN_LIFEANDSTYLE_BBC_ENTERTAINMENT_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (nyt_realestate / guardian_lifeandstyle /
        # bbc_entertainment) uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product
        # lock requires non-empty RSS description/summary on these
        # three feeds (all live-diff winners were 100% nonempty).
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_cbs_world_france24_asia_cnbc_top_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "cbs_world" in by_id
    assert by_id["cbs_world"].feed_url == "https://www.cbsnews.com/latest/rss/world"
    assert "france24_asia" in by_id
    assert by_id["france24_asia"].feed_url == (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert "cnbc_top" in by_id
    assert by_id["cnbc_top"].feed_url == (
        "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    )
    assert "cbs_news" in by_id
    assert by_id["cbs_news"].feed_url == "https://www.cbsnews.com/latest/rss/main"
    assert "france24_en" in by_id
    assert "france24_americas" in by_id
    assert "nyt_realestate" in by_id
    assert "guardian_lifeandstyle" in by_id
    assert "bbc_entertainment" in by_id
    assert "nyt_economy" in by_id
    assert "nyt_business" in by_id
    assert "bbc_business" in by_id
    assert "guardian_business" in by_id
    assert by_id["nyt_realestate"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml"
    )
    assert by_id["guardian_lifeandstyle"].feed_url == (
        "https://www.theguardian.com/lifeandstyle/rss"
    )
    assert by_id["bbc_entertainment"].feed_url == (
        "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"
    )
    assert by_id["cbs_world"].feed_url != by_id["cbs_news"].feed_url
    assert by_id["cbs_world"].feed_url != "https://www.cbsnews.com/latest/rss/world-news"
    assert by_id["france24_asia"].feed_url != by_id["france24_en"].feed_url
    assert by_id["france24_asia"].feed_url != by_id["france24_americas"].feed_url
    assert by_id["france24_asia"].feed_url != "https://www.france24.com/en/rss"
    assert by_id["france24_asia"].feed_url != "https://www.france24.com/en/europe/rss"
    assert by_id["france24_asia"].feed_url != "https://www.france24.com/en/americas/rss"
    assert by_id["france24_asia"].feed_url != "https://www.france24.com/en/asia/rss"
    assert by_id["cnbc_top"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["cnbc_top"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["cnbc_top"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["cnbc_top"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["cnbc_top"].feed_url != "https://www.theguardian.com/media/rss"
    assert by_id["cnbc_top"].feed_url != "https://feeds.bloomberg.com/markets/news.rss"
    assert by_id["cnbc_top"].feed_url != (
        "https://www.theguardian.com/business/economics/rss"
    )
    assert by_id["cbs_world"].feed_url != by_id["france24_asia"].feed_url
    assert by_id["cbs_world"].feed_url != by_id["cnbc_top"].feed_url
    assert by_id["france24_asia"].feed_url != by_id["cnbc_top"].feed_url
    # Unused backups / replaced / title+link-only / empty-desc /
    # not-this-batch feeds stay unregistered. guardian_media was
    # hard-swapped out this batch (public insert=4 <5) — do not
    # keep live and do not register as a backup. bloomberg_markets
    # / guardian_opinion / nyt_magazine are batch40 (those
    # unused batch39 backups bloomberg_markets /
    # guardian_economics were registered there; guardian_economics
    # was then hard-swapped for guardian_opinion after public
    # insert=1 <5). france24_middle_east / nyt_personaltech /
    # france24_africa are batch41. Unused batch41 backups
    # reuters_world / nyt_sports / guardian_food stay
    # unregistered. npr_business was
    # hard-swapped out in batch37 — do not keep live and
    # do not register as a backup. al_monitor stays
    # unregistered (replaced in batch29; not a live CAP slot).
    # independent_world is the daily-fetch RED slot — do not
    # keep live. nikkei / indian_express are empty-desc —
    # product skipped. sky_tech / restofworld / ars_science /
    # thehill / politico / abc_intl / sunday_review /
    # nyt_sports are not this batch (politico is X-handle only).
    assert "npr_business" not in by_id
    assert "guardian_media" not in by_id
    assert "guardian_economics" not in by_id
    assert "reuters_world" not in by_id
    assert "guardian_food" not in by_id
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in _CBS_WORLD_FRANCE24_ASIA_CNBC_TOP_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_cbs_world_france24_asia_cnbc_top_feeds_live_http_200():
    """Hit the three batch39 feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _CBS_WORLD_FRANCE24_ASIA_CNBC_TOP_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (cbs_world / france24_asia / cnbc_top)
        # uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product
        # lock requires non-empty RSS description/summary on these
        # three feeds (all live-diff winners were 100% nonempty).
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_bloomberg_markets_guardian_opinion_nyt_magazine_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "bloomberg_markets" in by_id
    assert by_id["bloomberg_markets"].feed_url == (
        "https://feeds.bloomberg.com/markets/news.rss"
    )
    assert "guardian_opinion" in by_id
    assert by_id["guardian_opinion"].feed_url == (
        "https://www.theguardian.com/commentisfree/rss"
    )
    assert "nyt_magazine" in by_id
    assert by_id["nyt_magazine"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Magazine.xml"
    )
    assert "cbs_world" in by_id
    assert "france24_asia" in by_id
    assert "cnbc_top" in by_id
    assert "france24_middle_east" in by_id
    assert "nyt_personaltech" in by_id
    assert "france24_africa" in by_id
    assert "nyt_realestate" in by_id
    assert "guardian_lifeandstyle" in by_id
    assert "bbc_entertainment" in by_id
    assert "nyt_economy" in by_id
    assert "nyt_business" in by_id
    assert "bbc_business" in by_id
    assert "guardian_business" in by_id
    assert "scmp_business" in by_id
    assert "nyt_world" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_science" in by_id
    assert "nyt_climate" in by_id
    assert "nyt_health" in by_id
    assert "nyt_education" in by_id
    assert "nyt_politics" in by_id
    assert "nyt_us" in by_id
    assert "nyt_europe" in by_id
    assert "nyt_upshot" in by_id
    assert "nyt_africa" in by_id
    assert "nyt_arts" in by_id
    assert "nyt_opinion" in by_id
    assert "nyt_movies" in by_id
    assert "nyt_books" in by_id
    assert "nyt_food" in by_id
    assert "nyt_travel" in by_id
    assert "guardian_world" in by_id
    assert "guardian_technology" in by_id
    assert "guardian_us" in by_id
    assert "guardian_environment" in by_id
    assert "guardian_science" in by_id
    assert "guardian_australia" in by_id
    assert "guardian_americas" in by_id
    assert "guardian_uk" in by_id
    assert "guardian_europe" in by_id
    assert "guardian_global_dev" in by_id
    assert "guardian_law" in by_id
    assert "guardian_society" in by_id
    assert "guardian_cities" in by_id
    assert "guardian_world_africa" in by_id
    assert "guardian_politics" in by_id
    assert "guardian_middle_east" in by_id
    assert "guardian_sport" in by_id
    assert "guardian_film" in by_id
    assert "guardian_music" in by_id
    assert "guardian_stage" in by_id
    assert "guardian_books" in by_id
    assert "guardian_tv" in by_id
    assert "guardian_fashion" in by_id
    assert by_id["cbs_world"].feed_url == "https://www.cbsnews.com/latest/rss/world"
    assert by_id["france24_asia"].feed_url == (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert by_id["cnbc_top"].feed_url == (
        "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    )
    assert by_id["bloomberg_markets"].feed_url != by_id["cnbc_top"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["bbc_business"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["scmp_business"].feed_url
    assert by_id["bloomberg_markets"].feed_url != (
        "https://www.bloomberg.com/feeds/markets/news.rss"
    )
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_world"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_technology"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_us"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_environment"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_business"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_science"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_australia"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_americas"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_uk"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_europe"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_global_dev"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_law"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_society"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_cities"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_politics"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_sport"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_film"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_music"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_stage"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_books"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_tv"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_fashion"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["guardian_lifeandstyle"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["guardian_opinion"].feed_url != (
        "https://www.theguardian.com/business/economics/rss"
    )
    assert by_id["guardian_opinion"].feed_url != (
        "https://www.theguardian.com/uk/commentisfree/rss"
    )
    assert by_id["guardian_opinion"].feed_url != (
        "https://www.theguardian.com/opinion/rss"
    )
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_food"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_travel"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_realestate"].feed_url
    assert by_id["nyt_magazine"].feed_url != by_id["nyt_personaltech"].feed_url
    assert by_id["nyt_magazine"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml"
    )
    assert by_id["nyt_magazine"].feed_url != (
        "https://www.nytimes.com/svc/collections/v1/publish/"
        "www.nytimes.com/section/magazine/rss.xml"
    )
    assert by_id["bloomberg_markets"].feed_url != by_id["guardian_opinion"].feed_url
    assert by_id["bloomberg_markets"].feed_url != by_id["nyt_magazine"].feed_url
    assert by_id["guardian_opinion"].feed_url != by_id["nyt_magazine"].feed_url
    # Unused backups / replaced / title+link-only / empty-desc /
    # not-this-batch feeds stay unregistered. guardian_economics
    # was hard-swapped out this batch (public insert=1 <5) —
    # do not keep live and do not register as a backup.
    # france24_middle_east / nyt_personaltech /
    # france24_africa are batch41 (those unused batch40
    # backups france24_middle_east / nyt_personaltech were
    # registered there). Unused batch41 backups
    # reuters_world / nyt_sports / guardian_food stay
    # unregistered. guardian_media was hard-swapped out in
    # batch39 — do not keep live and do not register as a
    # backup. npr_business was hard-swapped out in batch37.
    # al_monitor stays unregistered (replaced in batch29;
    # not a live CAP slot). independent_world is the
    # daily-fetch RED slot — do not keep live. nikkei /
    # indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science / thehill /
    # politico / abc_intl / sunday_review / nyt_sports are
    # not this batch (politico is X-handle only).
    assert "npr_business" not in by_id
    assert "guardian_media" not in by_id
    assert "guardian_economics" not in by_id
    assert "reuters_world" not in by_id
    assert "guardian_food" not in by_id
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in (
        _BLOOMBERG_MARKETS_GUARDIAN_OPINION_NYT_MAGAZINE_PRIMARY.items()
    ):
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_bloomberg_markets_guardian_opinion_nyt_magazine_feeds_live_http_200():
    """Hit the three batch40 feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _BLOOMBERG_MARKETS_GUARDIAN_OPINION_NYT_MAGAZINE_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (bloomberg_markets / guardian_opinion /
        # nyt_magazine) uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product
        # lock requires non-empty RSS description/summary on these
        # three feeds (all live-diff winners were 100% nonempty).
        nonempty = 0
        for item in items:
            if _item_description(item):
                nonempty += 1
        assert nonempty == len(items), (
            f"{source_id} empty description: {len(items) - nonempty}/{len(items)}"
        )


def test_france24_middle_east_nyt_personaltech_france24_africa_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    assert "france24_middle_east" in by_id
    assert by_id["france24_middle_east"].feed_url == (
        "https://www.france24.com/en/middle-east/rss"
    )
    assert "nyt_personaltech" in by_id
    assert by_id["nyt_personaltech"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml"
    )
    assert "france24_africa" in by_id
    assert by_id["france24_africa"].feed_url == (
        "https://www.france24.com/en/africa/rss"
    )
    assert "france24_en" in by_id
    assert "france24_americas" in by_id
    assert "france24_asia" in by_id
    assert "bloomberg_markets" in by_id
    assert "guardian_opinion" in by_id
    assert "nyt_magazine" in by_id
    assert "cbs_world" in by_id
    assert "cnbc_top" in by_id
    assert "nyt_technology" in by_id
    assert "nyt_africa" in by_id
    assert "bbc_africa" in by_id
    assert "guardian_world_africa" in by_id
    assert "bbc_middle_east" in by_id
    assert "guardian_middle_east" in by_id
    assert "middleeasteye" in by_id
    assert by_id["france24_en"].feed_url == "https://www.france24.com/en/europe/rss"
    assert by_id["france24_americas"].feed_url == (
        "https://www.france24.com/en/americas/rss"
    )
    assert by_id["france24_asia"].feed_url == (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert by_id["nyt_magazine"].feed_url == (
        "https://rss.nytimes.com/services/xml/rss/nyt/Magazine.xml"
    )
    assert by_id["france24_middle_east"].feed_url != by_id["france24_en"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["france24_americas"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["france24_asia"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["france24_africa"].feed_url
    assert by_id["france24_middle_east"].feed_url != "https://www.france24.com/en/rss"
    assert by_id["france24_middle_east"].feed_url != (
        "https://www.france24.com/en/europe/rss"
    )
    assert by_id["france24_middle_east"].feed_url != (
        "https://www.france24.com/en/americas/rss"
    )
    assert by_id["france24_middle_east"].feed_url != (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert by_id["france24_middle_east"].feed_url != (
        "https://www.france24.com/en/africa/rss"
    )
    assert by_id["france24_middle_east"].feed_url != (
        "https://www.france24.com/en/middleeast/rss"
    )
    assert by_id["france24_middle_east"].feed_url != by_id["bbc_middle_east"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["guardian_middle_east"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["middleeasteye"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_world"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_technology"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_business"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_science"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_climate"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_health"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_education"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_politics"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_us"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_europe"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_upshot"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_arts"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_opinion"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_movies"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_books"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_food"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_travel"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_economy"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_realestate"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["nyt_magazine"].feed_url
    assert by_id["nyt_personaltech"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/PersonalTechnology.xml"
    )
    assert by_id["nyt_personaltech"].feed_url != (
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
    )
    assert by_id["france24_africa"].feed_url != by_id["france24_en"].feed_url
    assert by_id["france24_africa"].feed_url != by_id["france24_americas"].feed_url
    assert by_id["france24_africa"].feed_url != by_id["france24_asia"].feed_url
    assert by_id["france24_africa"].feed_url != by_id["france24_middle_east"].feed_url
    assert by_id["france24_africa"].feed_url != "https://www.france24.com/en/rss"
    assert by_id["france24_africa"].feed_url != "https://www.france24.com/en/europe/rss"
    assert by_id["france24_africa"].feed_url != "https://www.france24.com/en/americas/rss"
    assert by_id["france24_africa"].feed_url != (
        "https://www.france24.com/en/asia-pacific/rss"
    )
    assert by_id["france24_africa"].feed_url != (
        "https://www.france24.com/en/middle-east/rss"
    )
    assert by_id["france24_africa"].feed_url != "https://www.france24.com/en/africa/rss.xml"
    assert by_id["france24_africa"].feed_url != by_id["bbc_africa"].feed_url
    assert by_id["france24_africa"].feed_url != by_id["nyt_africa"].feed_url
    assert by_id["france24_africa"].feed_url != by_id["guardian_world_africa"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["nyt_personaltech"].feed_url
    assert by_id["france24_middle_east"].feed_url != by_id["france24_africa"].feed_url
    assert by_id["nyt_personaltech"].feed_url != by_id["france24_africa"].feed_url
    # Unused backups / replaced / title+link-only / empty-desc /
    # not-this-batch feeds stay unregistered. reuters_world /
    # nyt_sports / guardian_food were probed only (primaries
    # won). reuters_world official public RSS is dead — do
    # not invent a Google News proxy. nyt_sports Sports.xml
    # is HTTP 200 / 0 items. guardian_food is healthy but
    # unused. guardian_economics was hard-swapped out in
    # batch40. guardian_media was hard-swapped out in
    # batch39. npr_business was hard-swapped out in
    # batch37. al_monitor stays unregistered (replaced in
    # batch29; not a live CAP slot). independent_world is
    # the daily-fetch RED slot — do not keep live. nikkei /
    # indian_express are empty-desc — product skipped.
    # sky_tech / restofworld / ars_science / thehill /
    # politico / abc_intl / sunday_review are not this
    # batch (politico is X-handle only).
    assert "npr_business" not in by_id
    assert "guardian_media" not in by_id
    assert "guardian_economics" not in by_id
    assert "reuters_world" not in by_id
    assert "guardian_food" not in by_id
    assert "independent_world" not in by_id
    assert "al_monitor" not in by_id
    assert "indian_express" not in by_id
    assert "nikkei" not in by_id
    assert "nyt_world_asia" not in by_id
    assert "nikkei_asia" not in by_id
    assert "sky_tech" not in by_id
    assert "restofworld" not in by_id
    assert "ars_science" not in by_id
    assert "thehill" not in by_id
    assert "politico" not in by_id
    assert "abc_intl" not in by_id
    assert "sunday_review" not in by_id
    assert "nyt_sports" not in by_id
    for source_id, expected in (
        _FRANCE24_MIDDLE_EAST_NYT_PERSONALTECH_FRANCE24_AFRICA_PRIMARY.items()
    ):
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


def test_france24_middle_east_nyt_personaltech_france24_africa_feeds_live_http_200():
    """Hit the three batch41 feeds with the same headers fetch_source sends (not stubs)."""
    by_id = {s.id: s for s in SOURCES}
    for source_id in _FRANCE24_MIDDLE_EAST_NYT_PERSONALTECH_FRANCE24_AFRICA_PRIMARY:
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
        root = ET.fromstring(_decode_feed_body(body))
        items = _feed_items(root)
        count = len(items)
        assert count > 0, f"{source_id} parsed 0 items (bytes={len(body)})"
        # Required: parseable title / url / published on each item.
        # RSS 2.0 (france24_middle_east / nyt_personaltech /
        # france24_africa) uses the un-namespaced element text.
        for i, item in enumerate(items):
            title = _item_title(item)
            url = _item_link(item)
            published = _item_published(item)
            assert title, f"{source_id} item[{i}] missing title"
            assert url, f"{source_id} item[{i}] missing url"
            assert published, f"{source_id} item[{i}] missing published"
        # #43 thin-skip: empty description would insert 0. Product
        # lock requires non-empty RSS description/summary on these
        # three feeds (all live-diff winners were 100% nonempty).
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
    test_bbc_politics_nyt_europe_guardian_law_primaries_registered()
    test_guardian_society_bbc_scotland_guardian_cities_primaries_registered()
    test_guardian_world_africa_guardian_politics_bbc_wales_primaries_registered()
    test_bbc_england_nyt_upshot_france24_en_primaries_registered()
    test_bbc_ni_guardian_me_euronews_primaries_registered()
    test_nyt_africa_smh_world_nbc_world_primaries_registered()
    test_csmonitor_latimes_hindu_primaries_registered()
    test_cbc_cna_elpais_primaries_registered()
    test_yonhap_anadolu_trt_primaries_registered()
    test_semafor_france24_americas_middleeasteye_primaries_registered()
    test_scmp_business_rfi_asia_theconversation_primaries_registered()
    test_nyt_arts_guardian_sport_intercept_primaries_registered()
    test_nyt_opinion_guardian_film_propublica_primaries_registered()
    test_forbes_innovation_dw_world_rfi_americas_primaries_registered()
    test_nyt_movies_guardian_music_guardian_stage_primaries_registered()
    test_nyt_books_guardian_books_npr_arts_primaries_registered()
    test_nyt_food_guardian_tv_npr_science_primaries_registered()
    test_nyt_travel_guardian_fashion_nyt_economy_primaries_registered()
    test_nyt_realestate_guardian_lifeandstyle_bbc_entertainment_primaries_registered()
    test_cbs_world_france24_asia_cnbc_top_primaries_registered()
    test_bloomberg_markets_guardian_opinion_nyt_magazine_primaries_registered()
    test_france24_middle_east_nyt_personaltech_france24_africa_primaries_registered()
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
    test_bbc_politics_nyt_europe_guardian_law_feeds_live_http_200()
    test_guardian_society_bbc_scotland_guardian_cities_feeds_live_http_200()
    test_guardian_world_africa_guardian_politics_bbc_wales_feeds_live_http_200()
    test_bbc_england_nyt_upshot_france24_en_feeds_live_http_200()
    test_bbc_ni_guardian_me_euronews_feeds_live_http_200()
    test_nyt_africa_smh_world_nbc_world_feeds_live_http_200()
    test_csmonitor_latimes_hindu_feeds_live_http_200()
    test_cbc_cna_elpais_feeds_live_http_200()
    test_yonhap_anadolu_trt_feeds_live_http_200()
    test_semafor_france24_americas_middleeasteye_feeds_live_http_200()
    test_scmp_business_rfi_asia_theconversation_feeds_live_http_200()
    test_nyt_arts_guardian_sport_intercept_feeds_live_http_200()
    test_nyt_opinion_guardian_film_propublica_feeds_live_http_200()
    test_forbes_innovation_dw_world_rfi_americas_feeds_live_http_200()
    test_nyt_movies_guardian_music_guardian_stage_feeds_live_http_200()
    test_nyt_books_guardian_books_npr_arts_feeds_live_http_200()
    test_nyt_food_guardian_tv_npr_science_feeds_live_http_200()
    test_nyt_travel_guardian_fashion_nyt_economy_feeds_live_http_200()
    test_nyt_realestate_guardian_lifeandstyle_bbc_entertainment_feeds_live_http_200()
    test_cbs_world_france24_asia_cnbc_top_feeds_live_http_200()
    test_bloomberg_markets_guardian_opinion_nyt_magazine_feeds_live_http_200()
    test_france24_middle_east_nyt_personaltech_france24_africa_feeds_live_http_200()
    print("✓ source registry tests PASSED")
