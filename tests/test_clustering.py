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
    
    print("\n✅ All tests PASSED!")
