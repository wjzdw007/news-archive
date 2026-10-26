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
        # Sorted by published_at desc (both have published_at here)
        assert exported[0]["url"] == "https://example.com/1"
        assert exported[1]["url"] == "https://example.com/2"
        assert exported[0]["status"] == "active"
        assert exported[1]["status"] == "gone"
        for item in exported:
            assert "content_snapshot" not in item
        
        store.close()


def test_article_list_time_prefers_published_at():
    """List SORT / display time: published_at, else fetched_at (null/empty)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import article_list_time

    fetched = "2026-10-15T12:00:00Z"
    published = "2024-01-01T08:00:00Z"
    assert article_list_time({"published_at": published, "fetched_at": fetched}) == published
    assert article_list_time({"published_at": None, "fetched_at": fetched}) == fetched
    assert article_list_time({"published_at": "", "fetched_at": fetched}) == fetched
    assert article_list_time({"published_at": "   ", "fetched_at": fetched}) == fetched


def test_export_articles_sorts_by_published_at_fallback_fetched_at():
    """Late-fetched old articles must not sort above newer published_at.

    Fixture:
      late-old   published 2024-01-01, fetched 2026-10-15  -> sort key 2024-01-01
      recent     published 2026-10-10, fetched 2026-10-11  -> sort key 2026-10-10
      no-pub     published None,       fetched 2026-10-12  -> sort key 2026-10-12
      empty-pub  published "",         fetched 2026-10-08  -> sort key 2026-10-08

    Expected desc: no-pub, recent, empty-pub, late-old
    (fetched_at desc would have put late-old first.)
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import article_list_time, export_articles

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        fixtures = [
            Article(
                url="https://example.com/late-old",
                title="Old article fetched late",
                published_at="2024-01-01T08:00:00Z",
                summary="old",
                source="test_source",
                fetched_at="2026-10-15T12:00:00Z",
                content_snapshot="must not appear",
                status="active",
            ),
            Article(
                url="https://example.com/recent",
                title="Recently published",
                published_at="2026-10-10T09:00:00Z",
                summary="recent",
                source="test_source",
                fetched_at="2026-10-11T09:00:00Z",
                content_snapshot="must not appear",
                status="active",
            ),
            Article(
                url="https://example.com/no-pub",
                title="Missing published_at",
                published_at=None,
                summary="no pub",
                source="test_source",
                fetched_at="2026-10-12T09:00:00Z",
                content_snapshot="must not appear",
                status="active",
            ),
            Article(
                url="https://example.com/empty-pub",
                title="Empty published_at",
                published_at="",
                summary="empty pub",
                source="test_source",
                fetched_at="2026-10-08T09:00:00Z",
                content_snapshot="must not appear",
                status="active",
            ),
        ]
        for article in fixtures:
            store.upsert(article)

        output_path = Path(tmpdir) / "articles.json"
        conn = sqlite3.connect(db_path)
        count = export_articles(conn, output_path)
        conn.close()

        assert count == 4
        exported = json.loads(output_path.read_text(encoding="utf-8"))
        urls = [item["url"] for item in exported]
        assert urls == [
            "https://example.com/no-pub",
            "https://example.com/recent",
            "https://example.com/empty-pub",
            "https://example.com/late-old",
        ]
        assert urls[0] != "https://example.com/late-old"

        keys = [article_list_time(item) for item in exported]
        assert keys == [
            "2026-10-12T09:00:00Z",
            "2026-10-10T09:00:00Z",
            "2026-10-08T09:00:00Z",
            "2024-01-01T08:00:00Z",
        ]
        assert keys == sorted(keys, reverse=True)
        for item in exported:
            assert "content_snapshot" not in item

        store.close()


def test_news_list_viewer_uses_published_at_helper():
    """Viewer list (not only detail) must use the published_at fallback helper."""
    app_js = (Path(__file__).parent.parent / "site" / "app.js").read_text(encoding="utf-8")
    assert "function articleListTime(article)" in app_js
    assert "formatDate(articleListTime(article))" in app_js
    assert "article.fetched_at);" not in app_js
    # X tab stays on posted_at with fetched_at fallback
    assert "formatDate(post.posted_at || post.fetched_at)" in app_js


