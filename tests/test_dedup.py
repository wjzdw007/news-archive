"""Test high-frequency deduplication: inserting same URLs should be idempotent."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_archive.schema import Article
from news_archive.store import Store


def test_high_frequency_dedup():
    """Insert same articles twice; second insert should return False (already exists).
    
    This simulates running the fetch job twice in quick succession (e.g., manual
    trigger + scheduled trigger overlap, or retry after transient failure).
    
    Uses seeded test data instead of live RSS feeds to ensure deterministic results.
    """
    # Use a temporary DB for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        
        # Create test articles with unique URLs
        now = datetime.now(timezone.utc).isoformat()
        test_articles = [
            Article(
                url=f"https://example.com/article-{i}",
                title=f"Test Article {i}",
                published_at=now,
                summary=f"Summary for article {i}",
                source="test-source",
                fetched_at=now,
                content_snapshot=f"Content for article {i}",
                status="active",
            )
            for i in range(10)
        ]
        
        # First insert - should succeed for all
        store1 = Store(db_path)
        inserted1 = 0
        for article in test_articles:
            if store1.upsert(article):
                inserted1 += 1
        store1.close()
        
        print(f"First insert: inserted {inserted1} articles")
        assert inserted1 == len(test_articles), f"Expected {len(test_articles)} inserts, got {inserted1}"
        
        # Second insert - should be rejected by PRIMARY KEY constraint
        store2 = Store(db_path)
        inserted2 = 0
        for article in test_articles:
            if store2.upsert(article):
                inserted2 += 1
        store2.close()
        
        print(f"Second insert: inserted {inserted2} articles (expected 0)")
        
        # Check for duplicates in DB
        conn = sqlite3.connect(db_path)
        duplicates = conn.execute(
            "SELECT url, COUNT(*) as cnt FROM articles GROUP BY url HAVING cnt > 1"
        ).fetchall()
        total_rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        
        # Assertions
        assert inserted2 == 0, (
            f"Second insert should insert 0 articles (URL PRIMARY KEY dedup), but inserted {inserted2}. "
            f"This indicates duplicate URLs were allowed."
        )
        
        assert len(duplicates) == 0, (
            f"Found {len(duplicates)} duplicate URLs in database: {duplicates[:5]}"
        )
        
        assert total_rows == len(test_articles), (
            f"Expected {len(test_articles)} total rows, found {total_rows}"
        )
        
        print("✓ High-frequency dedup test PASSED: second insert was idempotent, no duplicates in DB")


if __name__ == "__main__":
    test_high_frequency_dedup()
