"""Test topic_id clustering acceptance criteria."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_archive.clustering import (
    assign_topic_ids,
    char_bigrams,
    jaccard_similarity,
    normalize_title,
    should_merge,
    within_time_window,
)
from news_archive.schema import Article
from news_archive.store import Store


def test_normalize_title():
    """Test title normalization: lowercase, strip punctuation, keep CJK/Latin/digits."""
    assert normalize_title("Hello World!") == "helloworld"
    assert normalize_title("北京时间 2024-01-01") == "北京时间20240101"
    assert normalize_title("  SpaceX 发射火箭！！！") == "spacex发射火箭"
    assert normalize_title("Test-123_ABC") == "test123abc"
    # CJK should be preserved
    assert "中国" in normalize_title("中国经济增长")


def test_char_bigrams():
    """Test character bigram generation."""
    assert char_bigrams("abc") == {"ab", "bc"}
    assert char_bigrams("中国") == {"中国"}
    assert char_bigrams("a") == {"a"}
    assert char_bigrams("") == set()


def test_jaccard_similarity():
    """Test Jaccard similarity on character bigrams."""
    # Identical texts
    assert jaccard_similarity("hello", "hello") == 1.0
    
    # Similar texts (partial overlap)
    sim = jaccard_similarity("北京时间", "北京日报")
    assert 0.1 < sim < 0.5  # Partial overlap - share "北京" bigram
    
    # Different texts
    sim = jaccard_similarity("apple", "orange")
    assert sim < 0.3
    
    # Empty texts
    assert jaccard_similarity("", "") == 1.0
    assert jaccard_similarity("test", "") == 0.0


def test_within_time_window():
    """Test time window checking."""
    base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Within 6h window
    dt1 = base
    dt2 = base + timedelta(hours=5)
    assert within_time_window(dt1, dt2, window_hours=6.0)
    
    # Exactly at boundary
    dt2 = base + timedelta(hours=6)
    assert within_time_window(dt1, dt2, window_hours=6.0)
    
    # Outside window
    dt2 = base + timedelta(hours=7)
    assert not within_time_window(dt1, dt2, window_hours=6.0)
    
    # Reverse order (should work either way)
    dt1 = base + timedelta(hours=2)
    dt2 = base
    assert within_time_window(dt1, dt2, window_hours=6.0)
    
    # None values
    assert not within_time_window(None, dt1, window_hours=6.0)
    assert not within_time_window(dt1, None, window_hours=6.0)


def test_acceptance_1_cross_source_near_title_same_topic():
    """Acceptance 1: Two cross-source near-title articles in window → same topic_id."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://source1.com/article1",
            "title": "SpaceX launches Starship to Mars",
            "published_at": base_time.isoformat(),
            "source": "source1",
            "status": "active",
            "topic_id": None,
        },
        {
            "url": "https://source2.com/article2",
            "title": "SpaceX Launches Starship to Mars",  # Very similar, different case
            "published_at": (base_time + timedelta(hours=2)).isoformat(),
            "source": "source2",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Both should have topic_id
    assert all(a.get("topic_id") for a in result)
    
    # Should have same topic_id
    assert result[0]["topic_id"] == result[1]["topic_id"]
    print(f"✓ Acceptance 1 PASSED: Cross-source similar articles share topic_id={result[0]['topic_id']}")


def test_acceptance_2_unrelated_titles_different_topic():
    """Acceptance 2: Unrelated titles → different topic_id."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://source1.com/article1",
            "title": "SpaceX launches rocket",
            "published_at": base_time.isoformat(),
            "source": "source1",
            "status": "active",
            "topic_id": None,
        },
        {
            "url": "https://source2.com/article2",
            "title": "Tesla announces new car model",  # Completely different
            "published_at": base_time.isoformat(),
            "source": "source2",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Both should have topic_id
    assert all(a.get("topic_id") for a in result)
    
    # Should have different topic_id
    assert result[0]["topic_id"] != result[1]["topic_id"]
    print(f"✓ Acceptance 2 PASSED: Unrelated articles have different topic_ids")


def test_acceptance_3_near_titles_outside_window_different_topic():
    """Acceptance 3: Near titles but >6h apart → different topic_id."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://source1.com/article1",
            "title": "Breaking: Major earthquake hits Tokyo",
            "published_at": base_time.isoformat(),
            "source": "source1",
            "status": "active",
            "topic_id": None,
        },
        {
            "url": "https://source2.com/article2",
            "title": "Breaking Major Earthquake Hits Tokyo",  # Very similar title
            "published_at": (base_time + timedelta(hours=7)).isoformat(),  # >6h apart
            "source": "source2",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Both should have topic_id
    assert all(a.get("topic_id") for a in result)
    
    # Should have different topic_id (outside time window)
    assert result[0]["topic_id"] != result[1]["topic_id"]
    print(f"✓ Acceptance 3 PASSED: Similar articles >6h apart have different topic_ids")


def test_acceptance_4_preserves_existing_gone_not_merged():
    """Acceptance 4: Does not drop rows; gone not newly merged; prior topic_id kept."""
    base_time = datetime.now(timezone.utc)
    existing_topic = "existing-topic-123"
    
    articles = [
        {
            "url": "https://source1.com/old-article",
            "title": "Old article with existing topic",
            "published_at": base_time.isoformat(),
            "source": "source1",
            "status": "active",
            "topic_id": existing_topic,  # Already has topic_id
        },
        {
            "url": "https://source2.com/gone-article",
            "title": "Very similar old article title",
            "published_at": base_time.isoformat(),
            "source": "source2",
            "status": "gone",  # Marked as gone
            "topic_id": None,
        },
        {
            "url": "https://source3.com/new-article",
            "title": "Completely new article",
            "published_at": base_time.isoformat(),
            "source": "source3",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Should not drop any rows
    assert len(result) == len(articles)
    
    # Find articles in result
    old_article = next(a for a in result if a["url"] == "https://source1.com/old-article")
    gone_article = next(a for a in result if a["url"] == "https://source2.com/gone-article")
    new_article = next(a for a in result if a["url"] == "https://source3.com/new-article")
    
    # Existing topic_id should be preserved
    assert old_article["topic_id"] == existing_topic
    
    # Gone article should not get a new topic_id
    assert gone_article["topic_id"] is None
    
    # New article should get a topic_id
    assert new_article["topic_id"] is not None
    assert new_article["topic_id"] != existing_topic
    
    print(f"✓ Acceptance 4 PASSED: Existing topic_id preserved, gone excluded, no rows dropped")


def test_acceptance_5_p0_behavior_unchanged():
    """Acceptance 5: P0 fetch/persist/SLA behavior unchanged (schema-level check)."""
    # This test verifies that adding topic_id doesn't break existing functionality
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        store = Store(db_path)
        
        # Insert article without topic_id (backward compatibility)
        now = datetime.now(timezone.utc).isoformat()
        article = Article(
            url="https://test.com/article",
            title="Test Article",
            published_at=now,
            summary="Summary",
            source="test-source",
            fetched_at=now,
            content_snapshot="Content",
            status="active",
            topic_id=None,
        )
        
        inserted = store.upsert(article)
        assert inserted, "Should insert new article"
        
        # Verify schema has topic_id column
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]
        assert "topic_id" in cols, "topic_id column should exist"
        
        # Verify URL is still primary key (dedup works)
        duplicate_inserted = store.upsert(article)
        assert not duplicate_inserted, "Should not insert duplicate URL"
        
        # Verify existing fields still work
        row = conn.execute("SELECT * FROM articles WHERE url = ?", (article.url,)).fetchone()
        assert row is not None
        
        conn.close()
        store.close()
        
    print(f"✓ Acceptance 5 PASSED: P0 behavior unchanged, schema compatible")


def test_single_article_gets_topic_id():
    """Single articles should still get a topic_id."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://source1.com/lonely-article",
            "title": "Unique article about quantum computing",
            "published_at": base_time.isoformat(),
            "source": "source1",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    assert len(result) == 1
    assert result[0]["topic_id"] is not None
    print(f"✓ Single article gets topic_id={result[0]['topic_id']}")


def test_same_source_not_merged():
    """Same-source articles should generally not merge."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://source1.com/article1",
            "title": "Breaking News Today",
            "published_at": base_time.isoformat(),
            "source": "same-source",
            "status": "active",
            "topic_id": None,
        },
        {
            "url": "https://source1.com/article2",
            "title": "Breaking News Today",  # Identical title, same source
            "published_at": base_time.isoformat(),
            "source": "same-source",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Should have different topic_ids (same source)
    assert result[0]["topic_id"] != result[1]["topic_id"]
    print(f"✓ Same-source articles not merged")


def test_integration_with_store():
    """Integration test: full pipeline with store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        store = Store(db_path)
        
        base_time = datetime.now(timezone.utc)
        
        # Insert related articles from different sources
        article1 = Article(
            url="https://bbc.com/tech-news",
            title="Apple announces new iPhone 15",
            published_at=base_time.isoformat(),
            summary="Apple revealed iPhone 15",
            source="bbc",
            fetched_at=base_time.isoformat(),
            content_snapshot="Full content",
            status="active",
            topic_id=None,
        )
        
        article2 = Article(
            url="https://nyt.com/tech",
            title="Apple Announces New iPhone 15",  # Similar title, different source
            published_at=(base_time + timedelta(hours=1)).isoformat(),
            summary="New iPhone revealed",
            source="nyt",
            fetched_at=base_time.isoformat(),
            content_snapshot="Full content",
            status="active",
            topic_id=None,
        )
        
        store.upsert(article1)
        store.upsert(article2)
        
        # Cluster articles
        articles = store.get_articles_for_clustering()
        clustered = assign_topic_ids(articles)
        url_to_topic = {a["url"]: a["topic_id"] for a in clustered}
        updated = store.update_topic_ids(url_to_topic)
        
        assert updated == 2, f"Should update 2 articles, got {updated}"
        
        # Verify clustering worked
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT url, topic_id FROM articles").fetchall()
        topic_ids = [row[1] for row in rows]
        
        # Both should have the same topic_id
        assert topic_ids[0] == topic_ids[1], "Related articles should share topic_id"
        assert topic_ids[0] is not None
        
        conn.close()
        store.close()
        
    print(f"✓ Integration test PASSED: Store clustering works end-to-end")


def test_chinese_title_clustering():
    """Test clustering with Chinese (CJK) titles."""
    base_time = datetime.now(timezone.utc)
    
    articles = [
        {
            "url": "https://36kr.com/news1",
            "title": "美国通过新的科技法案",
            "published_at": base_time.isoformat(),
            "source": "36kr",
            "status": "active",
            "topic_id": None,
        },
        {
            "url": "https://tmtpost.com/news2",
            "title": "美国通过新的科技法案",  # Same Chinese title
            "published_at": (base_time + timedelta(hours=3)).isoformat(),
            "source": "tmtpost",
            "status": "active",
            "topic_id": None,
        },
    ]
    
    result = assign_topic_ids(articles)
    
    # Should merge (same title, different sources, within window)
    assert result[0]["topic_id"] == result[1]["topic_id"]
    print(f"✓ Chinese title clustering works")



def test_threshold_0_7_does_not_merge_half_similar_en_pair():
    """Product gold: Guardian/NYT-like rewrite ~0.525 must stay apart at 0.7."""
    from news_archive.clustering import jaccard_similarity, normalize_title, should_merge

    t1 = normalize_title("Russia detains Japanese journalist in Moscow")
    t2 = normalize_title("Japanese reporter held by Russia after Moscow raid")
    sim = jaccard_similarity(t1, t2)
    # Document observed band; don't assert exact value
    assert sim < 0.7, f"fixture unexpectedly ≥0.7: {sim}"
    base = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    a1 = {
        "title": "Russia detains Japanese journalist in Moscow",
        "published_at": base.isoformat(),
        "source": "guardian_world",
        "status": "active",
    }
    a2 = {
        "title": "Japanese reporter held by Russia after Moscow raid",
        "published_at": (base + __import__("datetime").timedelta(hours=1)).isoformat(),
        "source": "nyt_world",
        "status": "active",
    }
    assert not should_merge(a1, a2, similarity_threshold=0.7)
    print("✓ 0.7 still separates ~0.5 English rewrite pair")



def test_en_0_5_merges_gold_russia_journalist_pair():
    """Product gold: Guardian/NYT Russia-Japan journalist pair must merge at EN 0.5."""
    from datetime import datetime, timedelta, timezone
    from news_archive.clustering import (
        assign_topic_ids,
        jaccard_similarity,
        normalize_title,
        should_merge,
    )

    t1 = "Russia arrests Japanese journalist on allegations of spying"
    t2 = "Russia Detains Japanese Journalist for Alleged Espionage"
    sim = jaccard_similarity(normalize_title(t1), normalize_title(t2))
    assert abs(sim - 0.525) < 0.02, f"unexpected sim={sim}"
    base = datetime.now(timezone.utc)
    a1 = {
        "url": "https://guardian.example/1",
        "title": t1,
        "published_at": base.isoformat(),
        "source": "guardian_world",
        "status": "active",
        "topic_id": None,
    }
    a2 = {
        "url": "https://nyt.example/1",
        "title": t2,
        "published_at": (base + timedelta(hours=1)).isoformat(),
        "source": "nyt_world",
        "status": "active",
        "topic_id": None,
    }
    assert should_merge(a1, a2)  # language-aware 0.5
    assert not should_merge(a1, a2, similarity_threshold=0.7)
    result = assign_topic_ids([a1, a2])
    assert result[0]["topic_id"] == result[1]["topic_id"]
    print(f"✓ EN 0.5 gold pair merges (sim={sim:.3f})")


def test_cn_threshold_stays_0_7():
    """Chinese pairs still need ≥0.7; loose EN threshold must not apply."""
    from datetime import datetime, timezone
    from news_archive.clustering import pair_similarity_threshold, should_merge

    assert pair_similarity_threshold("美国通过新的科技法案", "日本发布经济数据") == 0.7
    base = datetime.now(timezone.utc).isoformat()
    a1 = {
        "title": "美国通过新的科技法案",
        "published_at": base,
        "source": "36kr",
        "status": "active",
    }
    a2 = {
        "title": "日本发布经济数据报告",
        "published_at": base,
        "source": "tmtpost",
        "status": "active",
    }
    assert not should_merge(a1, a2)
    print("✓ CN threshold stays 0.7")


def test_recluster_clears_topic_without_ok_brief():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from news_archive.schema import Article
    from news_archive.store import Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        now = datetime.now(timezone.utc).isoformat()
        store.upsert(
            Article(
                title="A",
                published_at=now,
                url="https://a.com/1",
                summary="s",
                source="36kr",
                fetched_at=now,
                content_snapshot="c",
                topic_id="orphan-topic",
            )
        )
        n = store.clear_topic_ids_without_ok_brief()
        assert n == 1
        row = store._conn.execute(
            "SELECT topic_id FROM articles WHERE url=?", ("https://a.com/1",)
        ).fetchone()
        assert row[0] is None
        store.close()
    print("✓ recluster clears topic_id without ok brief")


def test_recluster_lookback_skips_old_orphans():
    """Fetch must not reopen the whole archive — only the live window."""
    import tempfile
    from pathlib import Path

    from news_archive.schema import Article
    from news_archive.store import Store

    now = datetime(2026, 10, 21, 4, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        store.upsert(
            Article(
                title="Old orphan",
                published_at=(now - timedelta(days=10)).isoformat(),
                url="https://old.example/1",
                summary="s",
                source="36kr",
                fetched_at=(now - timedelta(days=10)).isoformat(),
                content_snapshot="c",
                topic_id="old-orphan",
            )
        )
        store.upsert(
            Article(
                title="Recent orphan",
                published_at=(now - timedelta(hours=3)).isoformat(),
                url="https://new.example/1",
                summary="s",
                source="bbc_world",
                fetched_at=(now - timedelta(hours=3)).isoformat(),
                content_snapshot="c",
                topic_id="recent-orphan",
            )
        )
        n = store.clear_topic_ids_without_ok_brief(lookback_hours=24.0, now=now)
        assert n == 1
        old = store.get_article("https://old.example/1")
        recent = store.get_article("https://new.example/1")
        store.close()
        assert old is not None and old["topic_id"] == "old-orphan"
        assert recent is not None and recent["topic_id"] is None
    print("✓ recluster lookback keeps old orphan topic_id")


def test_recluster_max_clear_prefers_newest():
    import tempfile
    from pathlib import Path

    from news_archive.schema import Article
    from news_archive.store import Store

    now = datetime(2026, 10, 21, 4, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        for i, hours_ago in enumerate((2, 5, 8)):
            store.upsert(
                Article(
                    title=f"Orphan {i}",
                    published_at=(now - timedelta(hours=hours_ago)).isoformat(),
                    url=f"https://cap.example/{i}",
                    summary="s",
                    source="36kr",
                    fetched_at=(now - timedelta(hours=hours_ago)).isoformat(),
                    content_snapshot="c",
                    topic_id=f"orphan-{i}",
                )
            )
        n = store.clear_topic_ids_without_ok_brief(
            lookback_hours=24.0, max_clear=2, now=now
        )
        assert n == 2
        assert store.get_article("https://cap.example/0")["topic_id"] is None
        assert store.get_article("https://cap.example/1")["topic_id"] is None
        assert store.get_article("https://cap.example/2")["topic_id"] == "orphan-2"
        store.close()
    print("✓ recluster max_clear keeps older of the window")


def test_assign_topic_ids_caps_candidates_newest_first():
    """Overflow still gets a singleton topic_id; pairwise work stays bounded."""
    base = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    articles = []
    for i in range(5):
        articles.append(
            {
                "url": f"https://cap.example/{i}",
                "title": f"Unrelated headline {i} xyz{i}",
                "published_at": (base - timedelta(hours=i)).isoformat(),
                "source": f"src{i}",
                "status": "active",
            }
        )
    result = assign_topic_ids(articles, max_candidates=2)
    by_url = {a["url"]: a["topic_id"] for a in result}
    assert all(by_url[f"https://cap.example/{i}"] for i in range(5))
    # Newest-first pair (0,1) is the only pairwise slice; 2–4 are singletons.
    assert by_url["https://cap.example/2"] != by_url["https://cap.example/3"]
    print("✓ assign_topic_ids caps pairwise candidates")


def test_assign_topic_ids_deadline_assigns_singletons():
    articles = [
        {
            "url": "https://deadline.example/a",
            "title": "Alpha story about markets",
            "published_at": "2026-10-21T12:00:00+00:00",
            "source": "36kr",
            "status": "active",
        },
        {
            "url": "https://deadline.example/b",
            "title": "Beta story about rockets",
            "published_at": "2026-10-21T12:10:00+00:00",
            "source": "tmtpost",
            "status": "active",
        },
    ]
    clock = {"n": 0}
    values = [0.0, 100.0]

    def mono() -> float:
        i = min(clock["n"], len(values) - 1)
        clock["n"] += 1
        return values[i]

    result = assign_topic_ids(articles, deadline_s=50.0, monotonic=mono)
    ids = {a["topic_id"] for a in result}
    assert all(a.get("topic_id") for a in result)
    assert len(ids) == 2
    print("✓ assign_topic_ids deadline still assigns singleton topic_ids")


def test_cli_windowed_recluster_keeps_old_topics_and_inserts():
    """Full Fetch path: inserts/dedupe unchanged; old orphans not cleared."""
    import io
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from news_archive.schema import Article
    from news_archive.sources import Source
    from news_archive.store import Store

    now = datetime(2026, 10, 21, 4, 0, tzinfo=timezone.utc)
    src = Source(
        id="abc_news",
        name="ABC News",
        feed_url="https://abcnews.go.com/abcnews/topstories",
        category="综合",
        role="primary",
    )
    rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>ABC</title>
<item>
  <title>Fresh ABC headline</title>
  <link>https://abcnews.go.com/fresh-1</link>
  <description>Non-empty summary so thin-skip does not apply.</description>
  <pubDate>Wed, 21 Oct 2026 03:30:00 GMT</pubDate>
</item>
</channel></rss>"""

    class _Resp:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url: str, **_kwargs):
            return _Resp(rss)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "archive.sqlite3"
        store = Store(db_path)
        for i in range(40):
            store.upsert(
                Article(
                    title=f"Old archive row {i}",
                    published_at=(now - timedelta(days=8, hours=i)).isoformat(),
                    url=f"https://old.example/{i}",
                    summary="old summary",
                    source="36kr",
                    fetched_at=(now - timedelta(days=8)).isoformat(),
                    content_snapshot="old body",
                    topic_id=f"old-topic-{i}",
                )
            )
        store.close()

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("news_archive.fetch.httpx.Client", _Client),
            patch("news_archive.fetch.time.sleep"),
            patch("news_archive.cli.SOURCES", (src,)),
            patch("news_archive.cli.enrich_store", return_value={"fetched": 0}),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])

        assert rc == 0, stderr.getvalue()
        stats = json.loads(stdout.getvalue())
        assert stats["inserted"] == 1
        assert stats["recluster_cleared"] == 0
        assert stats["cluster_candidates"] == 1
        assert stats["timings"]["cluster_s"] < 2.0
        assert "INFO fetch_phase cluster_s=" in stderr.getvalue()

        store = Store(db_path)
        fresh = store.get_article("https://abcnews.go.com/fresh-1")
        old = store.get_article("https://old.example/0")
        store.close()
        assert fresh is not None
        assert fresh["title"] == "Fresh ABC headline"
        assert fresh["topic_id"]
        assert old is not None
        assert old["topic_id"] == "old-topic-0"
    print("✓ CLI windowed recluster keeps old topics and still inserts")


