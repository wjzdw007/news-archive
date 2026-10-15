"""Test high-frequency deduplication: running fetch twice should not create duplicates."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from news_archive.fetch import fetch_all
from news_archive.sources import SOURCES
from news_archive.store import Store


def test_high_frequency_dedup():
    """Run fetch twice against same DB; second run should insert 0 new articles.
    
    This simulates running the fetch job twice in quick succession (e.g., manual
    trigger + scheduled trigger overlap, or retry after transient failure).
    """
    # Use a temporary DB for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        
        # First fetch
        store1 = Store(db_path)
        results1 = fetch_all(SOURCES)
        
        inserted1 = 0
        errors1 = []
        for source_id, payload in results1.items():
            if isinstance(payload, Exception):
                errors1.append(source_id)
                continue
            for article in payload:
                if store1.upsert(article):
                    inserted1 += 1
        
        store1.close()
        
        print(f"First fetch: inserted {inserted1} articles, {len(errors1)} errors")
        
        # Skip test if too many sources failed (network issues, etc.)
        if len(errors1) > len(SOURCES) // 2:
            print(f"WARNING: >50% sources failed ({len(errors1)}/{len(SOURCES)}), skipping dedup test")
            return
        
        # Verify first fetch got some data
        assert inserted1 > 0, "First fetch should have inserted articles"
        
        # Second fetch - should be immediate (high-frequency scenario)
        store2 = Store(db_path)
        results2 = fetch_all(SOURCES)
        
        inserted2 = 0
        for source_id, payload in results2.items():
            if isinstance(payload, Exception):
                continue
            for article in payload:
                if store2.upsert(article):
                    inserted2 += 1
        
        store2.close()
        
        print(f"Second fetch: inserted {inserted2} articles (expected 0)")
        
        # Check for duplicates in DB
        conn = sqlite3.connect(db_path)
        duplicates = conn.execute(
            "SELECT url, COUNT(*) as cnt FROM articles GROUP BY url HAVING cnt > 1"
        ).fetchall()
        conn.close()
        
        # Assertions
        assert inserted2 == 0, (
            f"Second fetch should insert 0 articles (URL dedup), but inserted {inserted2}. "
            f"This indicates duplicate URLs were allowed."
        )
        
        assert len(duplicates) == 0, (
            f"Found {len(duplicates)} duplicate URLs in database: {duplicates[:5]}"
        )
        
        print("✓ High-frequency dedup test PASSED: second fetch inserted 0, no duplicates in DB")


if __name__ == "__main__":
    test_high_frequency_dedup()
