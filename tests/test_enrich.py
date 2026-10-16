"""Product gates for archive-first page enrichment.

1. Long public summary but missing snapshot → DB has snapshot;
   public JSON still has no content_snapshot key
2. Already-usable snapshot → second run does not HTTP again
3. Simulated 403/paywall → that row soft-fails; overall fetch still green
4. Full public JSON sweep: no content_snapshot key; no public summary >280
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from datetime import datetime, timedelta, timezone

from news_archive.enrich import (
    CONSECUTIVE_FAIL_LIMIT,
    COOLDOWN_HOURS,
    MAX_HTTP_PER_RUN,
    MIN_USABLE_SUMMARY,
    PUBLIC_SUMMARY_MAX,
    derive_public_summary,
    enrich_store,
    html_to_text,
    is_usable_snapshot,
    needs_summary_fill,
    render_diversity_summary,
    render_job_summary,
    should_fetch_page,
    write_job_summary,
)
from news_archive.news_display import display_window_diversity
from news_archive.enrich_alternates import (
    MAX_ALTERNATES_PER_ARTICLE,
    alternate_urls_for,
)
from news_archive.schema import Article
from news_archive.store import Store
from news_archive.x_store import XStore

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PEOPLE_HTML = (FIXTURES / "people_cn_article.html").read_text(encoding="utf-8")
PEOPLE_URL = "https://finance.people.com.cn/n1/2026/1015/c1004-40399999.html"
PAYWALL_URL = "https://www.ftchinese.com/story/paywall-403"
LONG_SUMMARY_URL = "https://www.theguardian.com/world/2026/oct/15/long-summary"

sys.path.insert(0, str(ROOT / "scripts"))
from export_site_data import (  # noqa: E402
    export_articles,
    export_daily_briefs,
    export_topics,
    export_x_posts,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", content_type: str = "text/html"):
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type}


class _RecordingClient:
    def __init__(self, mapping: dict[str, _FakeResponse | Exception]):
        self.mapping = mapping
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs):
        self.calls.append(url)
        item = self.mapping.get(url)
        if item is None:
            return _FakeResponse(403, "unmapped")
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        return None


def _article(
    url: str,
    *,
    title: str = "标题",
    summary: str | None = None,
    snapshot: str | None = None,
    status: str = "active",
    source: str = "people_finance",
    fetched_at: str = "2026-10-15T10:00:00Z",
) -> Article:
    return Article(
        url=url,
        title=title,
        published_at="2026-10-15T08:00:00Z",
        summary=summary,
        source=source,
        fetched_at=fetched_at,
        content_snapshot=snapshot,
        status=status,  # type: ignore[arg-type]
    )


def _long_summary() -> str:
    text = (
        "联合国安理会今日就地区局势举行紧急会议，多国代表呼吁保持克制并恢复对话，"
        "同时强调人道救援通道必须保持畅通，避免冲突进一步外溢到周边国家与全球市场。"
        "分析人士认为，后续仍需观察各方表态与实地停火安排能否落实。"
    )
    assert MIN_USABLE_SUMMARY <= len(html_to_text(text)) <= PUBLIC_SUMMARY_MAX
    return text


def _export_articles_json(db_path: Path, out_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    export_articles(conn, out_path)
    conn.close()
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_html_to_text_strips_people_cn_chrome():
    text = html_to_text(PEOPLE_HTML)
    assert "<p>" not in text
    assert "script" not in text.lower() or "analytics" not in text
    assert "央行发布三季度金融统计数据" in text
    assert "社会融资规模增量保持平稳" in text
    assert len(text) >= MIN_USABLE_SUMMARY


def test_needs_summary_fill_triggers():
    assert needs_summary_fill({"summary": None, "status": "active"})
    assert needs_summary_fill({"summary": "   ", "status": "active"})
    assert needs_summary_fill({"summary": "<p>  </p>", "status": "active"})
    assert needs_summary_fill({"summary": "<p>短图说</p>", "status": "active"})
    assert needs_summary_fill({"summary": "甲" * 79, "status": "active"})
    assert not needs_summary_fill({"summary": "甲" * 80, "status": "active"})
    assert not needs_summary_fill({"summary": "", "status": "gone"})


def test_is_usable_snapshot_rejects_empty_and_shell():
    assert not is_usable_snapshot(None)
    assert not is_usable_snapshot("")
    assert not is_usable_snapshot("短")
    assert not is_usable_snapshot("首页 导航 登录 搜索 版权所有 网站地图")
    long_shell = ("首页 导航 登录 搜索 版权所有 网站地图 联系我们 " * 8).strip()
    assert len(html_to_text(long_shell)) >= MIN_USABLE_SUMMARY
    assert not is_usable_snapshot(long_shell)
    assert is_usable_snapshot("甲" * 80)
    assert is_usable_snapshot(PEOPLE_HTML)


def test_should_fetch_page_archive_first():
    missing = {
        "url": PEOPLE_URL,
        "summary": "",
        "content_snapshot": None,
        "status": "active",
    }
    assert should_fetch_page(missing)
    # Long public summary still enqueues when snapshot is missing.
    assert should_fetch_page({**missing, "summary": "乙" * 80})
    assert not should_fetch_page({**missing, "status": "gone"})
    assert not should_fetch_page({**missing, "url": "ftp://people.com.cn/x"})
    assert not should_fetch_page({**missing, "url": "not-a-url"})
    assert not should_fetch_page({**missing, "content_snapshot": "丙" * 80})
    # Too-short shell/nav snapshot is unusable → still fetch.
    assert should_fetch_page(
        {**missing, "content_snapshot": "首页 登录 导航 搜索 版权所有"}
    )


def test_people_cn_empty_summary_enrich_writes_snapshot_and_public_summary():
    """Empty-summary people.cn-style fixture → DB snapshot; public summary 80–280."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(PEOPLE_URL, title="央行发布三季度金融统计数据", summary=None))

        client = _RecordingClient({PEOPLE_URL: _FakeResponse(200, PEOPLE_HTML)})
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        assert stats["fetched"] == 1
        assert stats["soft_failed"] == 0
        assert client.calls == [PEOPLE_URL]

        row = store.get_article(PEOPLE_URL)
        assert row is not None
        snapshot = row["content_snapshot"]
        assert snapshot
        assert "<p>" not in snapshot
        assert "央行发布三季度金融统计数据" in snapshot
        assert "保持流动性合理充裕" in snapshot
        assert len(html_to_text(snapshot)) >= MIN_USABLE_SUMMARY

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "content_snapshot" not in exported[0]
        summary = exported[0]["summary"]
        assert summary
        assert "<" not in summary
        assert MIN_USABLE_SUMMARY <= len(summary) <= PUBLIC_SUMMARY_MAX
        # Full snapshot stays private and is longer than the public cap.
        assert len(snapshot) > len(summary)
        store.close()