def test_js_viewer_sorts_by_published_at_fallback_fetched_at():
    """Execute the viewer helpers against the late-fetch fixture."""
    import shutil
    import subprocess

    if not shutil.which("node"):
        raise AssertionError("node is required to execute the viewer list-time helpers")

    app_js = (Path(__file__).parent.parent / "site" / "app.js").read_text(encoding="utf-8")
    start = app_js.index("function articleListTime")
    end = app_js.index("// Render news list")
    helpers = app_js[start:end]
    script = (
        helpers
        + """
const items = [
  {url:'late-old', published_at:'2024-01-01T08:00:00Z', fetched_at:'2026-10-15T12:00:00Z'},
  {url:'recent', published_at:'2026-10-10T09:00:00Z', fetched_at:'2026-10-11T09:00:00Z'},
  {url:'no-pub', published_at:null, fetched_at:'2026-10-12T09:00:00Z'},
  {url:'empty-pub', published_at:'', fetched_at:'2026-10-08T09:00:00Z'},
];
const sorted = [...items].sort(compareArticleListTimeDesc);
console.log(JSON.stringify({
  urls: sorted.map(i => i.url),
  times: sorted.map(articleListTime),
}));
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["urls"] == ["no-pub", "recent", "empty-pub", "late-old"]
    assert payload["times"] == [
        "2026-10-12T09:00:00Z",
        "2026-10-10T09:00:00Z",
        "2026-10-08T09:00:00Z",
        "2024-01-01T08:00:00Z",
    ]
    assert payload["urls"][0] != "late-old"


def test_export_articles_omits_content_snapshot():
    """Public JSON must not include RSS content_snapshot keys."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        store.upsert(
            Article(
                url="https://example.com/secret",
                title="Guardian piece",
                published_at="2024-01-01T10:00:00Z",
                summary="<p>Visible summary.</p>",
                source="guardian",
                fetched_at="2024-01-01T12:00:00Z",
                content_snapshot="<p>FULL TEXT that must never ship to Pages.</p>",
                status="active",
            )
        )

        output_path = Path(tmpdir) / "articles.json"
        conn = sqlite3.connect(db_path)
        export_articles(conn, output_path)
        conn.close()

        raw = output_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "FULL TEXT that must never ship to Pages" not in raw

        exported = json.loads(raw)
        assert len(exported) == 1
        assert "content_snapshot" not in exported[0]
        assert exported[0]["summary"] == "Visible summary."

        store.close()


