"""RSS source timeout retry + per-source soft-fail (keep Persist).

Mock httpx only — no live people.com.cn. Covers:
(a) timeout then success on retry inserts
(b) timeout × 3 → error recorded, CLI exit 0
(c) successful sources still persist when one source soft-fails
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from news_archive.fetch import (
    RSS_FETCH_ATTEMPTS,
    RSS_RETRY_BACKOFF_S,
    fetch_all,
    fetch_source,
)
from news_archive.schema import Article
from news_archive.sources import SOURCES, Source
from news_archive.store import Store
from news_archive.validate import check_source_incremental

ABC_NEWS = Source(
    id="abc_news",
    name="ABC News",
    feed_url="https://abcnews.go.com/abcnews/topstories",
    category="综合",
    role="primary",
)
PEOPLE_FINANCE = next(s for s in SOURCES if s.id == "people_finance")
WIRED = Source(
    id="wired",
    name="WIRED",
    feed_url="https://www.wired.com/feed/rss",
    category="科技",
    role="primary",
)

_ABC_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>ABC News</title>
    <item>
      <title>ABC headline</title>
      <link>https://abcnews.go.com/story-abc</link>
      <description>Non-empty ABC summary so thin-skip does not apply.</description>
      <pubDate>Thu, 16 Oct 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
_WIRED_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>WIRED</title>
    <item>
      <title>Wired headline</title>
      <link>https://www.wired.com/story-wired</link>
      <description>Non-empty Wired summary so thin-skip does not apply.</description>
      <pubDate>Thu, 16 Oct 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com/rss.xml")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=request,
                response=response,
            )


def _timeout() -> httpx.ReadTimeout:
    return httpx.ReadTimeout("The read operation timed out")


def _client_factory(by_url: dict[str, list[object]]):
    """httpx.Client stand-in: each GET consumes the next outcome for that URL."""

    class _Client:
        gets: list[str] = []

        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url: str, **_kwargs):
            _Client.gets.append(url)
            queue = by_url.get(url)
            if not queue:
                raise AssertionError(f"unexpected RSS GET {url}")
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    _Client.gets = []
    return _Client


def _article(url: str, source: str, title: str = "Headline") -> Article:
    return Article(
        url=url,
        title=title,
        published_at="2026-10-16T12:00:00+00:00",
        summary="Non-empty summary",
        source=source,
        fetched_at="2026-10-18T19:00:00+00:00",
        content_snapshot="snapshot body",
        status="active",
    )


def test_timeout_then_success_on_retry_inserts():
    """(a) First GET times out, retry succeeds, article is inserted, exit 0."""
    sleeps: list[float] = []
    people_rss = _ABC_RSS.replace(
        b"https://abcnews.go.com/story-abc",
        b"https://www.people.com.cn/story-1",
    ).replace(b"ABC headline", b"People headline")
    client_cls = _client_factory(
        {PEOPLE_FINANCE.feed_url: [_timeout(), _FakeResponse(people_rss)]}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("news_archive.fetch.httpx.Client", client_cls),
            patch("news_archive.fetch.time.sleep", side_effect=sleeps.append),
            patch("news_archive.cli.SOURCES", (PEOPLE_FINANCE,)),
            patch("news_archive.cli.enrich_store", return_value={"fetched": 0}),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])

        assert rc == 0, stderr.getvalue()
        stats = json.loads(stdout.getvalue())
        assert stats["errors"] == {}
        assert stats["inserted"] == 1
        assert stats["sources"]["people_finance"]["inserted"] == 1
        assert sleeps == [RSS_RETRY_BACKOFF_S]
        assert client_cls.gets == [PEOPLE_FINANCE.feed_url, PEOPLE_FINANCE.feed_url]

        store = Store(db_path)
        row = store.get_article("https://www.people.com.cn/story-1")
        store.close()
        assert row is not None
        assert row["title"] == "People headline"
        assert row["source"] == "people_finance"

        warn = stderr.getvalue()
        assert "RSS timeout attempt 1/3" in warn
        assert "The read operation timed out" in warn
    print("✓ (a) timeout then success on retry inserts")


def test_timeout_three_times_records_error_exit_0():
    """(b) Three timeouts → stats.errors recorded, CLI still exit 0."""
    client_cls = _client_factory(
        {
            PEOPLE_FINANCE.feed_url: [_timeout(), _timeout(), _timeout()],
        }
    )
    sleeps: list[float] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("news_archive.fetch.httpx.Client", client_cls),
            patch("news_archive.fetch.time.sleep", side_effect=sleeps.append),
            patch("news_archive.cli.SOURCES", (PEOPLE_FINANCE,)),
            patch("news_archive.cli.enrich_store", return_value={"fetched": 0}),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])

        assert rc == 0, stderr.getvalue()
        stats = json.loads(stdout.getvalue())
        assert "people_finance" in stats["errors"]
        assert "timed out" in stats["errors"]["people_finance"]
        assert stats["inserted"] == 0
        assert stats["sources"] == {}
        assert sleeps == [RSS_RETRY_BACKOFF_S, RSS_RETRY_BACKOFF_S * 2]
        assert client_cls.gets == [PEOPLE_FINANCE.feed_url] * RSS_FETCH_ATTEMPTS

        store = Store(db_path)
        conn = sqlite3.connect(db_path)
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        store.close()
        assert total == 0

        warn = stderr.getvalue()
        assert "RSS timeout attempt 1/3" in warn
        assert "RSS timeout attempt 2/3" in warn
        assert "RSS timeout attempt 3/3" in warn
        assert "RSS source soft-fail" in warn
    print("✓ (b) timeout×3 records error, exit 0")


def test_successful_sources_persist_when_one_soft_fails():
    """(c) people_finance times out ×3; abc_news + wired still persist; exit 0."""
    client_cls = _client_factory(
        {
            PEOPLE_FINANCE.feed_url: [_timeout(), _timeout(), _timeout()],
            ABC_NEWS.feed_url: [_FakeResponse(_ABC_RSS)],
            WIRED.feed_url: [_FakeResponse(_WIRED_RSS)],
        }
    )
    sleeps: list[float] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        jsonl_path = Path(tmpdir) / "archive.jsonl"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("news_archive.fetch.httpx.Client", client_cls),
            patch("news_archive.fetch.time.sleep", side_effect=sleeps.append),
            patch("news_archive.cli.SOURCES", (ABC_NEWS, PEOPLE_FINANCE, WIRED)),
            patch("news_archive.cli.enrich_store", return_value={"fetched": 0}),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            from news_archive.cli import main

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--export-jsonl",
                    str(jsonl_path),
                    "--json",
                ]
            )

        assert rc == 0, stderr.getvalue()
        stats = json.loads(stdout.getvalue())
        assert stats["errors"]["people_finance"]
        assert "timed out" in stats["errors"]["people_finance"]
        assert "abc_news" not in stats["errors"]
        assert "wired" not in stats["errors"]
        assert stats["inserted"] == 2
        assert stats["sources"]["abc_news"]["inserted"] == 1
        assert stats["sources"]["wired"]["inserted"] == 1
        assert "people_finance" not in stats["sources"]

        store = Store(db_path)
        abc = store.get_article("https://abcnews.go.com/story-abc")
        wired = store.get_article("https://www.wired.com/story-wired")
        people = store.get_article("https://www.people.com.cn/story-1")
        store.close()
        assert abc is not None
        assert abc["source"] == "abc_news"
        assert wired is not None
        assert wired["source"] == "wired"
        assert people is None

        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        urls = {json.loads(line)["url"] for line in lines}
        assert "https://abcnews.go.com/story-abc" in urls
        assert "https://www.wired.com/story-wired" in urls

        people_gets = [u for u in client_cls.gets if u == PEOPLE_FINANCE.feed_url]
        assert len(people_gets) == RSS_FETCH_ATTEMPTS
        assert ABC_NEWS.feed_url in client_cls.gets
        assert WIRED.feed_url in client_cls.gets
        assert "RSS source soft-fail" in stderr.getvalue()
    print("✓ (c) other sources persist when one RSS source soft-fails")


def test_fetch_all_isolates_timeout_without_raising():
    client_cls = _client_factory(
        {PEOPLE_FINANCE.feed_url: [_timeout(), _timeout(), _timeout()]}
    )
    with (
        patch("news_archive.fetch.httpx.Client", client_cls),
        patch("news_archive.fetch.time.sleep"),
    ):
        results = fetch_all([PEOPLE_FINANCE])
    payload = results["people_finance"]
    assert isinstance(payload, httpx.TimeoutException)
    assert "timed out" in str(payload)


def test_fetch_source_retries_connect_timeout_too():
    """ConnectTimeout is a TimeoutException; same 3-attempt retry."""
    client_cls = _client_factory(
        {
            ABC_NEWS.feed_url: [
                httpx.ConnectTimeout("timed out"),
                _FakeResponse(_ABC_RSS),
            ]
        }
    )
    sleeps: list[float] = []
    with (
        patch("news_archive.fetch.httpx.Client", client_cls),
        patch("news_archive.fetch.time.sleep", side_effect=sleeps.append),
    ):
        articles = fetch_source(ABC_NEWS)
    assert len(articles) == 1
    assert articles[0].url == "https://abcnews.go.com/story-abc"
    assert sleeps == [RSS_RETRY_BACKOFF_S]


def test_http_status_error_is_not_retried():
    """4xx/5xx stay a single attempt; still isolated by fetch_all."""
    client_cls = _client_factory(
        {ABC_NEWS.feed_url: [_FakeResponse(b"nope", status_code=500)]}
    )
    with (
        patch("news_archive.fetch.httpx.Client", client_cls),
        patch("news_archive.fetch.time.sleep") as sleep,
    ):
        results = fetch_all([ABC_NEWS])
    assert isinstance(results["abc_news"], httpx.HTTPStatusError)
    sleep.assert_not_called()
    assert client_cls.gets == [ABC_NEWS.feed_url]


def test_source_incremental_warns_not_fails_on_soft_error():
    """P0 incremental stays green when one source timed out but history exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for source in SOURCES:
            store.upsert(
                _article(
                    f"https://example.com/{source.id}/existing",
                    source.id,
                    title=f"{source.id} existing",
                )
            )
        store.close()

        conn = sqlite3.connect(db_path)
        run_stats = {
            "inserted": 2,
            "errors": {"people_finance": "The read operation timed out"},
            "sources": {
                "abc_news": {"fetched": 1, "inserted": 1},
                "wired": {"fetched": 1, "inserted": 1},
            },
        }
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            passed, message = check_source_incremental(conn, run_stats)
        conn.close()
        assert passed, message
        assert "Soft-failed this run" in message
        assert "people_finance" in message
        assert "FAIL" not in message
        assert "soft-fail" in stderr.getvalue()
    print("✓ source incremental WARNs on per-source timeout, does not fail")


if __name__ == "__main__":
    test_timeout_then_success_on_retry_inserts()
    test_timeout_three_times_records_error_exit_0()
    test_successful_sources_persist_when_one_soft_fails()
    test_fetch_all_isolates_timeout_without_raising()
    test_fetch_source_retries_connect_timeout_too()
    test_http_status_error_is_not_retried()
    test_source_incremental_warns_not_fails_on_soft_error()
    print("✓ RSS timeout retry + soft-fail tests PASSED")