def test_long_summary_missing_snapshot_writes_snapshot_hides_from_public_json():
    """Gate 1: long public summary, no snapshot → enrich fills DB snapshot only."""
    long_summary = _long_summary()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                LONG_SUMMARY_URL,
                title="安理会紧急会议",
                summary=long_summary,
                source="guardian_world",
            )
        )
        client = _RecordingClient({LONG_SUMMARY_URL: _FakeResponse(200, PEOPLE_HTML)})
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        assert stats["fetched"] == 1
        assert client.calls == [LONG_SUMMARY_URL]

        row = store.get_article(LONG_SUMMARY_URL)
        assert row is not None
        assert row["content_snapshot"]
        assert "央行发布三季度金融统计数据" in row["content_snapshot"]
        # Qualified public summary is left alone (not rewritten from snapshot).
        assert row["summary"] == long_summary

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "content_snapshot" not in exported[0]
        assert exported[0]["summary"] == long_summary
        assert len(exported[0]["summary"]) <= PUBLIC_SUMMARY_MAX
        store.close()


def test_usable_snapshot_second_run_does_not_http():
    """Gate 2: already-usable snapshot → second run does not HTTP again."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(PEOPLE_URL, title="央行发布三季度金融统计数据", summary=None))
        client = _RecordingClient({PEOPLE_URL: _FakeResponse(200, PEOPLE_HTML)})

        first = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert first["fetched"] == 1
        assert client.calls == [PEOPLE_URL]
        snapshot = store.get_article(PEOPLE_URL)["content_snapshot"]
        assert snapshot

        second = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert second["fetched"] == 0
        assert client.calls == [PEOPLE_URL]
        assert store.get_article(PEOPLE_URL)["content_snapshot"] == snapshot
        store.close()


def test_public_json_sweep_omits_content_snapshot_and_caps_summary():
    """Gate 4: Full public JSON sweep: no content_snapshot; no summary >280."""
    secret = "PRIVATE_SNAPSHOT_BODY_MUST_NEVER_SHIP"
    overlong = "甲" * 400
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                PEOPLE_URL,
                title="央行",
                summary=overlong,
                snapshot=secret,
            )
        )
        store.upsert_daily_brief(
            {
                "date": "2026-10-15",
                "generated_at": "2026-10-15T12:00:00+00:00",
                "status": "ok",
                "model": "deepseek/deepseek-flash",
                "lede": "可见导语。",
                "sections": [
                    {
                        "topic_id": None,
                        "title": "其它",
                        "bullets": ["可见摘要。"],
                        "links": [
                            {
                                "title": "央行",
                                "url": PEOPLE_URL,
                                "source": "people_finance",
                            }
                        ],
                    }
                ],
                "error": None,
            }
        )
        store.upsert_topic_brief(
            {
                "topic_id": "t1",
                "title": "金融数据",
                "sources": [{"title": "央行", "url": PEOPLE_URL}],
                "article_urls": [PEOPLE_URL],
                "generated_at": "2026-10-15T12:00:00Z",
                "model": "rules-v2",
                "status": "ok",
            }
        )
        XStore(db_path).close()
        store.close()

        conn = sqlite3.connect(db_path)
        out_dir = Path(tmpdir)
        export_articles(conn, out_dir / "articles.json")
        export_daily_briefs(conn, out_dir / "daily_briefs.json")
        export_topics(conn, out_dir / "topics.json")
        export_x_posts(conn, out_dir / "x_posts.json")
        conn.close()

        for name in ("articles.json", "daily_briefs.json", "topics.json", "x_posts.json"):
            raw = (out_dir / name).read_text(encoding="utf-8")
            assert "content_snapshot" not in raw, name
            assert secret not in raw, name
            payload = json.loads(raw)
            blob = json.dumps(payload, ensure_ascii=False)
            assert "content_snapshot" not in blob, name

        articles = json.loads((out_dir / "articles.json").read_text(encoding="utf-8"))
        for item in articles:
            summary = item.get("summary") or ""
            assert len(summary) <= PUBLIC_SUMMARY_MAX
        assert articles[0]["summary"] == "甲" * PUBLIC_SUMMARY_MAX

        app_js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        assert "article.content_snapshot" not in app_js
        assert "articles.json" in (ROOT / "site" / "app.js").read_text(encoding="utf-8")


def test_simulated_403_soft_fails_row_but_fetch_job_stays_green():
    """Gate 3: 403/paywall on one URL: that row unchanged; CLI fetch still exit 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(PAYWALL_URL, title="付费墙稿", summary="付费墙RSS摘要", source="ftchinese")
        )
        store.upsert(
            _article(
                PEOPLE_URL,
                title="央行发布三季度金融统计数据",
                summary=None,
                source="people_finance",
            )
        )
        store.close()

        client = _RecordingClient(
            {
                PAYWALL_URL: _FakeResponse(403, "Paywall"),
                PEOPLE_URL: _FakeResponse(200, PEOPLE_HTML),
            }
        )

        thin_people = _article(
            PEOPLE_URL, title="央行发布三季度金融统计数据", summary=None
        )
        thin_paywall = _article(
            PAYWALL_URL, title="付费墙稿", summary="付费墙RSS摘要", source="ftchinese"
        )

        def fake_fetch_all(_sources):
            return {
                "people_finance": [thin_people],
                "ftchinese": [thin_paywall],
            }

        with (
            patch("news_archive.cli.fetch_all", side_effect=fake_fetch_all),
            patch("news_archive.enrich.httpx.Client", return_value=client),
            patch("news_archive.enrich.ENRICH_DELAY_S", 0),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])

        assert rc == 0
        store = Store(db_path)
        paywall = store.get_article(PAYWALL_URL)
        people = store.get_article(PEOPLE_URL)
        assert paywall is not None
        assert people is not None
        assert not paywall["content_snapshot"]
        assert people["content_snapshot"]
        assert "央行" in people["content_snapshot"]
        store.close()


