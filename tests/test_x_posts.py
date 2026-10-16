"""X minimal acceptance (mock; soft-fail isolation)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from news_archive.x_fetch import XFetchError, fetch_account_posts, sync_posts
from news_archive.x_store import XPost, XStore


def test_1_mock_insert_nonempty_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        store = XStore(Path(tmp) / "a.sqlite3")
        posts = fetch_account_posts(mode="mock", accounts=["BBCChinese"])
        assert posts and posts[0].text_snapshot
        assert store.upsert(posts[0])
        row = store.get(posts[0].post_id)
        assert row and row["text_snapshot"]
        store.close()
    print("✓ 1 insert + snapshot")


def test_2_dedupe_by_post_id():
    with tempfile.TemporaryDirectory() as tmp:
        store = XStore(Path(tmp) / "a.sqlite3")
        posts = fetch_account_posts(mode="mock", accounts=["FT"])
        assert store.upsert(posts[0])
        assert not store.upsert(posts[0])
        store.close()
    print("✓ 2 dedupe post_id")


def test_3_gone_keeps_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        store = XStore(Path(tmp) / "a.sqlite3")
        p = fetch_account_posts(mode="mock", accounts=["Reuters"])[0]
        store.upsert(p)
        assert store.mark_gone(p.post_id)
        row = store.get(p.post_id)
        assert row["status"] == "gone"
        assert row["text_snapshot"]
        store.close()
    print("✓ 3 gone keeps snapshot")


def test_4_soft_fail_live_without_creds():
    try:
        fetch_account_posts(mode="live")
        assert False, "should raise"
    except XFetchError:
        pass
    # RSS path untouched — just ensure XStore can share same db file as articles
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "shared.sqlite3"
        from news_archive.store import Store
        from news_archive.schema import Article
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        rss = Store(db)
        assert rss.upsert(
            Article(
                title="t",
                published_at=now,
                url="https://ex.com/1",
                summary="s",
                source="36kr",
                fetched_at=now,
                content_snapshot="c",
            )
        )
        rss.close()
        x = XStore(db)
        sync_posts(x, fetch_account_posts(mode="mock", accounts=["TechCrunch"]))
        x.close()
    print("✓ 4 soft-fail + shared DB with RSS")


def test_5_no_keyword_search_in_news_config():
    from news_archive import x_config

    assert hasattr(x_config, "X_NEWS_ACCOUNTS")
    expected = [
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
    ]
    assert x_config.X_NEWS_ACCOUNTS == expected
    assert len(x_config.X_NEWS_ACCOUNTS) == 22
    # guard: no queries list for full-site search in this slice
    assert not hasattr(x_config, "X_QUERIES") or not getattr(x_config, "X_QUERIES")
    print("✓ 5 account-only config")


if __name__ == "__main__":
    test_1_mock_insert_nonempty_snapshot()
    test_2_dedupe_by_post_id()
    test_3_gone_keeps_snapshot()
    test_4_soft_fail_live_without_creds()
    test_5_no_keyword_search_in_news_config()
    print("\n✅ All X tests PASSED")
