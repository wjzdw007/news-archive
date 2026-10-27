"""科技/AI curated topic: whitelist, keywords, X backups, no snapshot leak."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news_archive.news_display import NEWS_SOURCE_CAP
from news_archive.tech_ai import (
    AI_KEYWORDS_EN,
    AI_KEYWORDS_ZH,
    MAX_ITEMS,
    TECH_AI_ALWAYS_SOURCES,
    TECH_AI_KEYWORD_SOURCES,
    TECH_AI_SOURCE_WHITELIST,
    TECH_AI_TITLE,
    TECH_AI_TOPIC_ID,
    X_COLUMN_CAP,
    article_on_topic,
    assert_whitelist_registered,
    build_tech_ai_page,
    empty_tech_ai_payload,
    matches_ai_keywords,
    split_column_feeds,
    tech_ai_topic_card,
)
from news_archive.x_config import (
    X_AI_BACKUP_ACCOUNTS,
    X_AI_PRIMARY_ACCOUNTS,
    X_NEWS_ACCOUNTS,
    x_fetch_accounts,
)

NOW = datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc)


def _art(
    *,
    url: str,
    title: str,
    source: str,
    hours_ago: float = 1,
    summary: str = "",
    status: str = "active",
) -> dict:
    published = (NOW - timedelta(hours=hours_ago)).isoformat()
    return {
        "url": url,
        "title": title,
        "source": source,
        "summary": summary,
        "published_at": published,
        "fetched_at": NOW.isoformat(),
        "status": status,
        "content_snapshot": "FULL TEXT MUST NEVER LEAK",
    }


def _post(
    *,
    author: str,
    text: str,
    hours_ago: float = 1,
    status: str = "active",
    post_id: str = "secret-post-id",
) -> dict:
    posted = (NOW - timedelta(hours=hours_ago)).isoformat()
    return {
        "post_id": post_id,
        "author": author,
        "url": f"https://x.com/{author}/status/1",
        "text_snapshot": text,
        "posted_at": posted,
        "fetched_at": NOW.isoformat(),
        "status": status,
    }


def test_whitelist_registered_and_cap_unchanged():
    missing = assert_whitelist_registered()
    assert missing == [], f"whitelist ids missing from SOURCES: {missing}"
    assert NEWS_SOURCE_CAP == 6
    assert TECH_AI_TOPIC_ID == "tech-ai"
    assert TECH_AI_TITLE == "科技/AI"
    assert "wired" in TECH_AI_ALWAYS_SOURCES
    assert "verge" in TECH_AI_ALWAYS_SOURCES
    assert "36kr" in TECH_AI_ALWAYS_SOURCES
    assert "nyt_technology" in TECH_AI_ALWAYS_SOURCES
    assert "nyt_personaltech" in TECH_AI_ALWAYS_SOURCES
    assert "bbc_science" in TECH_AI_KEYWORD_SOURCES
    assert "bloomberg_markets" in TECH_AI_KEYWORD_SOURCES
    assert TECH_AI_ALWAYS_SOURCES.isdisjoint(TECH_AI_KEYWORD_SOURCES)
    # batch52 RSS primaries stay off the tech/AI whitelist.
    # ars_science → zdnet hard-swap stays off the whitelist.
    assert "bbc_australia" not in TECH_AI_SOURCE_WHITELIST
    assert "bloomberg_technology" not in TECH_AI_SOURCE_WHITELIST
    assert "ars_science" not in TECH_AI_SOURCE_WHITELIST
    assert "zdnet" not in TECH_AI_SOURCE_WHITELIST
    # batch53 RSS primaries stay off the tech/AI whitelist.
    assert "the_register" not in TECH_AI_SOURCE_WHITELIST
    assert "foreign_affairs" not in TECH_AI_SOURCE_WHITELIST
    assert "allafrica" not in TECH_AI_SOURCE_WHITELIST
    # batch54 RSS primaries stay off the tech/AI whitelist.
    assert "phys_org" not in TECH_AI_SOURCE_WHITELIST
    assert "globe_mail" not in TECH_AI_SOURCE_WHITELIST
    assert "newatlas" not in TECH_AI_SOURCE_WHITELIST
    # batch55 RSS primaries stay off the tech/AI whitelist.
    assert "politico_europe" not in TECH_AI_SOURCE_WHITELIST
    assert "breaking_defense" not in TECH_AI_SOURCE_WHITELIST
    assert "carbon_brief" not in TECH_AI_SOURCE_WHITELIST
    # batch56 RSS primaries stay off the tech/AI whitelist.
    assert "mongabay" not in TECH_AI_SOURCE_WHITELIST
    assert "daily_maverick" not in TECH_AI_SOURCE_WHITELIST
    assert "oilprice" not in TECH_AI_SOURCE_WHITELIST
    # batch57 RSS primaries stay off the tech/AI whitelist.
    # sciencedaily lands on the existing 科学 category path
    # and is not added to TECH_AI_KEYWORD_SOURCES.
    assert "africa_report" not in TECH_AI_SOURCE_WHITELIST
    assert "mexico_news_daily" not in TECH_AI_SOURCE_WHITELIST
    assert "sciencedaily" not in TECH_AI_SOURCE_WHITELIST
    # batch58 RSS primaries stay off the tech/AI whitelist.
    # nature_news lands on the existing 科学 category path
    # and is not added to TECH_AI_KEYWORD_SOURCES.
    assert "mercopress" not in TECH_AI_SOURCE_WHITELIST
    assert "nature_news" not in TECH_AI_SOURCE_WHITELIST
    assert "crisis_group" not in TECH_AI_SOURCE_WHITELIST
    # batch59 RSS primaries stay off the tech/AI whitelist.
    # aeon / noema land on the existing 综合 category path
    # and are not added to TECH_AI_KEYWORD_SOURCES.
    # marketwatch lands on the existing 财经 category path
    # and is not added to TECH_AI_KEYWORD_SOURCES.
    assert "aeon" not in TECH_AI_SOURCE_WHITELIST
    assert "noema" not in TECH_AI_SOURCE_WHITELIST
    assert "marketwatch" not in TECH_AI_SOURCE_WHITELIST
    # batch60 RSS primaries stay off the tech/AI whitelist.
    # aspi_strategist lands on the existing 国际 category path.
    # nautilus / hyperallergic land on the existing 综合
    # category path and are not added to
    # TECH_AI_KEYWORD_SOURCES.
    assert "aspi_strategist" not in TECH_AI_SOURCE_WHITELIST
    assert "nautilus" not in TECH_AI_SOURCE_WHITELIST
    assert "hyperallergic" not in TECH_AI_SOURCE_WHITELIST
    # batch61 RSS primaries stay off the tech/AI whitelist.
    # the_markup lands on the existing 综合 category
    # path (investigative, same as intercept /
    # propublica) and is not added to
    # TECH_AI_ALWAYS_SOURCES / TECH_AI_KEYWORD_SOURCES.
    # atlas_obscura / undark land on the existing
    # 综合 category path. asiatimes was httpx 403
    # and is not registered.
    assert "the_markup" not in TECH_AI_SOURCE_WHITELIST
    assert "atlas_obscura" not in TECH_AI_SOURCE_WHITELIST
    assert "undark" not in TECH_AI_SOURCE_WHITELIST
    assert "asiatimes" not in TECH_AI_SOURCE_WHITELIST
    assert "asia_times" not in TECH_AI_SOURCE_WHITELIST
    # batch62 RSS primaries stay off the tech/AI whitelist.
    # techinasia lands on the existing 科技
    # category path (Asia tech / startups;
    # same 科技 path as newatlas, not the
    # wired / verge / techcrunch ALWAYS
    # pattern and not 36kr 科技商业).
    # science_news lands on the existing
    # 综合 category path (science magazine,
    # same as nautilus / undark).
    # african_arguments lands on the
    # existing 国际 category path (same
    # as africa_report / allafrica).
    assert "techinasia" not in TECH_AI_SOURCE_WHITELIST
    assert "science_news" not in TECH_AI_SOURCE_WHITELIST
    assert "african_arguments" not in TECH_AI_SOURCE_WHITELIST
    assert "the_wire_china" not in TECH_AI_SOURCE_WHITELIST
    assert "literary_hub" not in TECH_AI_SOURCE_WHITELIST
    assert "world_politics_review" not in TECH_AI_SOURCE_WHITELIST
    # batch63 RSS primaries stay off the tech/AI whitelist.
    # defense_one / lowy_interpreter land on the
    # existing 国际 category path. fast_company
    # lands on 科技商业 but is not added to the
    # 36kr ALWAYS pattern (broader business /
    # innovation, not dedicated tech/AI).
    assert "defense_one" not in TECH_AI_SOURCE_WHITELIST
    assert "fast_company" not in TECH_AI_SOURCE_WHITELIST
    assert "lowy_interpreter" not in TECH_AI_SOURCE_WHITELIST
    assert "japan_forward" not in TECH_AI_SOURCE_WHITELIST
    assert "artforum" not in TECH_AI_SOURCE_WHITELIST
    assert "knowable" not in TECH_AI_SOURCE_WHITELIST
    # batch64 RSS primaries stay off the tech/AI whitelist.
    # the_wire_china lands on the existing 国际·中国
    # category path (China business magazine; same
    # as economist_china / scmp_china). literary_hub
    # lands on 综合 (literature, same as
    # guardian_books / nyt_books / hyperallergic).
    # himal lands on 国际 (Southasia magazine, same
    # as african_arguments / the_diplomat). None of
    # these match the wired / verge / techcrunch
    # ALWAYS pattern.
    assert "himal" not in TECH_AI_SOURCE_WHITELIST
    assert "artnet" not in TECH_AI_SOURCE_WHITELIST
    assert "military_times" not in TECH_AI_SOURCE_WHITELIST
    # batch65 RSS primaries stay off the tech/AI whitelist.
    # japan_forward lands on the existing 国际·亚太
    # category path (Japan English news /
    # opinion; same as japan_times).
    # artforum lands on 综合 (art / culture,
    # same as hyperallergic /
    # guardian_artanddesign). knowable
    # lands on 科学 (science magazine from
    # Annual Reviews; same as nature_news /
    # sciencedaily / phys_org) and is not
    # added to TECH_AI_KEYWORD_SOURCES.
    # None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    assert "japan_forward" not in TECH_AI_SOURCE_WHITELIST
    assert "artforum" not in TECH_AI_SOURCE_WHITELIST
    assert "knowable" not in TECH_AI_SOURCE_WHITELIST
    assert "the_new_humanitarian" not in TECH_AI_SOURCE_WHITELIST
    assert "dawn" not in TECH_AI_SOURCE_WHITELIST
    assert "grist" not in TECH_AI_SOURCE_WHITELIST
    # batch66 RSS primaries stay off the tech/AI whitelist.
    # world_politics_review lands on the existing
    # 国际 category path (international-affairs
    # analysis; same as foreign_affairs /
    # foreign_policy / the_diplomat).
    # climate_home lands on 科学 (climate news,
    # same as carbon_brief / nyt_climate /
    # guardian_environment) and is not added
    # to TECH_AI_KEYWORD_SOURCES.
    # project_syndicate lands on 综合 (world
    # opinion / commentary, same as atlantic /
    # nyt_opinion / guardian_opinion). None of
    # these match the wired / verge / techcrunch
    # ALWAYS pattern.
    assert "world_politics_review" not in TECH_AI_SOURCE_WHITELIST
    assert "climate_home" not in TECH_AI_SOURCE_WHITELIST
    assert "project_syndicate" not in TECH_AI_SOURCE_WHITELIST
    assert "artnet" not in TECH_AI_SOURCE_WHITELIST
    assert "reason" not in TECH_AI_SOURCE_WHITELIST
    assert "vox" not in TECH_AI_SOURCE_WHITELIST
    # batch67 RSS primaries stay off the tech/AI whitelist.
    # the_new_humanitarian lands on the existing 国际
    # category path (humanitarian / crisis reporting;
    # same as crisis_group / guardian_global_dev).
    # salon lands on 综合 (news / politics / culture,
    # same as atlantic / intercept) after dawn
    # official httpx 403 hard-swap. mother_jones
    # lands on 综合 (investigative magazine, same
    # as intercept / propublica). None of these
    # match the wired / verge / techcrunch ALWAYS
    # pattern.
    assert "the_new_humanitarian" not in TECH_AI_SOURCE_WHITELIST
    assert "salon" not in TECH_AI_SOURCE_WHITELIST
    assert "mother_jones" not in TECH_AI_SOURCE_WHITELIST
    assert "dawn" not in TECH_AI_SOURCE_WHITELIST
    assert "kff_health" not in TECH_AI_SOURCE_WHITELIST
    assert "niemanlab" not in TECH_AI_SOURCE_WHITELIST
    # batch68 RSS primaries stay off the tech/AI whitelist.
    # popular_science lands on the existing 科学
    # category path (science magazine; same as
    # science_news / knowable / sciencedaily).
    # slate lands on 综合 (news / politics /
    # culture, same as salon / atlantic) after
    # longreads official httpx 403 hard-swap.
    # the_19th lands on 综合 (gender / politics
    # / policy newsroom, same as salon /
    # atlantic / the_hill). None of these
    # match the wired / verge / techcrunch
    # ALWAYS pattern.
    assert "popular_science" not in TECH_AI_SOURCE_WHITELIST
    assert "slate" not in TECH_AI_SOURCE_WHITELIST
    assert "the_19th" not in TECH_AI_SOURCE_WHITELIST
    assert "longreads" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    assert "texas_tribune" not in TECH_AI_SOURCE_WHITELIST
    # batch69 RSS primaries stay off the tech/AI whitelist.
    # kff_health lands on the existing 科学
    # category path (health journalism;
    # same as stat_news / nyt_health /
    # bbc_health). niemanlab lands on 综合
    # (journalism / media research, same
    # as digiday_media). reason lands on
    # 综合 (news / politics / opinion
    # magazine, same as salon / slate /
    # atlantic). None of these match the
    # wired / verge / techcrunch ALWAYS
    # pattern.
    assert "kff_health" not in TECH_AI_SOURCE_WHITELIST
    assert "niemanlab" not in TECH_AI_SOURCE_WHITELIST
    assert "reason" not in TECH_AI_SOURCE_WHITELIST
    assert "vox" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    assert "pew_research" not in TECH_AI_SOURCE_WHITELIST
    # batch70 RSS primaries stay off the tech/AI whitelist.
    # hrw → jacobin hard-swap stays off
    # the whitelist. media404 lands on
    # the existing 综合 category path
    # (investigative tech journalism,
    # same as the_markup / intercept).
    # jacobin lands on 综合 (socialist
    # political magazine, same as salon
    # / slate / mother_jones / reason).
    # un_news lands on 国际 (UN global
    # newsroom, same as bbc_world /
    # guardian_world). None of these
    # match the wired / verge /
    # techcrunch ALWAYS pattern.
    assert "media404" not in TECH_AI_SOURCE_WHITELIST
    assert "hrw" not in TECH_AI_SOURCE_WHITELIST
    assert "un_news" not in TECH_AI_SOURCE_WHITELIST
    assert "jacobin" not in TECH_AI_SOURCE_WHITELIST
    assert "psyche" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    # batch71 RSS primaries stay off the tech/AI whitelist.
    # texas_tribune lands on the existing 综合
    # category path (state newsroom /
    # investigative, same as propublica /
    # intercept / the_19th). pew_research
    # lands on 综合 (public-opinion /
    # social research newsroom, same as
    # theconversation / niemanlab).
    # defector lands on 综合 (sports /
    # culture independent newsroom, same
    # as salon / slate / guardian_sport).
    # None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    assert "texas_tribune" not in TECH_AI_SOURCE_WHITELIST
    assert "pew_research" not in TECH_AI_SOURCE_WHITELIST
    assert "defector" not in TECH_AI_SOURCE_WHITELIST
    assert "vox" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    assert "passblue" not in TECH_AI_SOURCE_WHITELIST
    assert "inkstick" not in TECH_AI_SOURCE_WHITELIST
    # batch72 RSS primaries stay off the tech/AI whitelist.
    # independent → who_news hard-swap stays
    # off the whitelist. who_news lands on
    # 国际 (WHO global health newsroom,
    # same as un_news). scientific_american
    # lands on 科学 (science magazine, same
    # as popular_science / science_news /
    # knowable). thenewstack lands on 科技
    # (cloud-native / DevOps newsroom,
    # same as zdnet / techinasia /
    # newatlas) but later-batch tech
    # sources stay off the frozen
    # ALWAYS set (zdnet / the_register /
    # techinasia / fast_company were
    # also not added). None of these
    # match the wired / verge /
    # techcrunch ALWAYS pattern.
    assert "independent" not in TECH_AI_SOURCE_WHITELIST
    assert "scientific_american" not in TECH_AI_SOURCE_WHITELIST
    assert "thenewstack" not in TECH_AI_SOURCE_WHITELIST
    assert "who_news" not in TECH_AI_SOURCE_WHITELIST
    assert "new_yorker" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    # batch73 RSS primaries stay off the tech/AI whitelist.
    # irish_times lands on the existing 综合
    # category path (Irish general newsroom,
    # same as guardian_uk / bbc_uk /
    # axios). science_org lands on 科学
    # (AAAS Science Magazine news, same
    # as scientific_american /
    # popular_science / science_news).
    # variety lands on 综合 (entertainment
    # trade newsroom, same as
    # bbc_entertainment / nyt_movies /
    # guardian_film — existing pattern has
    # no 娱乐 category). None of these
    # match the wired / verge /
    # techcrunch ALWAYS pattern.
    assert "irish_times" not in TECH_AI_SOURCE_WHITELIST
    assert "science_org" not in TECH_AI_SOURCE_WHITELIST
    assert "variety" not in TECH_AI_SOURCE_WHITELIST
    assert "medicalxpress" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    assert "howtogeek" not in TECH_AI_SOURCE_WHITELIST
    # batch74 RSS primaries stay off the tech/AI whitelist.
    # physics_world lands on the existing 科学
    # category path (IOP Physics World
    # magazine, same as phys_org /
    # science_org / nature_news).
    # kyiv_independent lands on 国际
    # (Ukraine / Eastern Europe newsroom,
    # same as bbc_europe / politico_europe).
    # pitchfork is the euractiv hard-swap
    # fill and lands on 综合 (music /
    # culture newsroom, same as
    # guardian_music / variety — existing
    # pattern has no 音乐 / 娱乐 category).
    # Later-batch science / intl / culture
    # sources stay off the frozen ALWAYS
    # set. None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    # euractiv stays off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "physics_world" not in TECH_AI_SOURCE_WHITELIST
    assert "kyiv_independent" not in TECH_AI_SOURCE_WHITELIST
    assert "pitchfork" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    assert "scotusblog" not in TECH_AI_SOURCE_WHITELIST
    assert "infoq" not in TECH_AI_SOURCE_WHITELIST
    # batch75 RSS primaries stay off the tech/AI whitelist.
    # atlantic_council stays off (hard-swapped
    # after daily-fetch #40299450300 RSS 403
    # → DB=0; do not re-register).
    # grist is the atlantic_council hard-swap
    # fill and lands on 科学 (climate /
    # environment journalism, same as
    # climate_home / carbon_brief / mongabay)
    # but is not added to TECH_AI_KEYWORD_SOURCES.
    # balkan_insight lands on 国际 (Southeast
    # Europe newsroom, same as
    # kyiv_independent / bbc_europe).
    # tomshardware lands on 科技 (PC hardware
    # newsroom, same as thenewstack / zdnet /
    # techinasia / newatlas) but later-batch
    # tech sources stay off the frozen ALWAYS
    # set. None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    # Unused backups dezeen / moscow_times
    # stay off (reserved for hung batch77).
    # euractiv stays off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "grist" not in TECH_AI_SOURCE_WHITELIST
    assert "balkan_insight" not in TECH_AI_SOURCE_WHITELIST
    assert "tomshardware" not in TECH_AI_SOURCE_WHITELIST
    assert "dezeen" not in TECH_AI_SOURCE_WHITELIST
    assert "moscow_times" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch76 RSS primaries stay off the tech/AI whitelist.
    # livescience lands on the existing 科学
    # category path (science newsroom, same
    # as space_com / popular_science /
    # science_news) but later-batch science
    # sources stay off the frozen KEYWORD
    # set. thehackernews lands on 科技
    # (security newsroom, same as
    # thenewstack / zdnet / techinasia)
    # but later-batch tech sources stay
    # off the frozen ALWAYS set.
    # stereogum lands on 综合 (music /
    # culture newsroom, same as pitchfork
    # / variety). None of these match the
    # wired / verge / techcrunch ALWAYS
    # pattern. the_nation official /feed/
    # FAIL — not registered. Unused
    # backups scotusblog / times_of_israel
    # stay off (first-winner unused stay
    # out). atlantic_council stays off
    # (hard-swapped to grist in #139).
    # grist stays off the frozen KEYWORD
    # set. euractiv stays off (official
    # 301 to rapporteur.com; Feedburner stale).
    assert "livescience" not in TECH_AI_SOURCE_WHITELIST
    assert "thehackernews" not in TECH_AI_SOURCE_WHITELIST
    assert "stereogum" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "grist" not in TECH_AI_SOURCE_WHITELIST
    assert "scotusblog" not in TECH_AI_SOURCE_WHITELIST
    assert "times_of_israel" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch77 RSS primaries stay off the tech/AI whitelist.
    # moscow_times lands on 国际 (Russia /
    # Eurasia newsroom, same as
    # kyiv_independent / bbc_europe).
    # dezeen lands on 综合 (design /
    # architecture / culture newsroom,
    # same as hyperallergic / artforum /
    # guardian_artanddesign).
    # eff lands on 综合 (digital rights /
    # civil-liberties newsroom, same as
    # the_markup / intercept / reason).
    # None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    # Unused backups android_authority /
    # unherd are now batch79 KEEP (stay
    # off the whitelist). grist stays off the
    # frozen KEYWORD set (already used
    # for the atlantic_council hard-swap;
    # do not reuse as a backup).
    # atlantic_council stays off
    # (hard-swapped to grist in #139).
    # the_nation stays off (empty
    # site-wide FAIL). euractiv stays off
    # (official 301 to rapporteur.com;
    # Feedburner stale).
    assert "moscow_times" not in TECH_AI_SOURCE_WHITELIST
    assert "dezeen" not in TECH_AI_SOURCE_WHITELIST
    assert "eff" not in TECH_AI_SOURCE_WHITELIST
    assert "android_authority" not in TECH_AI_SOURCE_WHITELIST
    assert "unherd" not in TECH_AI_SOURCE_WHITELIST
    assert "grist" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch78 RSS primaries stay off the tech/AI whitelist.
    # scotusblog lands on 综合 (Supreme
    # Court / legal newsroom, same as
    # guardian_law / reason / intercept).
    # medicalxpress is the times_of_israel
    # hard-swap fill and lands on 科学
    # (medical / health science newsroom,
    # same as phys_org / stat_news /
    # kff_health) but later-batch science
    # sources stay off the frozen KEYWORD
    # set. infoq lands on 科技 (software
    # / architecture newsroom, same as
    # thenewstack / zdnet / the_register)
    # but later-batch tech sources stay
    # off the frozen ALWAYS set. None of
    # these match the wired / verge /
    # techcrunch ALWAYS pattern.
    # times_of_israel official FAIL
    # (Cloudflare 403; Feedburner stale
    # 2012) — not registered. Unused
    # backups howtogeek / new_republic
    # stay off (first-winner unused stay
    # out). atlantic_council stays off
    # (hard-swapped to grist in #139).
    # the_nation stays off (empty
    # site-wide FAIL). euractiv stays off
    # (official 301 to rapporteur.com;
    # Feedburner stale).
    assert "scotusblog" not in TECH_AI_SOURCE_WHITELIST
    assert "medicalxpress" not in TECH_AI_SOURCE_WHITELIST
    assert "infoq" not in TECH_AI_SOURCE_WHITELIST
    assert "times_of_israel" not in TECH_AI_SOURCE_WHITELIST
    assert "howtogeek" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch79 RSS primaries stay off the tech/AI whitelist.
    # android_authority lands on 科技 (Android
    # / mobile newsroom, same as
    # tomshardware / zdnet / thenewstack)
    # but later-batch tech sources stay
    # off the frozen ALWAYS set.
    # unherd lands on 综合 (opinion /
    # magazine newsroom, same as atlantic
    # / slate / salon / reason).
    # psyche lands on 综合 (ideas /
    # psychology magazine, same family as
    # aeon but different domain; same as
    # aeon / nautilus / noema). None of
    # these match the wired / verge /
    # techcrunch ALWAYS pattern.
    # Unused backups artnet is now
    # batch81 KEEP (techdirt Cloudflare
    # 403 hard-swap fill) and stays off
    # the whitelist. smithsonian_mag is
    # now the gizmodo official CI httpx
    # 403 hard-swap fill and stays off
    # the whitelist (MUST lock
    # /rss/latest_articles/ never stale
    # /rss/articles/). new_yorker stays
    # unused leftover (smithsonian_mag
    # live KEEP). gizmodo stays hung.
    # medicalxpress stays
    # off the frozen KEYWORD set
    # (already used for the
    # times_of_israel hard-swap; do not
    # re-register). atlantic_council
    # stays off (hard-swapped to grist
    # in #139). the_nation stays off
    # (empty site-wide FAIL). euractiv
    # stays off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "android_authority" not in TECH_AI_SOURCE_WHITELIST
    assert "unherd" not in TECH_AI_SOURCE_WHITELIST
    assert "psyche" not in TECH_AI_SOURCE_WHITELIST
    assert "artnet" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    assert "new_yorker" not in TECH_AI_SOURCE_WHITELIST
    assert "medicalxpress" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch80 RSS primaries stay off the tech/AI whitelist.
    # howtogeek lands on 科技 (how-to /
    # consumer tech newsroom, same as
    # tomshardware / zdnet /
    # android_authority) but later-batch
    # tech sources stay off the frozen
    # ALWAYS set. new_republic lands on
    # 综合 (political magazine newsroom,
    # same as atlantic / slate / salon /
    # unherd). vox lands on 综合 (news /
    # explainers newsroom, same as
    # atlantic / slate / axios / semafor).
    # None of these match the wired /
    # verge / techcrunch ALWAYS pattern.
    # Unused backups techdirt / macrumors
    # / quillette are now batch81
    # (techdirt official Cloudflare 403
    # hard-swap to artnet; macrumors /
    # quillette KEEP) and stay off the
    # whitelist. the_cut stays off
    # (product dropped — all 404; do
    # not probe / register).
    # atlantic_council stays off
    # (hard-swapped to grist in #139).
    # the_nation stays off (empty
    # site-wide FAIL). euractiv stays off
    # (official 301 to rapporteur.com;
    # Feedburner stale).
    assert "howtogeek" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    assert "vox" not in TECH_AI_SOURCE_WHITELIST
    assert "techdirt" not in TECH_AI_SOURCE_WHITELIST
    assert "macrumors" not in TECH_AI_SOURCE_WHITELIST
    assert "quillette" not in TECH_AI_SOURCE_WHITELIST
    assert "the_cut" not in TECH_AI_SOURCE_WHITELIST
    assert "android_authority" not in TECH_AI_SOURCE_WHITELIST
    assert "unherd" not in TECH_AI_SOURCE_WHITELIST
    assert "psyche" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch81 RSS primaries stay off the tech/AI whitelist.
    # artnet is the techdirt official
    # Cloudflare 403 hard-swap fill and
    # lands on 综合 (art newsroom, same
    # as artforum / hyperallergic /
    # guardian_artanddesign). macrumors
    # lands on 科技 (Apple / consumer
    # tech newsroom, same as
    # android_authority / howtogeek /
    # tomshardware) but later-batch tech
    # sources stay off the frozen ALWAYS
    # set. quillette lands on 综合
    # (ideas / culture / politics
    # magazine, same as unherd /
    # atlantic / new_republic). None of
    # these match the wired / verge /
    # techcrunch ALWAYS pattern.
    # techdirt official FAIL (Cloudflare
    # 403; do not register Feedburner)
    # — not registered. Unused backups
    # smithsonian_mag is now the gizmodo
    # official CI httpx 403 hard-swap
    # fill and stays off the whitelist
    # (MUST lock /rss/latest_articles/
    # never stale /rss/articles/).
    # new_yorker stays unused leftover
    # (smithsonian_mag live KEEP; if a
    # later hard-swap falls through MUST
    # prefer /feed/everything) and stays
    # off the whitelist. gizmodo stays
    # hung (do not re-hang; do not hang
    # Feedburner) and stays off. the_cut
    # stays off (product dropped — all
    # 404). atlantic_council stays off
    # (hard-swapped to grist in #139).
    # the_nation stays off (empty
    # site-wide FAIL). euractiv stays off
    # (official 301 to rapporteur.com;
    # Feedburner stale).
    assert "artnet" not in TECH_AI_SOURCE_WHITELIST
    assert "macrumors" not in TECH_AI_SOURCE_WHITELIST
    assert "quillette" not in TECH_AI_SOURCE_WHITELIST
    assert "techdirt" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    assert "new_yorker" not in TECH_AI_SOURCE_WHITELIST
    assert "the_cut" not in TECH_AI_SOURCE_WHITELIST
    assert "howtogeek" not in TECH_AI_SOURCE_WHITELIST
    assert "new_republic" not in TECH_AI_SOURCE_WHITELIST
    assert "vox" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch82 RSS primaries stay off the tech/AI whitelist.
    # cnet is the engadget official
    # CloudFront 403 → digital_trends
    # official Cloudflare 403 hard-swap
    # fill and lands on 科技 (consumer
    # tech / gadget newsroom, same as
    # howtogeek / tomshardware / zdnet)
    # but later-batch tech sources stay
    # off the frozen ALWAYS set.
    # 9to5mac lands on 科技 (Apple /
    # consumer tech newsroom, same as
    # macrumors / android_authority /
    # howtogeek) but later-batch tech
    # sources stay off the frozen ALWAYS
    # set. smithsonian_mag is the
    # gizmodo official CI httpx 403
    # hard-swap fill and lands on 综合
    # (culture / history / science
    # magazine, same as atlantic /
    # nautilus / undark /
    # atlas_obscura). Not added to the
    # tech/AI whitelist. None of these
    # match the wired / verge /
    # techcrunch ALWAYS pattern.
    # gizmodo official FAIL (CI httpx
    # 403 in daily-fetch #40315044842
    # → 0 DB rows; do not re-hang; do
    # not register Feedburner) — not
    # registered. engadget official
    # FAIL (CloudFront 403; do not
    # register Feedburner) — not
    # registered. digital_trends
    # official FAIL (Cloudflare 403 JS
    # challenge; do not register
    # Feedburner) — not registered.
    # polygon is now batch83 KEEP (was
    # a batch82 leftover; MUST lock
    # /feed/ never /rss/index.xml) and
    # stays off the whitelist. new_yorker stays
    # off (smithsonian_mag won). the_verge
    # stays off (verge already
    # registered). the_cut stays off
    # (product dropped — all 404).
    # techdirt stays off (official
    # Cloudflare 403). atlantic_council
    # stays off (hard-swapped to grist
    # in #139). the_nation stays off
    # (empty site-wide FAIL). euractiv
    # stays off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "cnet" not in TECH_AI_SOURCE_WHITELIST
    assert "9to5mac" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    assert "gizmodo" not in TECH_AI_SOURCE_WHITELIST
    assert "engadget" not in TECH_AI_SOURCE_WHITELIST
    assert "digital_trends" not in TECH_AI_SOURCE_WHITELIST
    assert "polygon" not in TECH_AI_SOURCE_WHITELIST
    assert "the_verge" not in TECH_AI_SOURCE_WHITELIST
    assert "techdirt" not in TECH_AI_SOURCE_WHITELIST
    assert "the_cut" not in TECH_AI_SOURCE_WHITELIST
    assert "artnet" not in TECH_AI_SOURCE_WHITELIST
    assert "macrumors" not in TECH_AI_SOURCE_WHITELIST
    assert "quillette" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch83 RSS primaries stay off the tech/AI whitelist.
    # polygon lands on 综合 (gaming /
    # entertainment newsroom, same as
    # variety / pitchfork) and is not
    # an ALWAYS tech source. pcmag
    # lands on 科技 (consumer tech /
    # reviews newsroom, same as cnet /
    # howtogeek / tomshardware) but
    # later-batch tech sources stay
    # off the frozen ALWAYS set.
    # mashable lands on 科技 (consumer
    # tech / culture newsroom, same as
    # gizmodo / cnet) but later-batch
    # tech sources stay off the frozen
    # ALWAYS set. None of these match
    # the wired / verge / techcrunch
    # ALWAYS pattern. Unused leftover
    # bleepingcomputer stays off
    # (official Cloudflare 403 JS
    # challenge; do not register
    # Feedburner). smithsonian_mag is
    # already the gizmodo hard-swap
    # primary and stays off the
    # whitelist (MUST lock
    # /rss/latest_articles/ never stale
    # /rss/articles/). new_yorker stays
    # unused leftover (smithsonian_mag
    # live KEEP; if a later hard-swap
    # falls through MUST prefer
    # /feed/everything).
    # engadget / digital_trends /
    # techdirt stay off (official RSS
    # 403; do not register Feedburner).
    # the_cut stays off (product
    # dropped — all 404). the_verge
    # stays off (verge already
    # registered). atlantic_council
    # stays off (hard-swapped to grist
    # in #139). the_nation stays off
    # (empty site-wide FAIL). euractiv
    # stays off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "polygon" not in TECH_AI_SOURCE_WHITELIST
    assert "pcmag" not in TECH_AI_SOURCE_WHITELIST
    assert "mashable" not in TECH_AI_SOURCE_WHITELIST
    assert "bleepingcomputer" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    assert "new_yorker" not in TECH_AI_SOURCE_WHITELIST
    assert "engadget" not in TECH_AI_SOURCE_WHITELIST
    assert "digital_trends" not in TECH_AI_SOURCE_WHITELIST
    assert "techdirt" not in TECH_AI_SOURCE_WHITELIST
    assert "the_cut" not in TECH_AI_SOURCE_WHITELIST
    assert "the_verge" not in TECH_AI_SOURCE_WHITELIST
    assert "cnet" not in TECH_AI_SOURCE_WHITELIST
    assert "9to5mac" not in TECH_AI_SOURCE_WHITELIST
    assert "gizmodo" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    # batch84 RSS primaries stay off the tech/AI whitelist.
    # inverse lands on 综合 (science /
    # culture / entertainment magazine,
    # same as smithsonian_mag / atlantic
    # / nautilus) and is not an ALWAYS
    # tech source. appleinsider lands
    # on 科技 (Apple newsroom, same as
    # macrumors / 9to5mac) but
    # later-batch tech sources stay
    # off the frozen ALWAYS set.
    # popular_mechanics lands on 科学
    # (science / engineering magazine,
    # same as popular_science) and is
    # not added to KEYWORD sources.
    # None of these match the wired /
    # verge / techcrunch ALWAYS
    # pattern. Unused leftover
    # new_yorker stays off (all three
    # primaries live KEEP; if a later
    # hard-swap falls through MUST
    # prefer /feed/everything).
    # Unused leftover macworld stays
    # off (popular_mechanics won;
    # product prefers
    # popular_mechanics to reduce
    # Apple stack overlap with live
    # 9to5mac + macrumors).
    # smithsonian_mag is already the
    # gizmodo hard-swap primary and
    # stays off the whitelist (MUST
    # lock /rss/latest_articles/ never
    # stale /rss/articles/). polygon /
    # pcmag / mashable stay off
    # (batch83 KEEP). engadget /
    # digital_trends / techdirt /
    # bleepingcomputer stay off
    # (official RSS 403; do not
    # register Feedburner). the_cut
    # stays off (product dropped —
    # all 404). the_verge stays off
    # (verge already registered).
    # atlantic_council stays off
    # (hard-swapped to grist in #139).
    # the_nation stays off (empty
    # site-wide FAIL). euractiv stays
    # off (official 301 to
    # rapporteur.com; Feedburner stale).
    assert "inverse" not in TECH_AI_SOURCE_WHITELIST
    assert "appleinsider" not in TECH_AI_SOURCE_WHITELIST
    assert "popular_mechanics" not in TECH_AI_SOURCE_WHITELIST
    assert "macworld" not in TECH_AI_SOURCE_WHITELIST
    assert "new_yorker" not in TECH_AI_SOURCE_WHITELIST
    assert "smithsonian_mag" not in TECH_AI_SOURCE_WHITELIST
    assert "polygon" not in TECH_AI_SOURCE_WHITELIST
    assert "pcmag" not in TECH_AI_SOURCE_WHITELIST
    assert "mashable" not in TECH_AI_SOURCE_WHITELIST
    assert "bleepingcomputer" not in TECH_AI_SOURCE_WHITELIST
    assert "engadget" not in TECH_AI_SOURCE_WHITELIST
    assert "digital_trends" not in TECH_AI_SOURCE_WHITELIST
    assert "techdirt" not in TECH_AI_SOURCE_WHITELIST
    assert "the_cut" not in TECH_AI_SOURCE_WHITELIST
    assert "the_verge" not in TECH_AI_SOURCE_WHITELIST
    assert "gizmodo" not in TECH_AI_SOURCE_WHITELIST
    assert "atlantic_council" not in TECH_AI_SOURCE_WHITELIST
    assert "the_nation" not in TECH_AI_SOURCE_WHITELIST
    assert "euractiv" not in TECH_AI_SOURCE_WHITELIST
    print("✓ whitelist registered + CAP=6")


def test_keywords_tight():
    assert matches_ai_keywords("OpenAI releases a new model")
    assert matches_ai_keywords("Anthropic 发布 Claude")
    assert matches_ai_keywords("国内大模型竞争加剧")
    assert matches_ai_keywords("Nvidia earnings beat")
    assert not matches_ai_keywords("Airlines face paid seating fight")
    assert not matches_ai_keywords("The main story from downtown")
    assert not matches_ai_keywords("Fresh air quality report")
    assert "ML" not in " ".join(AI_KEYWORDS_EN)
    assert "芯片" not in AI_KEYWORDS_ZH
    print("✓ keywords tight")


def test_article_filter_whitelist_and_keywords():
    wired = _art(url="https://wired/1", title="A new phone case", source="wired")
    assert article_on_topic(wired)

    science_ai = _art(
        url="https://nyt/sci",
        title="Lab uses machine learning to map proteins",
        source="nyt_science",
    )
    assert article_on_topic(science_ai)

    science_other = _art(
        url="https://nyt/sci2",
        title="Bird migration patterns this fall",
        source="nyt_science",
        summary="Warming shifts routes.",
    )
    assert not article_on_topic(science_other)

    world = _art(
        url="https://bbc/world",
        title="OpenAI policy hearing",
        source="bbc_world",
    )
    assert "bbc_world" not in TECH_AI_SOURCE_WHITELIST
    assert not article_on_topic(world)
    print("✓ article filter")


def test_page_prefers_24h_and_falls_back():
    fresh = _art(url="https://verge/fresh", title="Verge chip", source="verge", hours_ago=2)
    old = _art(url="https://verge/old", title="Verge old", source="verge", hours_ago=48)
    page = build_tech_ai_page([fresh, old], [], now=NOW)
    assert page["used_fallback"] is False
    assert [i["url"] for i in page["items"]] == ["https://verge/fresh"]

    page_fb = build_tech_ai_page([old], [], now=NOW)
    assert page_fb["used_fallback"] is True
    assert [i["url"] for i in page_fb["items"]] == ["https://verge/old"]
    print("✓ 24h window + 7d fallback")


def test_x_primaries_and_backups():
    primary = _post(author="OpenAI", text="Shipping GPT-5", hours_ago=1)
    backup = _post(author="AndrewYNg", text="Course update", hours_ago=1)
    news_only = _post(author="BBCChinese", text="World brief", hours_ago=1)

    page = build_tech_ai_page([], [primary, backup, news_only], now=NOW)
    authors = {i.get("author") for i in page["items"]}
    assert authors == {"OpenAI"}
    assert page["used_x_backups"] is False

    gone_primary = _post(author="OpenAI", text="old", hours_ago=1, status="gone")
    page_b = build_tech_ai_page([], [gone_primary, backup], now=NOW)
    authors_b = {i.get("author") for i in page_b["items"]}
    assert "AndrewYNg" in authors_b
    assert page_b["used_x_backups"] is True

    empty_primary = _post(author="OpenAI", text="   ", hours_ago=1)
    page_e = build_tech_ai_page([], [empty_primary, backup], now=NOW)
    assert {i.get("author") for i in page_e["items"]} == {"AndrewYNg"}
    print("✓ X primaries / backups")


def test_merge_time_order_rss_and_x():
    rss = _art(url="https://wired/2", title="WIRED AI chip", source="wired", hours_ago=3)
    x = _post(author="karpathy", text="new tokenizer notes", hours_ago=1)
    page = build_tech_ai_page([rss], [x], now=NOW)
    assert [i["kind"] for i in page["rss_items"]] == ["rss"]
    assert [i["kind"] for i in page["x_items"]] == ["x"]
    assert [i["kind"] for i in page["items"]] == ["x", "rss"]
    assert page["rss_count"] == 1
    assert page["x_count"] == 1
    assert page["layout"] == "columns"
    print("✓ columns keep per-column time order")


def test_no_snapshot_or_post_id():
    rss = _art(url="https://wired/3", title="WIRED", source="wired")
    x = _post(author="sama", text="hello", post_id="secret-post-id")
    page = build_tech_ai_page([rss], [x], now=NOW)
    raw = str(page)
    assert "content_snapshot" not in raw
    assert "FULL TEXT MUST NEVER LEAK" not in raw
    assert "post_id" not in raw
    assert "secret-post-id" not in raw
    for item in page["items"]:
        assert "content_snapshot" not in item
        assert "post_id" not in item
    card = tech_ai_topic_card(page)
    assert card["status"] == "ok"
    assert card["topic_id"] == "tech-ai"
    empty = empty_tech_ai_payload(now=NOW)
    assert empty["items"] == []
    assert empty["title"] == "科技/AI"
    print("✓ no snapshot / post_id")


def test_x_column_independent_of_rss_max():
    assert NEWS_SOURCE_CAP == 6
    assert MAX_ITEMS == 100
    assert X_COLUMN_CAP == 30

    rss = [
        _art(url=f"https://wired/{i}", title=f"WIRED {i}", source="wired", hours_ago=0.1 * i)
        for i in range(120)
    ]
    x_few = [
        _post(author="OpenAI", text=f"model {i}", hours_ago=0.2 * i, post_id=f"x-{i}")
        for i in range(5)
    ]
    page = build_tech_ai_page(rss, x_few, now=NOW)
    assert page["x_count"] == 5
    assert page["rss_count"] == 100
    assert len(page["rss_items"]) == 100
    assert len(page["x_items"]) == 5
    assert page["x_column_cap"] == 30
    assert "x_reserved_slots" not in page

    x_many = [
        _post(author="karpathy", text=f"note {i}", hours_ago=0.2 * i, post_id=f"k-{i}")
        for i in range(40)
    ]
    page_cap = build_tech_ai_page(rss, x_many, now=NOW)
    assert page_cap["x_count"] == 30
    assert page_cap["rss_count"] == 100
    assert len(page_cap["items"]) == 130

    page_rss_only = build_tech_ai_page(rss, [], now=NOW)
    assert page_rss_only["x_count"] == 0
    assert page_rss_only["rss_count"] == 100
    assert page_rss_only["x_items"] == []
    print("✓ X column cap independent of RSS MAX")


def test_split_column_feeds_independent_caps():
    rss = [_art(url="https://wired/old", title="old rss", source="wired", hours_ago=3)]
    x = [_post(author="sama", text="new x", hours_ago=1)]
    rss_items, x_items = split_column_feeds(rss, x)
    assert [i["kind"] for i in rss_items] == ["rss"]
    assert [i["kind"] for i in x_items] == ["x"]
    print("✓ split columns")


def test_x_fetch_accounts_union():
    expected_news = [
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
    assert X_NEWS_ACCOUNTS == expected_news
    assert X_AI_PRIMARY_ACCOUNTS == [
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
    assert X_AI_BACKUP_ACCOUNTS == [
        "AndrewYNg",
        "miramurati",
        "gdb",
        "MistralAI",
        "cohere",
    ]
    accounts = x_fetch_accounts()
    assert accounts.count("elonmusk") == 1
    for name in X_AI_PRIMARY_ACCOUNTS + X_AI_BACKUP_ACCOUNTS + X_NEWS_ACCOUNTS:
        assert name.lower() in {a.lower() for a in accounts}
    print("✓ x_fetch_accounts union")


if __name__ == "__main__":
    test_whitelist_registered_and_cap_unchanged()
    test_keywords_tight()
    test_article_filter_whitelist_and_keywords()
    test_page_prefers_24h_and_falls_back()
    test_x_primaries_and_backups()
    test_merge_time_order_rss_and_x()
    test_x_column_independent_of_rss_max()
    test_split_column_feeds_independent_caps()
    test_no_snapshot_or_post_id()
    test_x_fetch_accounts_union()
    print("✓ All tech_ai tests passed")