def test_existing_snapshot_derives_summary_without_http():
    snapshot = "甲" * 200
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(PEOPLE_URL, summary="", snapshot=snapshot))
        client = _RecordingClient({PEOPLE_URL: _FakeResponse(200, PEOPLE_HTML)})
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert client.calls == []
        assert stats["derived"] == 1
        row = store.get_article(PEOPLE_URL)
        assert row is not None
        assert row["content_snapshot"] == snapshot
        assert row["summary"] == snapshot[:PUBLIC_SUMMARY_MAX]
        store.close()


def test_export_caps_long_summary_at_280_and_omits_snapshot():
    long_summary = "甲" * 400
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                LONG_SUMMARY_URL,
                summary=long_summary,
                snapshot="<p>" + "乙" * 500 + "</p>",
                source="guardian_world",
            )
        )
        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "乙" not in raw
        assert len(exported[0]["summary"]) == PUBLIC_SUMMARY_MAX
        assert exported[0]["summary"] == "甲" * PUBLIC_SUMMARY_MAX
        store.close()


def test_gone_and_timeout_do_not_write_snapshot():
    gone_url = "https://www.people.com.cn/gone.html"
    timeout_url = "https://www.people.com.cn/timeout.html"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(gone_url, summary="", status="gone"))
        store.upsert(_article(timeout_url, summary=""))
        client = _RecordingClient(
            {timeout_url: httpx.TimeoutException("timed out")}
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert gone_url not in client.calls
        assert timeout_url in client.calls
        assert stats["soft_failed"] == 1
        assert store.get_article(gone_url)["content_snapshot"] is None
        assert store.get_article(timeout_url)["content_snapshot"] is None
        store.close()


def test_max_http_stockpiles_across_runs():
    """≤40 HTTP per run; leftover missing snapshots wait for the next cron."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        urls = [f"https://example.com/story-{i}" for i in range(3)]
        for url in urls:
            store.upsert(_article(url, summary=_long_summary(), source="36kr"))
        client = _RecordingClient(
            {url: _FakeResponse(200, PEOPLE_HTML) for url in urls}
        )
        stats = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, max_http=2
        )
        assert len(client.calls) == 2
        assert stats["fetched"] == 2
        filled = sum(
            1 for url in urls if store.get_article(url)["content_snapshot"]
        )
        assert filled == 2
        leftover = [url for url in urls if not store.get_article(url)["content_snapshot"]]
        assert len(leftover) == 1

        stats2 = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, max_http=2
        )
        assert leftover[0] in client.calls
        assert stats2["fetched"] == 1
        assert all(store.get_article(url)["content_snapshot"] for url in urls)
        store.close()


def test_derive_public_summary_prefers_snapshot():
    snapshot = "快照正文" * 40
    summary = "原摘要" * 40
    derived = derive_public_summary(snapshot=snapshot, summary=summary)
    assert derived is not None
    assert derived.startswith("快照正文")
    assert len(derived) <= PUBLIC_SUMMARY_MAX


def test_cli_enrich_exception_does_not_fail_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(PEOPLE_URL, summary="合格摘要" * 20))
        store.close()

        with (
            patch("news_archive.cli.fetch_all", return_value={"people_finance": []}),
            patch("news_archive.cli.enrich_store", side_effect=RuntimeError("boom")),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])
        assert rc == 0


def _nyt_urls(n: int) -> list[str]:
    return [f"https://www.nytimes.com/2026/10/16/world/story-{i}.html" for i in range(n)]


def _http_for_article(url: str, source: str) -> int:
    """Primary GET + configured alternates (budget cost of one hard-source miss)."""
    return 1 + len(alternate_urls_for(url=url, source=source))


def _people_urls(n: int) -> list[str]:
    return [
        f"https://finance.people.com.cn/n1/2026/1016/c1004-{40400000 + i}.html"
        for i in range(n)
    ]


def test_nyt_three_403s_stops_source_others_still_fetch():
    """NYT 403 ×3 in one run → stop NYT; other sources still HTTP; total ≤40."""
    assert MAX_HTTP_PER_RUN == 40
    nyt_urls = _nyt_urls(8)
    people_urls = _people_urls(3)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        # Newer fetched_at so NYT is processed first (the live budget-burn case).
        for url in nyt_urls:
            store.upsert(
                _article(
                    url,
                    summary=_long_summary(),
                    source="nyt_world",
                    fetched_at="2026-10-16T12:00:00Z",
                )
            )
        for url in people_urls:
            store.upsert(
                _article(
                    url,
                    summary=None,
                    source="people_finance",
                    fetched_at="2026-10-16T10:00:00Z",
                )
            )
        mapping: dict[str, _FakeResponse | Exception] = {
            url: _FakeResponse(403, "Forbidden") for url in nyt_urls
        }
        mapping.update({url: _FakeResponse(200, PEOPLE_HTML) for url in people_urls})
        client = _RecordingClient(mapping)

        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        nyt_calls = [u for u in client.calls if u in nyt_urls]
        people_calls = [u for u in client.calls if u in people_urls]
        assert len(nyt_calls) == CONSECUTIVE_FAIL_LIMIT
        assert len(people_calls) == len(people_urls)
        assert len(client.calls) <= MAX_HTTP_PER_RUN
        nyt_http = CONSECUTIVE_FAIL_LIMIT * _http_for_article(nyt_urls[0], "nyt_world")
        assert stats["http_used"] == nyt_http + len(people_urls)
        # Alternates were attempted (AMP / mobile) but still only 3 articles.
        assert any(".amp.html" in u or "mobile.nytimes.com" in u for u in client.calls)
        assert stats["soft_failed"] == CONSECUTIVE_FAIL_LIMIT
        assert stats["fetched"] == len(people_urls)
        assert stats["by_source"]["nyt_world"]["stopped"] is True
        assert stats["by_source"]["nyt_world"]["soft_fail"] == CONSECUTIVE_FAIL_LIMIT
        assert stats["by_source"]["nyt_world"]["success"] == 0
        assert stats["by_source"]["people_finance"]["stopped"] is False
        assert stats["by_source"]["people_finance"]["success"] == len(people_urls)
        assert stats["coverage"]["usable_snapshots"] == len(people_urls)
        assert stats["coverage"]["active_articles"] == len(nyt_urls) + len(people_urls)

        backoff = store.get_enrich_backoff()
        assert "nyt_world" in backoff
        assert "people_finance" not in backoff
        for url in nyt_urls:
            assert not store.get_article(url)["content_snapshot"]
        for url in people_urls:
            assert store.get_article(url)["content_snapshot"]

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert all("content_snapshot" not in item for item in exported)
        store.close()


def test_backoff_cooldown_persists_six_hours_then_expires():
    """Tripped source stays dequeued for 6h (sqlite run state), then retries."""
    nyt_urls = _nyt_urls(4)
    people_url = _people_urls(1)[0]
    now = datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(
                _article(
                    url,
                    summary=_long_summary(),
                    source="nyt_world",
                    fetched_at="2026-10-16T12:00:00Z",
                )
            )
        store.upsert(
            _article(
                people_url,
                summary=None,
                source="people_finance",
                fetched_at="2026-10-16T10:00:00Z",
            )
        )
        mapping: dict[str, _FakeResponse | Exception] = {
            url: _FakeResponse(403, "Forbidden") for url in nyt_urls
        }
        mapping[people_url] = _FakeResponse(200, PEOPLE_HTML)
        client = _RecordingClient(mapping)

        first = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, now_fn=lambda: now
        )
        assert first["by_source"]["nyt_world"]["stopped"] is True
        until_raw = store.get_enrich_backoff()["nyt_world"]
        until = datetime.fromisoformat(until_raw)
        assert until == now + timedelta(hours=COOLDOWN_HOURS)

        calls_after_first = list(client.calls)
        second = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, now_fn=lambda: now
        )
        assert client.calls == calls_after_first
        assert second["by_source"]["nyt_world"]["in_cooldown"] is True
        assert second["by_source"]["nyt_world"]["success"] == 0
        assert sum(1 for u in client.calls if u in nyt_urls) == CONSECUTIVE_FAIL_LIMIT

        for url in nyt_urls:
            mapping[url] = _FakeResponse(200, PEOPLE_HTML)
        expired = now + timedelta(hours=COOLDOWN_HOURS, seconds=1)
        third = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, now_fn=lambda: expired
        )
        assert any(u in nyt_urls for u in client.calls[len(calls_after_first) :])
        assert third["fetched"] >= 1
        store.close()


def test_http_budget_stays_at_40_when_nyt_would_burn_it():
    """Without backoff NYT would consume all 40; with backoff others still fetch."""
    nyt_urls = _nyt_urls(45)
    people_urls = _people_urls(5)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(
                _article(
                    url,
                    summary=_long_summary(),
                    source="nyt_world",
                    fetched_at="2026-10-16T12:00:00Z",
                )
            )
        for url in people_urls:
            store.upsert(
                _article(
                    url,
                    summary=None,
                    source="people_finance",
                    fetched_at="2026-10-16T10:00:00Z",
                )
            )
        mapping: dict[str, _FakeResponse | Exception] = {
            url: _FakeResponse(403, "Forbidden") for url in nyt_urls
        }
        mapping.update({url: _FakeResponse(200, PEOPLE_HTML) for url in people_urls})
        client = _RecordingClient(mapping)
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        assert len(client.calls) <= MAX_HTTP_PER_RUN
        assert stats["http_used"] <= MAX_HTTP_PER_RUN
        nyt_calls = [u for u in client.calls if u in set(nyt_urls)]
        assert len(nyt_calls) == CONSECUTIVE_FAIL_LIMIT
        assert set(u for u in client.calls if u in people_urls) == set(people_urls)
        assert stats["fetched"] == len(people_urls)
        store.close()


def test_mixed_403_429_timeout_trips_backoff():
    nyt_urls = _nyt_urls(3)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(_article(url, summary=_long_summary(), source="nyt_world"))
        extra = "https://www.nytimes.com/2026/10/16/world/story-extra.html"
        store.upsert(_article(extra, summary=_long_summary(), source="nyt_world"))
        client = _RecordingClient(
            {
                nyt_urls[0]: _FakeResponse(403, "no"),
                nyt_urls[1]: _FakeResponse(429, "slow"),
                nyt_urls[2]: httpx.TimeoutException("timed out"),
                extra: _FakeResponse(200, PEOPLE_HTML),
            }
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert extra not in client.calls
        assert stats["by_source"]["nyt_world"]["stopped"] is True
        assert extra not in [u for u in client.calls]
        store.close()


def test_job_summary_coverage_board_omits_snapshot_body():
    """Job Summary has totals + per-source backoff; never leaks snapshot text."""
    nyt_urls = _nyt_urls(3)
    people_url = _people_urls(1)[0]
    secret = "央行发布三季度金融统计数据"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(
                _article(
                    url,
                    summary=_long_summary(),
                    source="nyt_world",
                    fetched_at="2026-10-16T12:00:00Z",
                )
            )
        store.upsert(
            _article(
                people_url,
                summary=None,
                source="people_finance",
                fetched_at="2026-10-16T10:00:00Z",
            )
        )
        mapping: dict[str, _FakeResponse | Exception] = {
            url: _FakeResponse(403, "Forbidden") for url in nyt_urls
        }
        mapping[people_url] = _FakeResponse(200, PEOPLE_HTML)
        client = _RecordingClient(mapping)
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        md = render_job_summary(stats)
        assert "## Enrich coverage board" in md
        assert f"**candidates:** {stats['candidates']}" in md
        assert f"**fetched (ok):** {stats['fetched']}" in md
        assert f"**soft_failed:** {stats['soft_failed']}" in md
        assert f"**skipped:** {stats['skipped']}" in md
        assert "| nyt_world |" in md
        assert "| people_finance |" in md
        assert "stopped (backoff)" in md
        assert "yes" in md
        assert "usable `content_snapshot`" in md
        assert f"{stats['coverage']['usable_snapshots']} / {stats['coverage']['active_articles']}" in md
        assert secret not in md
        assert "Paywall" not in md
        assert people_url not in md
        assert nyt_urls[0] not in md

        summary_path = Path(tmpdir) / "step-summary.md"
        write_job_summary(stats, path=summary_path)
        written = summary_path.read_text(encoding="utf-8")
        assert written in {md, md + "\n"}
        assert secret not in written
        index_html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        assert 'id="stats-tab"' not in index_html
        assert "/stats" not in app_js

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert all("content_snapshot" not in item for item in exported)
        store.close()


def test_job_summary_primary_source_max_is_display_window_not_raw():
    """Primary diversity line is display-window max; raw front-50 is diagnostic only."""
    articles = json.loads((FIXTURES / "news_source_diversity.json").read_text(encoding="utf-8"))
    diversity = display_window_diversity(articles)
    assert diversity["display_max"] == 6
    assert diversity["display_max_source"] == "36kr"
    assert diversity["raw_max"] == 20
    assert diversity["raw_max"] > diversity["display_max"]

    md = render_job_summary(
        {
            "candidates": 0,
            "fetched": 0,
            "soft_failed": 0,
            "skipped": 0,
            "by_source": {},
            "coverage": {"usable_snapshots": 0, "active_articles": 0},
        },
        diversity=diversity,
    )
    section = render_diversity_summary(diversity)
    assert "### News list diversity (display-window)" in md
    assert section in md
    assert "**display-window same-source max:** 6 (`36kr`)" in md
    assert "NEWS_SOURCE_CAP=6" in md
    assert "raw published_at-order front-50 max: 20 (`36kr`)" in md
    assert "not the display gate" in md
    primary_at = md.index("**display-window same-source max:**")
    raw_at = md.index("raw published_at-order front-50 max:")
    assert primary_at < raw_at
    # Bare/raw 20 must not be the primary bold number (false 'gate broken' alarm).
    assert "**display-window same-source max:** 20" not in md
    assert "content_snapshot" not in section
    for article in articles:
        assert article["url"] not in md
        assert article["title"] not in md


def test_cli_writes_job_summary_and_stays_green_on_nyt_backoff():
    nyt_urls = _nyt_urls(3)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        summary_path = Path(tmpdir) / "GITHUB_STEP_SUMMARY.md"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(_article(url, summary=_long_summary(), source="nyt_world"))
        store.upsert(_article(PEOPLE_URL, title="央行", summary=None))
        store.close()

        client = _RecordingClient(
            {
                **{url: _FakeResponse(403, "Forbidden") for url in nyt_urls},
                PEOPLE_URL: _FakeResponse(200, PEOPLE_HTML),
            }
        )

        def fake_fetch_all(_sources):
            return {
                "nyt_world": [
                    _article(url, summary=_long_summary(), source="nyt_world")
                    for url in nyt_urls
                ],
                "people_finance": [
                    _article(PEOPLE_URL, title="央行", summary=None)
                ],
            }

        with (
            patch("news_archive.cli.fetch_all", side_effect=fake_fetch_all),
            patch("news_archive.enrich.httpx.Client", return_value=client),
            patch("news_archive.enrich.ENRICH_DELAY_S", 0),
            patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_path)}, clear=False),
        ):
            from news_archive.cli import main

            rc = main(["--db", str(db_path), "--json"])

        assert rc == 0
        assert summary_path.exists()
        body = summary_path.read_text(encoding="utf-8")
        assert "Enrich coverage board" in body
        assert "nyt_world" in body
        assert "stopped (backoff)" in body
        assert "display-window same-source max" in body
        assert "NEWS_SOURCE_CAP=6" in body
        assert "not the display gate" in body
        store = Store(db_path)
        assert store.get_enrich_backoff().get("nyt_world")
        store.close()


def test_nyt_alternate_urls_are_amp_then_mobile():
    url = "https://www.nytimes.com/2026/10/16/world/story-0.html"
    alts = alternate_urls_for(url=url, source="nyt_world")
    assert MAX_ALTERNATES_PER_ARTICLE == 2
    assert alts == [
        "https://www.nytimes.com/2026/10/16/world/story-0.amp.html",
        "https://mobile.nytimes.com/2026/10/16/world/story-0.html",
    ]
    assert url not in alts
    # Host fallback when source id is missing.
    assert alternate_urls_for(url=url, source="unknown") == alts
    already_amp = "https://www.nytimes.com/2026/10/16/world/story-0.amp.html"
    amp_alts = alternate_urls_for(url=already_amp, source="nyt_world")
    assert already_amp not in amp_alts
    assert amp_alts == ["https://mobile.nytimes.com/2026/10/16/world/story-0.amp.html"]


def test_ftchinese_alternate_urls_are_mobile_then_amp():
    url = "https://www.ftchinese.com/story/001104123"
    alts = alternate_urls_for(url=url, source="ftchinese")
    assert alts == [
        "https://m.ftchinese.com/story/001104123",
        "https://www.ftchinese.com/amp/story/001104123",
    ]
    assert url not in alts
    assert len(alts) <= MAX_ALTERNATES_PER_ARTICLE
    mobile = "https://m.ftchinese.com/story/001104123"
    assert alternate_urls_for(url=mobile, source="ftchinese") == [
        "https://m.ftchinese.com/amp/story/001104123",
    ]


def test_unknown_source_has_no_alternates():
    url = "https://finance.people.com.cn/n1/2026/1015/c1004-40399999.html"
    assert alternate_urls_for(url=url, source="people_finance") == []
    assert alternate_urls_for(url=url, source="unknown") == []
    assert alternate_urls_for(url="https://example.com/story", source="36kr") == []


def test_nyt_primary_403_alternate_succeeds_stores_snapshot():
    """Primary 403 → AMP 200 → private snapshot stored; public JSON omits it."""
    url = "https://www.nytimes.com/2026/10/16/world/story-alt.html"
    amp = "https://www.nytimes.com/2026/10/16/world/story-alt.amp.html"
    mobile = "https://mobile.nytimes.com/2026/10/16/world/story-alt.html"
    assert alternate_urls_for(url=url, source="nyt_world") == [amp, mobile]
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(url, title="World story", summary=_long_summary(), source="nyt_world")
        )
        client = _RecordingClient(
            {
                url: _FakeResponse(403, "Forbidden"),
                amp: _FakeResponse(200, PEOPLE_HTML),
                mobile: _FakeResponse(200, PEOPLE_HTML),
            }
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        assert client.calls == [url, amp]
        assert mobile not in client.calls
        assert stats["fetched"] == 1
        assert stats["soft_failed"] == 0
        assert stats["by_source"]["nyt_world"]["success"] == 1
        assert stats["by_source"]["nyt_world"]["stopped"] is False
        assert stats["http_used"] == 2
        assert not store.get_enrich_backoff()

        row = store.get_article(url)
        assert row is not None
        snapshot = row["content_snapshot"]
        assert snapshot
        assert "央行发布三季度金融统计数据" in snapshot
        assert is_usable_snapshot(snapshot)

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "content_snapshot" not in exported[0]
        assert "央行发布三季度金融统计数据" not in raw
        assert len(exported[0]["summary"]) <= PUBLIC_SUMMARY_MAX
        store.close()


def test_ftchinese_empty_body_alternate_succeeds_stores_snapshot():
    """Desktop 200 + empty body → m.ftchinese.com body stored under original URL."""
    url = "https://www.ftchinese.com/story/001104999"
    mobile = "https://m.ftchinese.com/story/001104999"
    amp = "https://www.ftchinese.com/amp/story/001104999"
    assert alternate_urls_for(url=url, source="ftchinese") == [mobile, amp]
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(url, title="FT稿", summary=None, source="ftchinese"))
        client = _RecordingClient(
            {
                url: _FakeResponse(200, "   "),
                mobile: _FakeResponse(200, PEOPLE_HTML),
            }
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        assert client.calls == [url, mobile]
        assert amp not in client.calls
        assert stats["fetched"] == 1
        assert stats["soft_failed"] == 0
        row = store.get_article(url)
        assert row is not None
        assert is_usable_snapshot(row["content_snapshot"])
        assert "央行发布三季度金融统计数据" in row["content_snapshot"]
        summary = row["summary"]
        assert summary
        assert MIN_USABLE_SUMMARY <= len(html_to_text(summary)) <= PUBLIC_SUMMARY_MAX

        out_path = Path(tmpdir) / "articles.json"
        exported = _export_articles_json(db_path, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "content_snapshot" not in exported[0]
        store.close()


def test_all_alternates_fail_counts_one_backoff_per_article():
    """Primary+alts all 403 → one streak hit per article; 3 articles trip backoff."""
    nyt_urls = _nyt_urls(4)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        for url in nyt_urls:
            store.upsert(_article(url, summary=_long_summary(), source="nyt_world"))
        client = _RecordingClient(
            {url: _FakeResponse(403, "Forbidden") for url in nyt_urls}
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)

        per_article = _http_for_article(nyt_urls[0], "nyt_world")
        assert per_article == 1 + MAX_ALTERNATES_PER_ARTICLE
        assert stats["soft_failed"] == CONSECUTIVE_FAIL_LIMIT
        assert stats["http_used"] == CONSECUTIVE_FAIL_LIMIT * per_article
        assert stats["by_source"]["nyt_world"]["stopped"] is True
        assert stats["by_source"]["nyt_world"]["soft_fail"] == CONSECUTIVE_FAIL_LIMIT
        # Fourth article never enqueued.
        assert nyt_urls[3] not in client.calls
        assert store.get_enrich_backoff().get("nyt_world")
        for url in nyt_urls:
            assert not store.get_article(url)["content_snapshot"]
        store.close()


def test_alternates_stop_when_http_budget_exhausted():
    """Do not burn remaining budget on a third GET for one article when max_http=2."""
    url_a = "https://www.nytimes.com/2026/10/16/world/story-a.html"
    url_b = "https://www.nytimes.com/2026/10/16/world/story-b.html"
    amp_a = "https://www.nytimes.com/2026/10/16/world/story-a.amp.html"
    mobile_a = "https://mobile.nytimes.com/2026/10/16/world/story-a.html"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(_article(url_a, summary=_long_summary(), source="nyt_world"))
        store.upsert(_article(url_b, summary=_long_summary(), source="nyt_world"))
        client = _RecordingClient(
            {
                url_a: _FakeResponse(403, "no"),
                amp_a: _FakeResponse(403, "no"),
                mobile_a: _FakeResponse(200, PEOPLE_HTML),
                url_b: _FakeResponse(200, PEOPLE_HTML),
            }
        )
        stats = enrich_store(
            store, client=client, sleep_fn=lambda _s: None, max_http=2
        )
        assert client.calls == [url_a, amp_a]
        assert mobile_a not in client.calls
        assert url_b not in client.calls
        assert stats["http_used"] == 2
        assert stats["soft_failed"] == 1
        assert stats["fetched"] == 0
        assert not store.get_article(url_a)["content_snapshot"]
        assert not store.get_article(url_b)["content_snapshot"]
        store.close()


if __name__ == "__main__":
    test_html_to_text_strips_people_cn_chrome()
    test_needs_summary_fill_triggers()
    test_is_usable_snapshot_rejects_empty_and_shell()
    test_should_fetch_page_archive_first()
    test_people_cn_empty_summary_enrich_writes_snapshot_and_public_summary()
    test_long_summary_missing_snapshot_writes_snapshot_hides_from_public_json()
    test_usable_snapshot_second_run_does_not_http()
    test_public_json_sweep_omits_content_snapshot_and_caps_summary()
    test_simulated_403_soft_fails_row_but_fetch_job_stays_green()
    test_existing_snapshot_derives_summary_without_http()
    test_export_caps_long_summary_at_280_and_omits_snapshot()
    test_gone_and_timeout_do_not_write_snapshot()
    test_max_http_stockpiles_across_runs()
    test_derive_public_summary_prefers_snapshot()
    test_cli_enrich_exception_does_not_fail_job()
    test_nyt_three_403s_stops_source_others_still_fetch()
    test_backoff_cooldown_persists_six_hours_then_expires()
    test_http_budget_stays_at_40_when_nyt_would_burn_it()
    test_mixed_403_429_timeout_trips_backoff()
    test_job_summary_coverage_board_omits_snapshot_body()
    test_job_summary_primary_source_max_is_display_window_not_raw()
    test_cli_writes_job_summary_and_stays_green_on_nyt_backoff()
    test_nyt_alternate_urls_are_amp_then_mobile()
    test_ftchinese_alternate_urls_are_mobile_then_amp()
    test_unknown_source_has_no_alternates()
    test_nyt_primary_403_alternate_succeeds_stores_snapshot()
    test_ftchinese_empty_body_alternate_succeeds_stores_snapshot()
    test_all_alternates_fail_counts_one_backoff_per_article()
    test_alternates_stop_when_http_budget_exhausted()
    print("✓ All enrich tests passed")
