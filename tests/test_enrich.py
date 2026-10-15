"""Product gates for thin-RSS page enrichment.

1. Empty-summary people.cn fixture → DB snapshot + public summary 80–280
2. Full public JSON sweep: no content_snapshot key
3. Simulated 403/paywall → that row soft-fails; overall fetch still green
4. Long existing summary → no enrich HTTP call
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


def test_should_fetch_page_skips():
    thin = {"url": PEOPLE_URL, "summary": "", "content_snapshot": None, "status": "active"}
    assert should_fetch_page(thin)
    assert not should_fetch_page({**thin, "status": "gone"})
    assert not should_fetch_page({**thin, "url": "ftp://people.com.cn/x"})
    assert not should_fetch_page({**thin, "url": "not-a-url"})
    assert not should_fetch_page({**thin, "summary": "乙" * 80})
    assert not should_fetch_page({**thin, "content_snapshot": "丙" * 80})


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


def test_public_json_sweep_omits_content_snapshot_key():
    """Full public JSON sweep: no content_snapshot key in any Pages export."""
    secret = "PRIVATE_SNAPSHOT_BODY_MUST_NEVER_SHIP"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "archive.sqlite3"
        store = Store(db_path)
        store.upsert(
            _article(
                PEOPLE_URL,
                title="央行",
                summary="可见摘要。" * 10,
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

        app_js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        assert "article.content_snapshot" not in app_js
        assert "articles.json" in (ROOT / "site" / "app.js").read_text(encoding="utf-8")


def test_simulated_403_soft_fails_row_but_fetch_job_stays_green():
    """403/paywall on one URL: that row unchanged; CLI fetch still exit 0."""
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


def test_long_existing_summary_skips_http():
    """Already-qualified summary (≥80) must not trigger an enrich HTTP call."""
    long_summary = (
        "联合国安理会今日就地区局势举行紧急会议，多国代表呼吁保持克制并恢复对话，"
        "同时强调人道救援通道必须保持畅通，避免冲突进一步外溢到周边国家与全球市场。"
        "分析人士认为，后续仍需观察各方表态与实地停火安排能否落实。"
    )
    assert len(html_to_text(long_summary)) >= MIN_USABLE_SUMMARY

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
        client = _RecordingClient(
            {LONG_SUMMARY_URL: _FakeResponse(200, "<p>SHOULD NOT BE FETCHED</p>")}
        )
        stats = enrich_store(store, client=client, sleep_fn=lambda _s: None)
        assert client.calls == []
        assert stats["skipped"] >= 1
        assert stats["fetched"] == 0
        row = store.get_article(LONG_SUMMARY_URL)
        assert row is not None
        assert row["summary"] == long_summary
        assert row["content_snapshot"] is None
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
    test_should_fetch_page_skips()
    test_people_cn_empty_summary_enrich_writes_snapshot_and_public_summary()
    test_public_json_sweep_omits_content_snapshot_key()
    test_simulated_403_soft_fails_row_but_fetch_job_stays_green()
    test_long_existing_summary_skips_http()
    test_existing_snapshot_derives_summary_without_http()
    test_export_caps_long_summary_at_280_and_omits_snapshot()
    test_gone_and_timeout_do_not_write_snapshot()
    test_derive_public_summary_prefers_snapshot()
    test_cli_enrich_exception_does_not_fail_job()
    print("✓ All enrich tests passed")