def test_export_articles_strips_html_from_summary():
    """Guardian-style <p> tags must not appear in exported summaries."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles, strip_html

    assert strip_html("<p>Police arrested a reporter.</p><p>More.</p>") == (
        "Police arrested a reporter. More."
    )
    assert strip_html("&lt;p&gt;Escaped tags&lt;/p&gt;") == "Escaped tags"
    assert strip_html("  ") is None

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        store.upsert(
            Article(
                url="https://theguardian.com/world/1",
                title="Arrest",
                published_at="2024-01-01T10:00:00Z",
                summary=(
                    "<p>FSB said reporter was arrested on Sakhalin.</p>"
                    "<p>Continue reading.</p>"
                ),
                source="guardian",
                fetched_at="2024-01-01T12:00:00Z",
                content_snapshot="<p>Long body.</p>",
                status="active",
            )
        )

        output_path = Path(tmpdir) / "articles.json"
        conn = sqlite3.connect(db_path)
        export_articles(conn, output_path)
        conn.close()

        exported = json.loads(output_path.read_text(encoding="utf-8"))
        summary = exported[0]["summary"]
        assert "<p>" not in summary
        assert "</p>" not in summary
        assert "FSB said reporter was arrested on Sakhalin." in summary
        assert "content_snapshot" not in exported[0]
        assert len(summary) <= 280

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
        # Should be sorted by posted_at desc (identified by public display fields)
        assert exported[0]["url"] == "https://x.com/testuser/status/123"
        assert exported[1]["url"] == "https://x.com/testuser/status/456"
        assert exported[0]["status"] == "active"
        assert exported[1]["status"] == "gone"
        for item in exported:
            assert set(item) == {
                "author",
                "posted_at",
                "fetched_at",
                "text_snapshot",
                "url",
                "status",
            }
            assert "post_id" not in item
        
        x_store.close()


def test_export_x_posts_omits_secrets_and_post_id():
    """x_posts.json must stay display-only even if secret columns exist."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_x_posts

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        x_store = XStore(db_path)
        x_store.upsert(
            XPost(
                post_id="secret-id-999",
                author="reuters",
                url="https://x.com/reuters/status/999",
                text_snapshot="Market update",
                posted_at="2024-01-01T10:00:00Z",
                fetched_at="2024-01-01T11:00:00Z",
                status="gone",
            )
        )
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            ALTER TABLE x_posts ADD COLUMN cookie TEXT;
            ALTER TABLE x_posts ADD COLUMN authorization TEXT;
            ALTER TABLE x_posts ADD COLUMN headers TEXT;
            UPDATE x_posts SET
                cookie = 'auth_token=LEAK',
                authorization = 'Bearer LEAK',
                headers = '{"Cookie":"LEAK"}';
            """
        )
        conn.commit()

        output_path = Path(tmpdir) / "x_posts.json"
        export_x_posts(conn, output_path)
        conn.close()

        raw = output_path.read_text(encoding="utf-8")
        for forbidden in (
            "post_id",
            "secret-id-999",
            "cookie",
            "Cookie",
            "authorization",
            "Authorization",
            "headers",
            "auth_token",
            "Bearer",
            "LEAK",
        ):
            assert forbidden not in raw

        exported = json.loads(raw)
        assert exported[0] == {
            "author": "reuters",
            "posted_at": "2024-01-01T10:00:00Z",
            "fetched_at": "2024-01-01T11:00:00Z",
            "text_snapshot": "Market update",
            "url": "https://x.com/reuters/status/999",
            "status": "gone",
        }

        x_store.close()


def test_export_empty_files():
    """Test empty file generation when DB missing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_empty_files
    
    with tempfile.TemporaryDirectory() as tmpdir:
        site_data_dir = Path(tmpdir) / "site" / "data"
        export_empty_files(site_data_dir)
        
        for filename in ["articles.json", "x_posts.json", "daily_briefs.json"]:
            filepath = site_data_dir / filename
            assert filepath.exists()
            with filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)
            assert data == []

        topics = json.loads((site_data_dir / "topics.json").read_text(encoding="utf-8"))
        assert topics[0]["topic_id"] == "tech-ai"
        assert topics[0]["status"] == "ok"
        assert topics[0]["title"] == "科技/AI"

        tech_ai_raw = (site_data_dir / "tech_ai.json").read_text(encoding="utf-8")
        assert "content_snapshot" not in tech_ai_raw
        assert "post_id" not in tech_ai_raw
        tech_ai = json.loads(tech_ai_raw)
        assert tech_ai["topic_id"] == "tech-ai"
        assert tech_ai["items"] == []


