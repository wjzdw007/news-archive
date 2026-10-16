"""Empty RSS description must not hard-fail daily-fetch Required Fields."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_archive.fetch import article_from_entry
from news_archive.schema import PUBLIC_SUMMARY_MAX, Article, title_as_summary
from news_archive.sources import Source
from news_archive.store import Store
from news_archive.validate import check_required_fields

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


def test_empty_rss_description_falls_back_to_title():
    """Ingest: empty RSS description / summary → public summary is title (≤280)."""
    entry = {
        "link": _NYT_LIVE_URL,
        "title": _NYT_LIVE_TITLE,
        "summary": "",
        "description": "   ",
    }
    article = article_from_entry(entry, _NYT_BUSINESS, _now())
    assert article is not None
    assert article.summary == _NYT_LIVE_TITLE
    assert article.content_snapshot is None
    assert len(article.summary) <= PUBLIC_SUMMARY_MAX
    print("✓ ingest empty RSS description → summary becomes title (≤280)")


def test_empty_rss_description_truncates_long_title():
    title = "甲" * 400
    entry = {
        "link": "https://example.com/long-title-only",
        "title": title,
        "summary": None,
        "description": None,
    }
    article = article_from_entry(entry, _NYT_BUSINESS, _now())
    assert article is not None
    assert article.summary == "甲" * PUBLIC_SUMMARY_MAX
    assert len(article.summary) == PUBLIC_SUMMARY_MAX
    print("✓ ingest empty description + long title → summary capped at 280")


def test_nonempty_rss_description_is_kept():
    entry = {
        "link": "https://example.com/has-desc",
        "title": "Headline",
        "summary": "RSS teaser that should stay.",
    }
    article = article_from_entry(entry, _NYT_BUSINESS, _now())
    assert article is not None
    assert article.summary == "RSS teaser that should stay."
    assert len(article.summary) <= PUBLIC_SUMMARY_MAX
    print("✓ ingest keeps a real RSS description (≤280)")


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


def test_missing_title_is_not_inserted_even_with_description():
    entry = {
        "link": "https://example.com/body-only",
        "title": "",
        "summary": "Has a teaser but no title.",
    }
    assert article_from_entry(entry, _NYT_BUSINESS, _now()) is None
    print("✓ missing title is skipped (title is required)")


def test_required_fields_fails_on_both_empty_then_passes_after_heal():
    """Validate stays zero-tolerance; self-heal fills title so the check can pass."""
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
        store.close()

        conn = sqlite3.connect(db_path)
        passed, message = check_required_fields(conn)
        conn.close()
        assert passed is False
        assert "content_snapshot+summary both empty: 1/" in message

        store = Store(db_path)
        healed = store.fill_empty_summaries_from_title()
        assert healed == 1
        row = store.get_article(_NYT_LIVE_URL)
        assert row is not None
        assert row["summary"] == _NYT_LIVE_TITLE
        assert row["content_snapshot"] is None
        assert len(row["summary"]) <= PUBLIC_SUMMARY_MAX
        store.close()

        conn = sqlite3.connect(db_path)
        passed, message = check_required_fields(conn)
        conn.close()
        assert passed is True, message
        assert "both empty" not in message
        print("✓ Required Fields fails on both-empty, passes after title heal")


def test_heal_does_not_overwrite_existing_summary_or_gone():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                "https://example.com/keep",
                title="Keep title",
                summary="Keep summary",
                snapshot=None,
            )
        )
        store.upsert(
            _article(
                "https://example.com/gone",
                title="Gone title",
                summary=None,
                snapshot=None,
                status="gone",
            )
        )
        assert store.fill_empty_summaries_from_title() == 0
        assert store.get_article("https://example.com/keep")["summary"] == "Keep summary"
        assert store.get_article("https://example.com/gone")["summary"] is None
        store.close()
        print("✓ heal skips rows that already have summary, and gone rows")


def test_public_export_omits_snapshot_and_caps_healed_summary():
    """Public articles.json still omits content_snapshot; summary ≤280."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        out_path = Path(tmpdir) / "articles.json"
        store = Store(db_path)
        article = article_from_entry(
            {
                "link": "https://example.com/title-only",
                "title": "乙" * 400,
                "summary": "",
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
        print("✓ public export omits content_snapshot; healed summary ≤280")


def test_title_as_summary_helper():
    assert title_as_summary("  hi  ") == "hi"
    assert title_as_summary("   ") is None
    assert title_as_summary(None) is None
    assert title_as_summary("x" * 281) == "x" * PUBLIC_SUMMARY_MAX
    print("✓ title_as_summary trims and caps at 280")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Testing empty-summary title fallback / Required Fields")
    print("=" * 70)
    try:
        test_empty_rss_description_falls_back_to_title()
        test_empty_rss_description_truncates_long_title()
        test_nonempty_rss_description_is_kept()
        test_true_both_empty_without_title_is_skipped()
        test_missing_title_is_not_inserted_even_with_description()
        test_required_fields_fails_on_both_empty_then_passes_after_heal()
        test_heal_does_not_overwrite_existing_summary_or_gone()
        test_public_export_omits_snapshot_and_caps_healed_summary()
        test_title_as_summary_helper()
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