if __name__ == "__main__":
    # Run all acceptance tests
    print("Running topic_id clustering acceptance tests...\n")
    
    test_normalize_title()
    test_char_bigrams()
    test_jaccard_similarity()
    test_within_time_window()
    
    print("\n=== Acceptance Tests ===\n")
    test_acceptance_1_cross_source_near_title_same_topic()
    test_acceptance_2_unrelated_titles_different_topic()
    test_acceptance_3_near_titles_outside_window_different_topic()
    test_acceptance_4_preserves_existing_gone_not_merged()
    test_acceptance_5_p0_behavior_unchanged()
    
    print("\n=== Additional Tests ===\n")
    test_single_article_gets_topic_id()
    test_same_source_not_merged()
    test_integration_with_store()
    test_chinese_title_clustering()
    test_threshold_0_7_does_not_merge_half_similar_en_pair()
    test_en_0_5_merges_gold_russia_journalist_pair()
    test_cn_threshold_stays_0_7()
    test_recluster_clears_topic_without_ok_brief()
    test_recluster_lookback_skips_old_orphans()
    test_recluster_max_clear_prefers_newest()
    test_assign_topic_ids_caps_candidates_newest_first()
    test_assign_topic_ids_deadline_assigns_singletons()
    test_cli_windowed_recluster_keeps_old_topics_and_inserts()
    
    print("\n✅ All tests PASSED!")
