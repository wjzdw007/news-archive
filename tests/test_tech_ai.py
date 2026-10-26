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