def test_export_daily_briefs():
    """Export ok/failed/empty rows; omit internal error and content_snapshot."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_daily_briefs

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        store.upsert_daily_brief(
            {
                "date": "2026-10-15",
                "generated_at": "2026-10-15T12:00:00+00:00",
                "status": "ok",
                "model": "deepseek/deepseek-flash",
                "lede": "多源关注航天发射。",
                "sections": [
                    {
                        "topic_id": "t1",
                        "title": "航天发射",
                        "bullets": ["发射按计划完成。"],
                        "links": [
                            {
                                "title": "发射成功",
                                "url": "https://example.com/1",
                                "source": "36kr",
                            }
                        ],
                    }
                ],
                "error": None,
            }
        )
        store.upsert_daily_brief(
            {
                "date": "2026-10-14",
                "generated_at": "2026-10-14T12:00:00+00:00",
                "status": "failed",
                "model": "",
                "lede": "",
                "sections": [],
                "error": "missing DAILY_BRIEF_API_KEY or DAILY_BRIEF_API_BASE",
            }
        )
        store.upsert_daily_brief(
            {
                "date": "2026-10-13",
                "generated_at": "2026-10-13T12:00:00+00:00",
                "status": "empty",
                "model": "",
                "lede": "",
                "sections": [],
            }
        )
        output_path = Path(tmpdir) / "daily_briefs.json"
        conn = sqlite3.connect(db_path)
        count = export_daily_briefs(conn, output_path)
        conn.close()
        assert count == 3
        exported = json.loads(output_path.read_text(encoding="utf-8"))
        assert [row["date"] for row in exported] == [
            "2026-10-15",
            "2026-10-14",
            "2026-10-13",
        ]
        assert exported[0]["status"] == "ok"
        assert exported[1]["status"] == "failed"
        assert exported[2]["status"] == "empty"
        for row in exported:
            assert set(row) == {
                "date",
                "generated_at",
                "status",
                "model",
                "lede",
                "sections",
            }
            assert "content_snapshot" not in row
            assert "error" not in row
        store.close()


def test_export_daily_briefs_omits_content_snapshot_and_error():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_articles, export_daily_briefs

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        store.upsert(
            Article(
                url="https://example.com/secret",
                title="Guardian piece",
                published_at="2026-10-15T10:00:00Z",
                summary="Visible summary.",
                source="guardian",
                fetched_at="2026-10-15T12:00:00Z",
                content_snapshot="<p>FULL TEXT that must never ship to Pages.</p>",
                status="active",
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
                        "bullets": ["Visible summary."],
                        "links": [
                            {
                                "title": "Guardian piece",
                                "url": "https://example.com/secret",
                                "source": "guardian",
                            }
                        ],
                    }
                ],
                "error": "internal: Bearer LEAK",
            }
        )
        conn = sqlite3.connect(db_path)
        articles_path = Path(tmpdir) / "articles.json"
        briefs_path = Path(tmpdir) / "daily_briefs.json"
        export_articles(conn, articles_path)
        export_daily_briefs(conn, briefs_path)
        conn.close()

        articles_raw = articles_path.read_text(encoding="utf-8")
        briefs_raw = briefs_path.read_text(encoding="utf-8")
        for raw in (articles_raw, briefs_raw):
            assert "content_snapshot" not in raw
            assert "FULL TEXT that must never ship to Pages" not in raw
        assert "Bearer LEAK" not in briefs_raw
        assert "error" not in json.loads(briefs_raw)[0]
        store.close()


def test_export_daily_briefs_x_section_omits_post_id_and_secrets():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_daily_briefs, export_x_posts

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        x_store = XStore(db_path)
        x_store.upsert(
            XPost(
                post_id="secret-post-id",
                author="FT",
                url="https://x.com/FT/status/1",
                text_snapshot="Markets rose.",
                posted_at="2026-10-14T16:30:00Z",
                fetched_at="2026-10-15T03:00:00Z",
                status="active",
            )
        )
        x_store.close()
        store.upsert_daily_brief(
            {
                "date": "2026-10-15",
                "generated_at": "2026-10-15T12:00:00+00:00",
                "status": "ok",
                "model": "deepseek/deepseek-flash",
                "lede": "外媒账号关注市场。",
                "sections": [
                    {
                        "topic_id": "t1",
                        "title": "航天发射",
                        "bullets": ["发射按计划完成。"],
                        "links": [
                            {
                                "title": "发射成功",
                                "url": "https://example.com/1",
                                "source": "36kr",
                            }
                        ],
                    },
                    {
                        "topic_id": "x-daily",
                        "title": "X 动态",
                        "bullets": ["FT 账号提到市场定价。"],
                        "links": [
                            {
                                "title": "Markets rose.",
                                "url": "https://x.com/FT/status/1",
                                "source": "FT",
                            }
                        ],
                    },
                ],
                "error": None,
            }
        )
        conn = sqlite3.connect(db_path)
        briefs_path = Path(tmpdir) / "daily_briefs.json"
        posts_path = Path(tmpdir) / "x_posts.json"
        export_daily_briefs(conn, briefs_path)
        export_x_posts(conn, posts_path)
        conn.close()
        briefs_raw = briefs_path.read_text(encoding="utf-8")
        posts_raw = posts_path.read_text(encoding="utf-8")
        for raw in (briefs_raw, posts_raw):
            assert "post_id" not in raw
            assert "secret-post-id" not in raw
            assert "cookie" not in raw.lower()
            assert "authorization" not in raw.lower()
            assert "content_snapshot" not in raw
        exported = json.loads(briefs_raw)
        titles = [s["title"] for s in exported[0]["sections"]]
        assert "航天发射" in titles
        assert "X 动态" in titles
        store.close()


def test_export_tech_ai_merges_and_omits_secrets():
    """tech_ai.json is RSS∪X, whitelist-only, no content_snapshot / post_id."""
    import sys
    from datetime import datetime, timedelta, timezone

    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_tech_ai, prepend_tech_ai_topic

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=1)).isoformat()
    fetched = now.isoformat()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        store.upsert(
            Article(
                url="https://www.wired.com/ai",
                title="WIRED covers OpenAI",
                published_at=recent,
                summary="On-topic tech.",
                source="wired",
                fetched_at=fetched,
                content_snapshot="FULL TEXT that must never ship to Pages.",
                status="active",
            )
        )
        store.upsert(
            Article(
                url="https://www.bbc.com/world/1",
                title="OpenAI hearing",
                published_at=recent,
                summary="AI keyword but source not whitelisted.",
                source="bbc_world",
                fetched_at=fetched,
                content_snapshot="nope",
                status="active",
            )
        )
        x_store = XStore(db_path)
        x_store.upsert(
            XPost(
                post_id="secret-id-ai",
                author="OpenAI",
                url="https://x.com/OpenAI/status/1",
                text_snapshot="Shipping a model",
                posted_at=recent,
                fetched_at=fetched,
                status="active",
            )
        )
        x_store.close()

        conn = sqlite3.connect(db_path)
        output_path = Path(tmpdir) / "tech_ai.json"
        payload = export_tech_ai(conn, output_path)
        topics_path = Path(tmpdir) / "topics.json"
        topics_path.write_text("[]", encoding="utf-8")
        prepend_tech_ai_topic(topics_path, payload)
        conn.close()

        raw = output_path.read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
        assert "FULL TEXT that must never ship to Pages" not in raw
        assert "post_id" not in raw
        assert "secret-id-ai" not in raw
        assert payload["title"] == "科技/AI"
        urls = [item["url"] for item in payload["items"]]
        assert "https://www.wired.com/ai" in urls
        assert "https://x.com/OpenAI/status/1" in urls
        assert "https://www.bbc.com/world/1" not in urls
        topics = json.loads(topics_path.read_text(encoding="utf-8"))
        assert topics[0]["topic_id"] == "tech-ai"
        store.close()


def test_export_daily_briefs_missing_table_soft_fail():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from export_site_data import export_daily_briefs

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "old.db"
        conn = sqlite3.connect(db_path)
        output_path = Path(tmpdir) / "daily_briefs.json"
        count = export_daily_briefs(conn, output_path)
        conn.close()
        assert count == 0
        assert json.loads(output_path.read_text(encoding="utf-8")) == []


if __name__ == "__main__":
    test_export_articles()
    test_article_list_time_prefers_published_at()
    test_export_articles_sorts_by_published_at_fallback_fetched_at()
    test_news_list_viewer_uses_published_at_helper()
    test_js_viewer_sorts_by_published_at_fallback_fetched_at()
    test_export_articles_omits_content_snapshot()
    test_export_articles_strips_html_from_summary()
    test_export_topics()
    test_export_x_posts()
    test_export_x_posts_omits_secrets_and_post_id()
    test_export_empty_files()
    test_export_tech_ai_merges_and_omits_secrets()
    test_export_daily_briefs()
    test_export_daily_briefs_omits_content_snapshot_and_error()
    test_export_daily_briefs_x_section_omits_post_id_and_secrets()
    test_export_daily_briefs_missing_table_soft_fail()
    print("✓ All site export tests passed")
