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

from news_archive.enrich import (
    MIN_USABLE_SUMMARY,
    PUBLIC_SUMMARY_MAX,
    derive_public_summary,
    enrich_store,
    html_to_text,
    is_usable_snapshot,
    needs_summary_fill,
    should_fetch_page,
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
        item = self.mapping[url]
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
) -> Article:
    return Article(
        url=url,
        title=title,
        published_at="2026-10-15T08:00:00Z",
        summary=summary,
        source=source,
        fetched_at="2026-10-15T10:00:00Z",
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
        store.upsert(_article(PAYWALL_URL, title="付费墙稿", summary="", source="ftchinese"))
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
            PAYWALL_URL, title="付费墙稿", summary="", source="ftchinese"
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
    print("✓ All enrich tests passed")
