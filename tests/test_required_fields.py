"""Thin RSS items are skipped so Required Fields is not failed by title-only rows."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_archive.fetch import article_from_entry
from news_archive.schema import Article
from news_archive.sources import Source
from news_archive.store import Store
from news_archive.validate import check_required_fields

PUBLIC_SUMMARY_MAX = 280

_NYT_LIVE_URL = (
    "https://www.nytimes.com/live/2026/10/14/business/"
    "inflation-cpi-report-september/heres-the-latest"
)
_NYT_LIVE_TITLE = "Here’s the latest."
_NYT_BUSINESS = Source(
    id="nyt_business",
    name="NYT Business",
    feed_url="https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    category="财经",
    role="primary",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _article(
    url: str,
    *,
    title: str = "Has a title",
    summary: str | None,
    snapshot: str | None = None,
    source: str = "nyt_business",
    status: str = "active",
) -> Article:
    return Article(
        url=url,
        title=title,
        published_at="2026-10-14T14:43:18+00:00",
        summary=summary,
        source=source,
        fetched_at=_now(),
        content_snapshot=snapshot,
        status=status,  # type: ignore[arg-type]
    )


def test_empty_description_with_title_is_skipped():
    """Thin: has title, empty RSS body → skip insert; summary is never title."""
    entry = {
        "link": _NYT_LIVE_URL,
        "title": _NYT_LIVE_TITLE,
        "summary": "",
        "description": "   ",
    }
    article = article_from_entry(entry, _NYT_BUSINESS, _now())
    assert article is None

    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(Path(tmpdir) / "archive.sqlite3")
        # Ingest path never produces an Article; nothing is upserted.
        assert store.get_article(_NYT_LIVE_URL) is None
        store.close()
    print("✓ empty description + title is skipped; summary never = title")


def test_true_both_empty_without_title_is_skipped():
    """No usable title and no summary/description → do not insert."""
    entry = {
        "link": "https://example.com/no-title-no-body",
        "title": "   ",
        "summary": "",
        "description": None,
    }
    assert article_from_entry(entry, _NYT_BUSINESS, _now()) is None
    print("✓ true both-empty (no title, no body) is skipped")


def test_nonempty_rss_description_still_inserts():
    entry = {
        "link": "https://example.com/has-desc",
        "title": "Headline",
        "summary": "RSS teaser that should stay.",
    }
    article = article_from_entry(entry, _NYT_BUSINESS, _now())
    assert article is not None
    assert article.summary == "RSS teaser that should stay."
    assert article.summary != article.title
    assert len(article.summary) <= PUBLIC_SUMMARY_MAX

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        assert store.upsert(article)
        row = store.get_article(article.url)
        store.close()
        assert row is not None
        assert row["summary"] == "RSS teaser that should stay."
    print("✓ normal description still inserts (summary ≤280, not title)")


def test_relative_rss_link_is_resolved_against_feed_url():
    """TRT World emits `/article/...`; public href and enrich need http(s)."""
    src = Source(
        id="trt_world",
        name="TRT World",
        feed_url="https://www.trtworld.com/feed/rss.xml",
        category="国际",
        role="primary",
    )
    relative = article_from_entry(
        {
            "link": "/article/b00ff1504db7",
            "title": "Headline",
            "summary": "RSS teaser that should stay.",
        },
        src,
        _now(),
    )
    assert relative is not None
    assert relative.url == "https://www.trtworld.com/article/b00ff1504db7"
    absolute = article_from_entry(
        {
            "link": "https://www.trtworld.com/article/already-absolute",
            "title": "Headline",
            "summary": "RSS teaser that should stay.",
        },
        src,
        _now(),
    )
    assert absolute is not None
    assert absolute.url == "https://www.trtworld.com/article/already-absolute"
    print("✓ relative RSS link resolves against feed URL; absolute stays")


def test_purge_deletes_titled_both_empty_then_required_fields_pass():
    """Pre-seeded titled both-empty row is deleted; Required Fields then passes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                _NYT_LIVE_URL,
                title=_NYT_LIVE_TITLE,
                summary=None,
                snapshot=None,
            )
        )
        store.upsert(
            _article(
                "https://example.com/ok",
                title="Normal story",
                summary="Has a teaser",
                snapshot="Private body",
            )
        )
        store.upsert(
            _article(
                "https://example.com/gone",
                title="Gone title-only",
                summary=None,
                snapshot=None,
                status="gone",
            )
        )

        conn = sqlite3.connect(db_path)
        passed, message = check_required_fields(conn)
        conn.close()
        assert passed is False
        assert "content_snapshot+summary both empty: 1/" in message

        deleted = store.purge_both_empty_active()
        assert deleted == 1
        assert store.get_article(_NYT_LIVE_URL) is None
        kept = store.get_article("https://example.com/ok")
        assert kept is not None
        assert kept["summary"] == "Has a teaser"
        gone = store.get_article("https://example.com/gone")
        assert gone is not None
        assert gone["status"] == "gone"
        store.close()

        conn = sqlite3.connect(db_path)
        passed, message = check_required_fields(conn)
        conn.close()
        assert passed is True, message
        assert "both empty" not in message
        print("✓ purge deletes titled both-empty; normal rows kept; Required Fields PASS")


def test_purge_on_clean_db_deletes_zero():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(Path(tmpdir) / "archive.sqlite3")
        store.upsert(
            _article(
                "https://example.com/ok",
                title="Normal story",
                summary="Has a teaser",
                snapshot="Private body",
            )
        )
        assert store.purge_both_empty_active() == 0
        assert store.purge_both_empty_active() == 0
        row = store.get_article("https://example.com/ok")
        store.close()
        assert row is not None
        assert row["summary"] == "Has a teaser"
        print("✓ heal on clean DB deletes 0 (idempotent)")


def test_public_export_omits_snapshot_and_caps_summary():
    """Public articles.json still omits content_snapshot; summary ≤280."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        out_path = Path(tmpdir) / "articles.json"
        store = Store(db_path)
        article = article_from_entry(
            {
                "link": "https://example.com/has-desc",
                "title": "Headline",
                "summary": "乙" * 400,
            },
            _NYT_BUSINESS,
            _now(),
        )
        assert article is not None
        store.upsert(article)
        store.close()

        conn = sqlite3.connect(db_path)
        export_articles(conn, out_path)
        conn.close()

        exported = json.loads(out_path.read_text(encoding="utf-8"))
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert len(exported) == 1
        assert "content_snapshot" not in exported[0]
        assert exported[0]["summary"] == "乙" * PUBLIC_SUMMARY_MAX
        assert len(exported[0]["summary"]) <= PUBLIC_SUMMARY_MAX
        print("✓ public export omits content_snapshot; summary ≤280")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Testing thin RSS skip / Required Fields")
    print("=" * 70)
    try:
        test_empty_description_with_title_is_skipped()
        test_true_both_empty_without_title_is_skipped()
        test_nonempty_rss_description_still_inserts()
        test_relative_rss_link_is_resolved_against_feed_url()
        test_purge_deletes_titled_both_empty_then_required_fields_pass()
        test_purge_on_clean_db_deletes_zero()
        test_public_export_omits_snapshot_and_caps_summary()
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
    except AssertionError as exc:
        print(f"\n❌ TEST FAILED: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
