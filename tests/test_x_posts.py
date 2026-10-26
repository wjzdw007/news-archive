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
        "axios",
        "NikkeiAsia",
        "politico",
    ]
    assert x_config.X_NEWS_ACCOUNTS == expected
    assert len(x_config.X_NEWS_ACCOUNTS) == 25
    # 科技/AI accounts share this fetch job (no new secret / no keyword search).
    assert "OpenAI" in x_config.X_AI_PRIMARY_ACCOUNTS
    assert "AndrewYNg" in x_config.X_AI_BACKUP_ACCOUNTS
    assert "OpenAI" in x_config.x_fetch_accounts()
    # guard: no queries list for full-site search in this slice
    assert not hasattr(x_config, "X_QUERIES") or not getattr(x_config, "X_QUERIES")
    print("✓ 5 account-only config")


def test_latest_post_ids_for_since_id():
    with tempfile.TemporaryDirectory() as tmp:
        store = XStore(Path(tmp) / "a.sqlite3")
        now = "2026-10-25T16:00:00+00:00"
        later = "2026-10-25T17:00:00+00:00"
        store.upsert(
            XPost(
                post_id="100",
                author="OpenAI",
                url="https://x.com/OpenAI/status/100",
                text_snapshot="old",
                posted_at=now,
                fetched_at=now,
            )
        )
        store.upsert(
            XPost(
                post_id="200",
                author="OpenAI",
                url="https://x.com/OpenAI/status/200",
                text_snapshot="new",
                posted_at=later,
                fetched_at=later,
            )
        )
        ids = store.latest_post_ids(["OpenAI", "karpathy"])
        assert ids == {"openai": "200"}
        store.close()
    print("✓ latest_post_ids")


def test_6_live_splits_news_hometimeline_and_ai_usertweets():
    """News stays on HomeTimeline; AI primaries use UserTweets; backups skipped."""
    from unittest.mock import patch

    from news_archive.x_config import X_AI_PRIMARY_ACCOUNTS, X_NEWS_ACCOUNTS

    news_tweet = {
        "post_id": "n1",
        "author": "BBCChinese",
        "url": "https://x.com/BBCChinese/status/n1",
        "text": "world brief",
        "posted_at": "2026-10-25T16:00:00+00:00",
    }
    ai_tweet = {
        "post_id": "a1",
        "author": "OpenAI",
        "url": "https://x.com/OpenAI/status/a1",
        "text": "shipping gpt",
        "posted_at": "2026-10-25T16:30:00+00:00",
    }

    with patch("news_archive.x_http_client.fetch_news_accounts", return_value=[news_tweet]) as news:
        with patch("news_archive.x_http_client.fetch_user_accounts", return_value=[ai_tweet]) as users:
            posts = fetch_account_posts(mode="live", auth_token="t", ct0="c")

    authors = {p.author for p in posts}
    assert authors == {"BBCChinese", "OpenAI"}
    news.assert_called_once()
    assert news.call_args.kwargs["target_accounts"] == X_NEWS_ACCOUNTS
    users.assert_called_once()
    assert users.call_args.kwargs["target_accounts"] == X_AI_PRIMARY_ACCOUNTS
    print("✓ 6 live split HomeTimeline vs UserTweets")


def test_7_backups_only_when_primaries_empty():
    from unittest.mock import patch

    from news_archive.x_config import X_AI_BACKUP_ACCOUNTS, X_AI_PRIMARY_ACCOUNTS

    backup_tweet = {
        "post_id": "b1",
        "author": "AndrewYNg",
        "url": "https://x.com/AndrewYNg/status/b1",
        "text": "course note",
        "posted_at": "2026-10-25T16:00:00+00:00",
    }

    with patch("news_archive.x_http_client.fetch_news_accounts", return_value=[]):
        with patch(
            "news_archive.x_http_client.fetch_user_accounts",
            side_effect=[[], [backup_tweet]],
        ) as users:
            posts = fetch_account_posts(
                mode="live",
                accounts=X_AI_PRIMARY_ACCOUNTS + X_AI_BACKUP_ACCOUNTS,
                auth_token="t",
                ct0="c",
            )

    assert [p.author for p in posts] == ["AndrewYNg"]
    assert users.call_count == 2
    assert users.call_args_list[0].kwargs["target_accounts"] == X_AI_PRIMARY_ACCOUNTS
    assert users.call_args_list[1].kwargs["target_accounts"] == X_AI_BACKUP_ACCOUNTS
    print("✓ 7 backups when primaries empty")


def test_8_since_id_drops_older_after_backup_decision():
    from unittest.mock import patch

    ai_old = {
        "post_id": "100",
        "author": "OpenAI",
        "url": "https://x.com/OpenAI/status/100",
        "text": "old",
        "posted_at": "2026-10-25T16:00:00+00:00",
    }
    ai_new = {
        "post_id": "200",
        "author": "OpenAI",
        "url": "https://x.com/OpenAI/status/200",
        "text": "new",
        "posted_at": "2026-10-25T16:30:00+00:00",
    }

    with patch("news_archive.x_http_client.fetch_news_accounts", return_value=[]):
        with patch(
            "news_archive.x_http_client.fetch_user_accounts",
            return_value=[ai_old, ai_new],
        ) as users:
            posts = fetch_account_posts(
                mode="live",
                accounts=["OpenAI"],
                auth_token="t",
                ct0="c",
                since_ids={"openai": "100"},
            )

    assert [p.post_id for p in posts] == ["200"]
    # since_id is applied after the window check, so backups are not fetched
    assert users.call_count == 1
    print("✓ 8 since_id incremental")


if __name__ == "__main__":
    test_1_mock_insert_nonempty_snapshot()
    test_2_dedupe_by_post_id()
    test_3_gone_keeps_snapshot()
    test_4_soft_fail_live_without_creds()
    test_5_no_keyword_search_in_news_config()
    test_latest_post_ids_for_since_id()
    test_6_live_splits_news_hometimeline_and_ai_usertweets()
    test_7_backups_only_when_primaries_empty()
    test_8_since_id_drops_older_after_backup_decision()
    print("\n✅ All X tests PASSED")
