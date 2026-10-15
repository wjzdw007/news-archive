"""Test site data export for static viewer."""

import json
import sqlite3
import tempfile
from pathlib import Path

from news_archive.schema import Article
from news_archive.store import Store
from news_archive.x_store import XPost, XStore


def test_export_articles():
    """Test articles.json export."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        
        # Insert sample articles
        articles = [
            Article(
                url="https://example.com/1",
                title="Test Article 1",
                published_at="2024-01-01T10:00:00Z",
                summary="Summary 1",
                source="test_source",
                fetched_at="2024-01-01T12:00:00Z",
                content_snapshot="Content 1",
                status="active",
            ),
            Article(
                url="https://example.com/2",
                title="Test Article 2",
                published_at="2024-01-01T09:00:00Z",
                summary="Summary 2",
                source="test_source",
                fetched_at="2024-01-01T11:00:00Z",
                content_snapshot="Content 2",
                status="gone",
            ),
        ]
        for article in articles:
            store.upsert(article)
        
        # Export
        output_path = Path(tmpdir) / "articles.json"
        conn = sqlite3.connect(db_path)
        count = export_articles(conn, output_path)
        conn.close()
        
        # Verify
        assert count == 2
        assert output_path.exists()
        
        with output_path.open("r", encoding="utf-8") as f:
            exported = json.load(f)
        
        assert len(exported) == 2
        # Should be sorted by fetched_at desc
        assert exported[0]["url"] == "https://example.com/1"
        assert exported[1]["url"] == "https://example.com/2"
        assert exported[0]["status"] == "active"
        assert exported[1]["status"] == "gone"
        
        store.close()


def test_export_topics():
    """Test topics.json export (only status=ok)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_topics
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        
        # Insert sample topic briefs
        briefs = [
            {
                "topic_id": "topic-1",
                "title": "Topic 1",
                "sources": [{"title": "Source 1", "url": "https://example.com/1"}],
                "article_urls": ["https://example.com/1"],
                "generated_at": "2024-01-01T12:00:00Z",
                "model": "test",
                "status": "ok",
            },
            {
                "topic_id": "topic-2",
                "title": "Topic 2",
                "sources": [{"title": "Source 2", "url": "https://example.com/2"}],
                "article_urls": ["https://example.com/2"],
                "generated_at": "2024-01-01T11:00:00Z",
                "model": "test",
                "status": "failed",
                "error": "Test error",
            },
        ]
        for brief in briefs:
            store.upsert_topic_brief(brief)
        
        # Export
        output_path = Path(tmpdir) / "topics.json"
        conn = sqlite3.connect(db_path)
        count = export_topics(conn, output_path)
        conn.close()
        
        # Verify
        assert count == 1  # Only status=ok
        assert output_path.exists()
        
        with output_path.open("r", encoding="utf-8") as f:
            exported = json.load(f)
        
        assert len(exported) == 1
        assert exported[0]["topic_id"] == "topic-1"
        assert exported[0]["status"] == "ok"
        assert exported[0]["sources"] == [{"title": "Source 1", "url": "https://example.com/1"}]
        
        store.close()


def test_export_x_posts():
    """Test x_posts.json export."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_x_posts
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        x_store = XStore(db_path)
        
        # Insert sample posts
        posts = [
            XPost(
                post_id="123",
                author="testuser",
                url="https://x.com/testuser/status/123",
                text_snapshot="Test post 1",
                posted_at="2024-01-01T10:00:00Z",
                fetched_at="2024-01-01T11:00:00Z",
                status="active",
            ),
            XPost(
                post_id="456",
                author="testuser",
                url="https://x.com/testuser/status/456",
                text_snapshot="Test post 2",
                posted_at="2024-01-01T09:00:00Z",
                fetched_at="2024-01-01T10:00:00Z",
                status="gone",
            ),
        ]
        for post in posts:
            x_store.upsert(post)
        
        # Export
        output_path = Path(tmpdir) / "x_posts.json"
        conn = sqlite3.connect(db_path)
        count = export_x_posts(conn, output_path)
        conn.close()
        
        # Verify
        assert count == 2
        assert output_path.exists()
        
        with output_path.open("r", encoding="utf-8") as f:
            exported = json.load(f)
        
        assert len(exported) == 2
        # Should be sorted by posted_at desc
        assert exported[0]["post_id"] == "123"
        assert exported[1]["post_id"] == "456"
        assert exported[0]["status"] == "active"
        assert exported[1]["status"] == "gone"
        
        x_store.close()


def test_export_empty_files():
    """Test empty file generation when DB missing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_empty_files
    
    with tempfile.TemporaryDirectory() as tmpdir:
        site_data_dir = Path(tmpdir) / "site" / "data"
        export_empty_files(site_data_dir)
        
        # Verify all files exist with empty arrays
        for filename in ["articles.json", "topics.json", "x_posts.json"]:
            filepath = site_data_dir / filename
            assert filepath.exists()
            
            with filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            assert data == []


if __name__ == "__main__":
    test_export_articles()
    test_export_topics()
    test_export_x_posts()
    test_export_empty_files()
    print("✓ All site export tests passed")
