"""Daily brief generation: Shanghai day, topic grouping, soft-fail, no snapshot."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_archive.daily_brief import generate_for_dates
from news_archive.daily_brief import main as daily_brief_main
from news_archive.daily_briefs import (
    API_BASE_ENV,
    API_KEY_ENV,
    DAILY_BRIEF_ARTICLE_FIELDS,
    DAILY_BRIEF_X_FIELDS,
    DEFAULT_MODEL,
    MODEL_ENV,
    OTHER_TITLE,
    SECTIONS_MAX,
    X_LINKS_MAX,
    X_SECTION_TITLE,
    X_SECTION_TOPIC_ID,
    X_TEXT_SNAPSHOT_MAX,
    articles_for_day,
    daily_brief_fingerprint_input,
    day_input_fingerprint,
    generate_daily_brief,
    group_sections,
    input_fingerprint,
    redact_secrets,
    resolve_llm_config,
    resolve_model,
    shanghai_calendar_date,
    x_posts_for_day,
)
from news_archive.schema import Article
from news_archive.store import Store
from news_archive.x_store import XPost, XStore

ROOT = Path(__file__).parent.parent
SECRET_SNAPSHOT = "SECRET_SNAPSHOT_BODY_SHOULD_NEVER_LEAK"
SECRET_COOKIE = "SECRET_COOKIE_SHOULD_NEVER_LEAK"
SECRET_AUTH = "SECRET_AUTHORIZATION_SHOULD_NEVER_LEAK"
SECRET_POST_ID = "secret-post-id-should-never-leak"


def _art(**kwargs) -> dict:
    base = {
        "url": "https://example.com/1",
        "title": "SpaceX今日成功发射火星探测器",
        "published_at": "2026-10-15T02:00:00+00:00",
        "summary": "SpaceX今日成功发射火星探测器，任务按计划进行。",
        "source": "36kr",
        "fetched_at": "2026-10-15T03:00:00+00:00",
        "status": "active",
        "topic_id": "t-space",
        "content_snapshot": SECRET_SNAPSHOT,
    }
    base.update(kwargs)
    return base


def _x(**kwargs) -> dict:
    base = {
        "post_id": SECRET_POST_ID,
        "author": "FT",
        "text_snapshot": "Markets rose as traders priced in a rate pause.",
        "url": "https://x.com/FT/status/1",
        "posted_at": "2026-10-14T16:30:00Z",  # Shanghai 15th
        "fetched_at": "2026-10-15T03:00:00+00:00",
        "status": "active",
        "cookie": SECRET_COOKIE,
        "authorization": SECRET_AUTH,
        "headers": {"Authorization": SECRET_AUTH},
    }
    base.update(kwargs)
    return base


def _x_section_count(sections) -> int:
    return sum(1 for s in sections if s.get("title") == X_SECTION_TITLE)


def _ok_llm(grouped):
    first = grouped[0]
    return {
        "lede": "多源关注航天发射进展。",
        "sections": [
            {
                "topic_id": first.get("topic_id"),
                "title": first.get("title"),
                "bullets": ["发射按计划完成，地面站确认信号。"],
            }
        ],
    }


def test_shanghai_date_uses_calendar_not_utc():
    # 16:00 UTC = 00:00 next day in Asia/Shanghai
    assert shanghai_calendar_date(datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)) == "2026-10-15"
    assert shanghai_calendar_date(datetime(2026, 10, 14, 15, 59, tzinfo=timezone.utc)) == "2026-10-14"


def test_articles_for_day_published_at_fallback_fetched_at():
    articles = [
        _art(url="https://a/1", published_at="2026-10-14T16:30:00Z"),  # Shanghai 15th
        _art(
            url="https://a/2",
            published_at=None,
            fetched_at="2026-10-14T16:10:00Z",
            title="无发布时间稿",
        ),
        _art(
            url="https://a/3",
            published_at="",
            fetched_at="2026-10-14T10:00:00Z",
            title="仍是14日",
        ),
        _art(url="https://a/gone", status="gone", title="已失效"),
    ]
    day = articles_for_day(articles, "2026-10-15")
    urls = {a["url"] for a in day}
    assert urls == {"https://a/1", "https://a/2"}
    for row in day:
        assert set(row) == set(DAILY_BRIEF_ARTICLE_FIELDS)
        assert "content_snapshot" not in row
        assert SECRET_SNAPSHOT not in json.dumps(row, ensure_ascii=False)


def test_group_by_topic_and_single_other():
    articles = [
        _art(url="https://a/1", topic_id="t1", title="主题甲报道一"),
        _art(url="https://a/2", topic_id="t1", title="主题甲报道二", source="tmtpost"),
        _art(url="https://a/3", topic_id=None, title="散稿一足够长的标题"),
        _art(url="https://a/4", topic_id="", title="散稿二足够长的标题"),
    ]
    sections = group_sections(articles)
    titles = [s["title"] for s in sections]
    assert OTHER_TITLE in titles
    assert titles.count(OTHER_TITLE) == 1
    other = next(s for s in sections if s["title"] == OTHER_TITLE)
    assert other["topic_id"] is None
    assert len(other["links"]) == 2
    topic = next(s for s in sections if s["topic_id"] == "t1")
    assert {l["url"] for l in topic["links"]} == {"https://a/1", "https://a/2"}


def test_sections_cap_eight_with_other_last():
    articles = []
    for i in range(12):
        articles.append(
            _art(
                url=f"https://a/{i}",
                topic_id=f"t{i}",
                title=f"专题{i}标题足够长了",
                summary=f"专题{i}的摘要句子足够长了。",
            )
        )
    articles.append(_art(url="https://a/other", topic_id=None, title="未归类稿件标题足够长"))
    sections = group_sections(articles)
    assert len(sections) <= SECTIONS_MAX
    assert sections[-1]["title"] == OTHER_TITLE
    assert sections[-1]["topic_id"] is None
    assert sum(1 for s in sections if s["title"] == OTHER_TITLE) == 1


def test_empty_day_status_empty():
    brief = generate_daily_brief([], "2026-10-15", llm_fn=_ok_llm, model="gpt-4o-mini")
    assert brief["status"] == "empty"
    assert brief["lede"] == ""
    assert brief["sections"] == []


def test_missing_key_status_failed():
    brief = generate_daily_brief([_art()], "2026-10-15", missing_config=True)
    assert brief["status"] == "failed"
    assert brief["lede"] == ""
    assert brief["sections"] == []
    assert API_KEY_ENV in (brief.get("error") or "")
    assert API_BASE_ENV in (brief.get("error") or "")


def test_resolve_llm_config_requires_key_and_base():
    assert resolve_llm_config({}) is None
    assert resolve_llm_config({API_KEY_ENV: "sk-test"}) is None
    assert resolve_llm_config({API_BASE_ENV: "https://api.lkeap.cloud.tencent.com/plan/v3"}) is None
    cfg = resolve_llm_config(
        {
            API_KEY_ENV: "sk-test",
            API_BASE_ENV: "https://api.lkeap.cloud.tencent.com/plan/v3/",
        }
    )
    assert cfg is not None
    assert cfg["base_url"] == "https://api.lkeap.cloud.tencent.com/plan/v3"
    assert cfg["api_key"] == "sk-test"
    assert cfg["model"] == "deepseek/deepseek-flash"
    assert "openai.com" not in cfg["base_url"]


def test_resolve_model_defaults_and_env_override():
    assert DEFAULT_MODEL == "deepseek/deepseek-flash"
    assert resolve_model({}) == "deepseek/deepseek-flash"
    assert resolve_model({MODEL_ENV: "   "}) == "deepseek/deepseek-flash"
    assert resolve_model({MODEL_ENV: "  other/custom-id  "}) == "other/custom-id"
    cfg = resolve_llm_config(
        {
            API_KEY_ENV: "sk-test",
            API_BASE_ENV: "https://api.lkeap.cloud.tencent.com/plan/v3",
            MODEL_ENV: "custom/override",
        }
    )
    assert cfg is not None
    assert cfg["model"] == "custom/override"


def test_redact_secrets_never_keeps_values():
    planted = "sk-live-SHOULD-NOT-LEAK"
    text = redact_secrets(f"Bearer {planted} boom", planted)
    assert planted not in text
    assert "Bearer ***" in text


def test_model_error_status_failed():
    def boom(_grouped):
        raise RuntimeError("upstream 500")

    brief = generate_daily_brief(
        [_art()], "2026-10-15", llm_fn=boom, model="gpt-4o-mini"
    )
    assert brief["status"] == "failed"
    assert brief["lede"] == ""
    assert "500" in (brief.get("error") or "")


def test_ok_brief_records_default_model_when_unspecified():
    saved_env = _clear_brief_env()
    try:
        brief = generate_daily_brief([_art()], "2026-10-15", llm_fn=_ok_llm)
        assert brief["status"] == "ok"
        assert brief["model"] == "deepseek/deepseek-flash"
    finally:
        _restore_brief_env(saved_env)


def test_ok_brief_from_title_summary_only():
    captured = []

    def llm(grouped):
        captured.append(json.loads(json.dumps(grouped, ensure_ascii=False)))
        return _ok_llm(grouped)

    articles = [
        _art(),
        _art(
            url="https://example.com/2",
            title="SpaceX 发射成功",
            summary="报道称SpaceX完成发射。地面站工作正常。",
            source="tmtpost",
            content_snapshot=SECRET_SNAPSHOT,
        ),
        _art(
            url="https://example.com/3",
            title="一则未归类财经短讯足够长",
            summary="市场情绪平稳，指数小幅波动。",
            source="geekpark",
            topic_id=None,
            content_snapshot=SECRET_SNAPSHOT,
        ),
    ]
    brief = generate_daily_brief(
        articles, "2026-10-15", llm_fn=llm, model="gpt-4o-mini"
    )
    assert brief["status"] == "ok"
    assert 1 <= len(brief["lede"]) <= 80
    assert 1 <= len(brief["sections"]) <= 8
    blob = json.dumps(brief, ensure_ascii=False)
    assert "content_snapshot" not in blob
    assert SECRET_SNAPSHOT not in blob
    prompt_blob = json.dumps(captured, ensure_ascii=False)
    assert "content_snapshot" not in prompt_blob
    assert SECRET_SNAPSHOT not in prompt_blob
    for section in brief["sections"]:
        assert 1 <= len(section["bullets"]) <= 3
        assert 1 <= len(section["links"]) <= 5
        for link in section["links"]:
            assert set(link) == {"title", "url", "source"}
    assert any(s.get("topic_id") is None and s["title"] == OTHER_TITLE for s in brief["sections"])


def test_store_daily_brief_query_omits_snapshot():
    store_src = (ROOT / "src" / "news_archive" / "store.py").read_text(encoding="utf-8")
    start = store_src.index("def get_articles_for_daily_brief")
    end = store_src.index("\n    def ", start + 10)
    fn = store_src[start:end]
    select_list = fn[fn.index("SELECT"):fn.index("FROM")]
    assert "content_snapshot" not in select_list

    gen_src = (ROOT / "src" / "news_archive" / "daily_briefs.py").read_text(encoding="utf-8")
    assert '["content_snapshot"]' not in gen_src
    assert ".get(\"content_snapshot\")" not in gen_src

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        store.upsert(
            Article(
                title="T",
                published_at="2026-10-15T02:00:00+00:00",
                url="https://z.com/1",
                summary="visible summary",
                source="36kr",
                fetched_at="2026-10-15T03:00:00+00:00",
                content_snapshot=SECRET_SNAPSHOT,
                status="active",
                topic_id="t1",
            )
        )
        rows = store.get_articles_for_daily_brief()
        assert rows
        assert "content_snapshot" not in rows[0]
        assert SECRET_SNAPSHOT not in json.dumps(rows, ensure_ascii=False)
        brief = generate_daily_brief(
            rows, "2026-10-15", llm_fn=_ok_llm, model="gpt-4o-mini"
        )
        store.upsert_daily_brief(brief)
        saved = store.get_daily_brief("2026-10-15")
        assert saved["status"] == "ok"
        store.close()


def _seed_x_post(store: Store, **kwargs) -> None:
    payload = {
        "post_id": "ft-1",
        "author": "FT",
        "url": "https://x.com/FT/status/1",
        "text_snapshot": "Markets rose as traders priced in a rate pause.",
        "posted_at": "2026-10-14T16:30:00Z",
        "fetched_at": "2026-10-15T03:00:00+00:00",
        "status": "active",
    }
    payload.update(kwargs)
    x_store = XStore(store.db_path)
    x_store.upsert(XPost(**payload))
    x_store.close()


def _seed_article(store: Store, **kwargs) -> None:
    payload = {
        "title": "SpaceX今日成功发射火星探测器",
        "published_at": "2026-10-15T02:00:00+00:00",
        "url": "https://example.com/1",
        "summary": "SpaceX今日成功发射火星探测器，任务按计划进行。",
        "source": "36kr",
        "fetched_at": "2026-10-15T03:00:00+00:00",
        "content_snapshot": SECRET_SNAPSHOT,
        "status": "active",
        "topic_id": "t-space",
    }
    payload.update(kwargs)
    store.upsert(Article(**payload))


def _counting_llm():
    calls = {"n": 0}

    def llm(grouped):
        calls["n"] += 1
        return _ok_llm(grouped)

    return llm, calls


def test_input_fingerprint_stable_sorted_by_url():
    a = [
        _art(url="https://b.com/1", title="B稿", source="tmtpost"),
        _art(url="https://a.com/1", title="A稿", source="36kr"),
    ]
    b = list(reversed(a))
    assert input_fingerprint(a) == input_fingerprint(b)
    edited = [
        _art(url="https://b.com/1", title="B稿改标题", source="tmtpost"),
        _art(url="https://a.com/1", title="A稿", source="36kr"),
    ]
    assert input_fingerprint(a) != input_fingerprint(edited)


def test_ok_same_fingerprint_kept_ok_skips_llm():
    llm, calls = _counting_llm()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        _seed_article(store)
        first = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert first[0]["action"] == "inserted"
        assert first[0]["status"] == "ok"
        assert calls["n"] == 1
        saved = store.get_daily_brief("2026-10-15")
        assert saved["status"] == "ok"
        assert saved["input_fingerprint"] == input_fingerprint(
            articles_for_day(store.get_articles_for_daily_brief(), "2026-10-15")
        )
        second = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert second[0]["action"] == "kept_ok"
        assert second[0]["status"] == "ok"
        assert calls["n"] == 1
        store.close()


def test_ok_unchanged_rss_changed_x_updates_stable_x_kept_ok():
    """Unchanged RSS+X → kept_ok; same-day X add/edit → updated."""
    llm, calls = _counting_llm()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        _seed_article(store)
        _seed_x_post(store)
        first = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert first[0]["action"] == "inserted"
        assert first[0]["status"] == "ok"
        assert calls["n"] == 1
        saved = store.get_daily_brief("2026-10-15")
        assert saved["input_fingerprint"] == day_input_fingerprint(
            store.get_articles_for_daily_brief(),
            "2026-10-15",
            store.get_x_posts_for_daily_brief(),
        )
        assert _x_section_count(saved["sections"]) == 1

        stable = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert stable[0]["action"] == "kept_ok"
        assert stable[0]["status"] == "ok"
        assert calls["n"] == 1

        _seed_x_post(
            store,
            post_id="bbc-2",
            author="BBCChinese",
            url="https://x.com/BBCChinese/status/2",
            text_snapshot="午夜简讯改变当日 X 集合。",
        )
        added = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert added[0]["action"] == "updated"
        assert added[0]["status"] == "ok"
        assert calls["n"] == 2

        store._conn.execute(
            "UPDATE x_posts SET text_snapshot = ? WHERE url = ?",
            ("Edited market take from FT.", "https://x.com/FT/status/1"),
        )
        store._conn.commit()
        edited = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert edited[0]["action"] == "updated"
        assert edited[0]["status"] == "ok"
        assert calls["n"] == 3
        saved = store.get_daily_brief("2026-10-15")
        assert saved["input_fingerprint"] == day_input_fingerprint(
            store.get_articles_for_daily_brief(),
            "2026-10-15",
            store.get_x_posts_for_daily_brief(),
        )
        store.close()


def test_ok_changed_article_set_updates_and_calls_llm():
    llm, calls = _counting_llm()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        _seed_article(store)
        first = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert first[0]["action"] == "inserted"
        assert calls["n"] == 1
        _seed_article(
            store,
            url="https://example.com/2",
            title="第二篇入选稿件标题足够长",
            summary="新增稿件改变当日所选集合。",
            source="tmtpost",
        )
        second = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert second[0]["action"] == "updated"
        assert second[0]["status"] == "ok"
        assert calls["n"] == 2
        saved = store.get_daily_brief("2026-10-15")
        assert saved["input_fingerprint"] == input_fingerprint(
            articles_for_day(store.get_articles_for_daily_brief(), "2026-10-15")
        )
        store.close()


def test_failed_or_empty_regenerated():
    llm, calls = _counting_llm()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        _seed_article(store)
        store.upsert_daily_brief(
            {
                "date": "2026-10-15",
                "generated_at": "2026-10-15T01:00:00+00:00",
                "status": "failed",
                "model": "",
                "lede": "",
                "sections": [],
                "error": "missing DAILY_BRIEF_API_KEY or DAILY_BRIEF_API_BASE",
                "input_fingerprint": input_fingerprint(
                    articles_for_day(store.get_articles_for_daily_brief(), "2026-10-15")
                ),
            }
        )
        failed_run = generate_for_dates(
            store, ["2026-10-15"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert failed_run[0]["action"] == "updated"
        assert failed_run[0]["status"] == "ok"
        assert calls["n"] == 1

        store.upsert_daily_brief(
            {
                "date": "2026-10-14",
                "generated_at": "2026-10-14T01:00:00+00:00",
                "status": "empty",
                "model": "",
                "lede": "",
                "sections": [],
                "error": None,
                "input_fingerprint": input_fingerprint([]),
            }
        )
        _seed_article(
            store,
            url="https://example.com/empty-day",
            published_at="2026-10-14T02:00:00+00:00",
            fetched_at="2026-10-14T03:00:00+00:00",
            title="空日后新增稿",
            summary="空状态应重新生成日报。",
        )
        empty_run = generate_for_dates(
            store, ["2026-10-14"], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert empty_run[0]["action"] == "updated"
        assert empty_run[0]["status"] == "ok"
        assert calls["n"] == 2
        store.close()


def test_today_same_as_other_days_no_force_refresh():
    """Today is not special: ok + same fingerprint → kept_ok, llm_fn not called."""
    llm, calls = _counting_llm()
    today = shanghai_calendar_date()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        _seed_article(
            store,
            published_at=f"{today}T02:00:00+00:00",
            fetched_at=f"{today}T03:00:00+00:00",
        )
        first = generate_for_dates(
            store, [today], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert first[0]["action"] == "inserted"
        assert first[0]["status"] == "ok"
        assert calls["n"] == 1
        second = generate_for_dates(
            store, [today], llm_fn=llm, model="deepseek/deepseek-flash"
        )
        assert second[0]["action"] == "kept_ok"
        assert second[0]["status"] == "ok"
        assert calls["n"] == 1
        src = (ROOT / "src" / "news_archive" / "daily_brief.py").read_text(
            encoding="utf-8"
        )
        assert "Always refresh today" not in src
        assert "date != today" not in src
        store.close()


def test_store_migrates_input_fingerprint_column():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "old.sqlite3"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                published_at TEXT,
                summary TEXT,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                content_snapshot TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                topic_id TEXT
            );
            CREATE TABLE daily_briefs (
                date TEXT PRIMARY KEY,
                generated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                lede TEXT NOT NULL DEFAULT '',
                sections_json TEXT NOT NULL,
                error TEXT
            );
            INSERT INTO daily_briefs
                (date, generated_at, status, model, lede, sections_json, error)
            VALUES
                ('2026-10-15', '2026-10-15T12:00:00+00:00', 'ok', 'm', 'lede', '[]', NULL);
            """
        )
        conn.commit()
        conn.close()
        store = Store(path)
        cols = {
            row["name"]
            for row in store._conn.execute("PRAGMA table_info(daily_briefs)").fetchall()
        }
        assert "input_fingerprint" in cols
        saved = store.get_daily_brief("2026-10-15")
        assert saved["status"] == "ok"
        assert saved["input_fingerprint"] == ""
        store.close()


def _clear_brief_env() -> dict[str, str]:
    saved = {}
    for name in (API_KEY_ENV, API_BASE_ENV, MODEL_ENV, "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        if name in os.environ:
            saved[name] = os.environ.pop(name)
    return saved


def _restore_brief_env(saved: dict[str, str]) -> None:
    for name, value in saved.items():
        os.environ[name] = value


def test_cli_missing_key_exits_zero_and_writes_failed():
    saved_env = _clear_brief_env()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.sqlite3"
            store = Store(db_path)
            store.upsert(
                Article(
                    title="有稿无 key",
                    published_at="2026-10-15T02:00:00+00:00",
                    url="https://z.com/1",
                    summary="摘要句子足够长了。",
                    source="36kr",
                    fetched_at="2026-10-15T03:00:00+00:00",
                    content_snapshot=SECRET_SNAPSHOT,
                    status="active",
                )
            )
            store.close()
            rc = daily_brief_main(
                ["--db", str(db_path), "--date", "2026-10-15", "--json"]
            )
            assert rc == 0
            saved = Store(db_path).get_daily_brief("2026-10-15")
            assert saved["status"] == "failed"
            assert saved["lede"] == ""
    finally:
        _restore_brief_env(saved_env)


def test_cli_empty_day_exits_zero():
    saved_env = _clear_brief_env()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.sqlite3"
            Store(db_path).close()
            rc = daily_brief_main(
                ["--db", str(db_path), "--date", "2026-10-15", "--json"]
            )
            assert rc == 0
            saved = Store(db_path).get_daily_brief("2026-10-15")
            assert saved["status"] == "empty"
    finally:
        _restore_brief_env(saved_env)


def test_cli_never_fails_on_corrupt_handler():
    """main() must return 0 even when the db path cannot be used as sqlite."""
    rc = daily_brief_main(["--db", "/dev/full/not-a-db", "--date", "2026-10-15"])
    assert rc == 0


def test_workflow_wires_daily_brief_secrets_soft_fail():
    yml = (ROOT / ".github" / "workflows" / "daily-fetch.yml").read_text(encoding="utf-8")
    assert "news_archive.daily_brief" in yml
    assert "secrets.DAILY_BRIEF_API_KEY" in yml
    assert "secrets.DAILY_BRIEF_API_BASE" in yml
    assert "secrets.DAILY_BRIEF_MODEL" not in yml
    assert "deepseek/deepseek-flash" in yml
    assert "continue-on-error: true" in yml
    assert "OPENAI_API_KEY" not in yml
    assert "X_BEARER" not in yml
    assert "x_cookie" not in yml.lower()


def test_model_error_redacts_secret_values():
    planted = "sk-live-SHOULD-NOT-LEAK-xyz"

    def boom(_grouped):
        raise RuntimeError(f"401 Authorization: Bearer {planted}")

    brief = generate_daily_brief(
        [_art()], "2026-10-15", llm_fn=boom, model="deepseek/deepseek-flash"
    )
    blob = json.dumps(brief, ensure_ascii=False)
    assert planted not in blob
    assert brief["status"] == "failed"
    assert "Bearer ***" in (brief.get("error") or "")


def test_cli_stdout_never_prints_secret_values():
    import io
    from contextlib import redirect_stderr, redirect_stdout

    import news_archive.daily_briefs as daily_mod

    saved_env = _clear_brief_env()
    planted = "sk-live-SHOULD-NOT-LEAK-xyz"
    os.environ[API_KEY_ENV] = planted
    os.environ[API_BASE_ENV] = "https://api.lkeap.cloud.tencent.com/plan/v3"
    orig = daily_mod.openai_complete

    def fake_complete(*_args, **kwargs):
        raise RuntimeError("401 Authorization: Bearer " + kwargs.get("api_key", planted))

    daily_mod.openai_complete = fake_complete
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.sqlite3"
            store = Store(db_path)
            store.upsert(
                Article(
                    title="有稿将打模型",
                    published_at="2026-10-15T02:00:00+00:00",
                    url="https://z.com/1",
                    summary="摘要句子足够长了。",
                    source="36kr",
                    fetched_at="2026-10-15T03:00:00+00:00",
                    content_snapshot=SECRET_SNAPSHOT,
                    status="active",
                )
            )
            store.close()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = daily_brief_main(
                    ["--db", str(db_path), "--date", "2026-10-15", "--json"]
                )
            assert rc == 0
            combined = stdout.getvalue() + stderr.getvalue()
            assert planted not in combined
            assert "Bearer sk-" not in combined
            saved = Store(db_path).get_daily_brief("2026-10-15")
            assert saved["status"] == "failed"
            assert planted not in json.dumps(saved, ensure_ascii=False)
    finally:
        daily_mod.openai_complete = orig
        os.environ.pop(API_KEY_ENV, None)
        os.environ.pop(API_BASE_ENV, None)
        _restore_brief_env(saved_env)


def _assert_public_only(blob: str) -> None:
    assert "content_snapshot" not in blob
    assert SECRET_SNAPSHOT not in blob
    assert SECRET_COOKIE not in blob
    assert SECRET_AUTH not in blob
    assert SECRET_POST_ID not in blob
    assert "post_id" not in blob
    assert "cookie" not in blob.lower()
    assert "authorization" not in blob.lower()


def test_x_posts_for_day_shanghai_and_active_only():
    posts = [
        _x(url="https://x.com/FT/status/1"),
        _x(
            author="Reuters",
            url="https://x.com/Reuters/status/2",
            posted_at="2026-10-14T15:59:00Z",  # still Shanghai 14th
            text_snapshot="Still the 14th in Shanghai.",
        ),
        _x(
            author="BBCChinese",
            url="https://x.com/BBCChinese/status/3",
            posted_at="2026-10-14T16:00:00Z",
            text_snapshot="Shanghai 15th at midnight.",
        ),
        _x(
            author="TechCrunch",
            url="https://x.com/TechCrunch/status/gone",
            status="gone",
            text_snapshot="Gone post must be excluded.",
        ),
        _x(
            author="NotInList",
            url="https://x.com/NotInList/status/9",
            text_snapshot="Wrong account.",
        ),
        _x(url="https://x.com/FT/status/no-time", posted_at=None, text_snapshot="No posted_at."),
    ]
    day = x_posts_for_day(posts, "2026-10-15")
    urls = {p["url"] for p in day}
    assert urls == {"https://x.com/FT/status/1", "https://x.com/BBCChinese/status/3"}
    for row in day:
        assert set(row) == set(DAILY_BRIEF_X_FIELDS)
    _assert_public_only(json.dumps(day, ensure_ascii=False))


def test_day_with_x_has_dedicated_section():
    captured = []

    def llm(grouped):
        captured.append(json.loads(json.dumps(grouped, ensure_ascii=False)))
        return {
            "lede": "外媒账号关注市场定价。",
            "sections": [
                {
                    "topic_id": X_SECTION_TOPIC_ID,
                    "title": X_SECTION_TITLE,
                    "bullets": ["FT 与 BBC 账号同时提到市场与午夜动态。"],
                }
            ],
        }

    posts = [
        _x(),
        _x(
            author="BBCChinese",
            url="https://x.com/BBCChinese/status/3",
            posted_at="2026-10-14T16:10:00Z",
            text_snapshot="午夜之后的简讯。",
        ),
        _x(
            author="Reuters",
            url="https://x.com/Reuters/status/14",
            posted_at="2026-10-14T10:00:00Z",
            text_snapshot="Other day.",
        ),
    ]
    brief = generate_daily_brief(
        [], "2026-10-15", x_posts=posts, llm_fn=llm, model="gpt-4o-mini"
    )
    assert brief["status"] == "ok"
    assert _x_section_count(brief["sections"]) == 1
    section = brief["sections"][-1]
    assert section["title"] == X_SECTION_TITLE
    assert section["topic_id"] == X_SECTION_TOPIC_ID
    assert 1 <= len(section["bullets"]) <= 3
    assert 1 <= len(section["links"]) <= X_LINKS_MAX
    for link in section["links"]:
        assert set(link) == {"title", "url", "source"}
        assert link["source"] in {"FT", "BBCChinese"}
        assert link["url"].startswith("https://x.com/")
    blob = json.dumps(brief, ensure_ascii=False)
    prompt_blob = json.dumps(captured, ensure_ascii=False)
    _assert_public_only(blob)
    _assert_public_only(prompt_blob)
    x_prompt = next(s for s in captured[0] if s.get("title") == X_SECTION_TITLE)
    assert "articles" not in x_prompt
    for post in x_prompt["x_posts"]:
        assert set(post) == set(DAILY_BRIEF_X_FIELDS)


def test_x_only_missing_config_failed_not_empty():
    brief = generate_daily_brief(
        [], "2026-10-15", x_posts=[_x()], missing_config=True
    )
    assert brief["status"] == "failed"
    assert brief["sections"] == []
    assert brief["lede"] == ""


def test_day_without_x_omits_section():
    posts = [
        _x(posted_at="2026-10-14T10:00:00Z"),  # Shanghai 14th
        _x(author="Reuters", url="https://x.com/Reuters/status/gone", status="gone"),
    ]
    brief = generate_daily_brief(
        [_art()], "2026-10-15", x_posts=posts, llm_fn=_ok_llm, model="gpt-4o-mini"
    )
    assert brief["status"] == "ok"
    assert _x_section_count(brief["sections"]) == 0
    assert any(s.get("topic_id") == "t-space" for s in brief["sections"])


def test_rss_sections_remain_when_x_present():
    def llm(grouped):
        rss = next(s for s in grouped if s.get("topic_id") == "t-space")
        return {
            "lede": "航天与外媒动态并行。",
            "sections": [
                {
                    "topic_id": "t-space",
                    "title": rss.get("title"),
                    "bullets": ["发射按计划完成。"],
                },
                {
                    "topic_id": X_SECTION_TOPIC_ID,
                    "title": X_SECTION_TITLE,
                    "bullets": ["外媒账号关注市场定价。"],
                },
            ],
        }

    brief = generate_daily_brief(
        [_art(), _art(url="https://example.com/3", topic_id=None, title="一则未归类财经短讯足够长")],
        "2026-10-15",
        x_posts=[_x(), _x(author="TechCrunch", url="https://x.com/TechCrunch/status/4", text_snapshot="Startups raised a new round.")],
        llm_fn=llm,
        model="gpt-4o-mini",
    )
    assert brief["status"] == "ok"
    titles = [s["title"] for s in brief["sections"]]
    assert X_SECTION_TITLE in titles
    assert OTHER_TITLE in titles
    assert _x_section_count(brief["sections"]) == 1
    rss_sections = [s for s in brief["sections"] if s["title"] != X_SECTION_TITLE]
    assert rss_sections
    assert all(s.get("topic_id") != X_SECTION_TOPIC_ID for s in rss_sections)
    x_section = next(s for s in brief["sections"] if s["title"] == X_SECTION_TITLE)
    assert len(x_section["links"]) <= X_LINKS_MAX
    assert all(link["source"] in {"FT", "TechCrunch"} for link in x_section["links"])


def test_x_links_cap_eight_and_bullets_cap_three():
    posts = []
    for i in range(10):
        author = [
            "FT",
            "Reuters",
            "BBCChinese",
            "TechCrunch",
            "Tesla",
            "elonmusk",
            "AP",
            "WSJ",
            "BBCWorld",
            "NPR",
            "nytimes",
            "TheEconomist",
            "SCMPNews",
            "Bloomberg",
            "WIRED",
            "AFP",
            "CNBC",
            "AJEnglish",
            "Nature",
        ][i % 19]
        posts.append(
            _x(
                author=author,
                url=f"https://x.com/{author}/status/{i}",
                text_snapshot=f"{author} headline number {i} about markets and policy.",
                posted_at="2026-10-14T16:30:00Z",
            )
        )
    brief = generate_daily_brief(
        [_art()], "2026-10-15", x_posts=posts, llm_fn=_ok_llm, model="gpt-4o-mini"
    )
    x_section = next(s for s in brief["sections"] if s["title"] == X_SECTION_TITLE)
    assert 1 <= len(x_section["bullets"]) <= 3
    assert 1 <= len(x_section["links"]) <= 8
    assert len(x_section["links"]) == 8


def test_truncated_text_only_in_llm_input():
    long_text = "行情 " * 300
    captured = []

    def llm(grouped):
        captured.append(grouped)
        return _ok_llm(grouped)

    brief = generate_daily_brief(
        [_art()],
        "2026-10-15",
        x_posts=[_x(text_snapshot=long_text)],
        llm_fn=llm,
        model="gpt-4o-mini",
    )
    x_prompt = next(s for s in captured[0] if s.get("title") == X_SECTION_TITLE)
    snap = x_prompt["x_posts"][0]["text_snapshot"]
    assert len(snap) <= X_TEXT_SNAPSHOT_MAX
    assert snap.endswith("...")
    x_section = next(s for s in brief["sections"] if s["title"] == X_SECTION_TITLE)
    assert x_section["links"][0]["source"] == "FT"


def test_fingerprint_input_includes_x_selected_set():
    payload = daily_brief_fingerprint_input(
        [_art(), _art(url="https://z.com/other-day", published_at="2026-10-13T02:00:00Z")],
        "2026-10-15",
        x_posts=[_x(), _x(posted_at="2026-10-13T02:00:00Z", url="https://x.com/FT/status/old")],
    )
    assert payload["date"] == "2026-10-15"
    assert {a["url"] for a in payload["articles"]} == {"https://example.com/1"}
    assert {p["url"] for p in payload["x_posts"]} == {"https://x.com/FT/status/1"}
    for post in payload["x_posts"]:
        assert set(post) == set(DAILY_BRIEF_X_FIELDS)
    _assert_public_only(json.dumps(payload, ensure_ascii=False))
    fp = input_fingerprint(payload["articles"], payload["x_posts"])
    assert fp == day_input_fingerprint(
        [_art()],
        "2026-10-15",
        [_x()],
    )
    assert fp != input_fingerprint(payload["articles"], [])
    extra = payload["x_posts"] + [
        {
            "author": "Reuters",
            "text_snapshot": "Another same-day post.",
            "url": "https://x.com/Reuters/status/9",
            "posted_at": "2026-10-14T16:45:00Z",
        }
    ]
    assert input_fingerprint(payload["articles"], extra) != fp
    edited = [
        {**payload["x_posts"][0], "text_snapshot": "Edited same-day post."}
    ]
    assert input_fingerprint(payload["articles"], edited) != fp


def test_store_x_query_omits_post_id_and_secrets():
    store_src = (ROOT / "src" / "news_archive" / "store.py").read_text(encoding="utf-8")
    start = store_src.index("def get_x_posts_for_daily_brief")
    end = store_src.index("\n    def ", start + 10)
    fn = store_src[start:end]
    select_list = fn[fn.index("SELECT"):fn.index("FROM")]
    assert "post_id" not in select_list
    assert "cookie" not in select_list.lower()
    assert "authorization" not in select_list.lower()
    assert "text_snapshot" in select_list

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "t.sqlite3"
        store = Store(db_path)
        x_store = XStore(db_path)
        x_store.upsert(
            XPost(
                post_id=SECRET_POST_ID,
                author="FT",
                url="https://x.com/FT/status/1",
                text_snapshot="Visible X text.",
                posted_at="2026-10-14T16:30:00Z",
                fetched_at="2026-10-15T03:00:00+00:00",
                status="active",
            )
        )
        x_store.close()
        rows = store.get_x_posts_for_daily_brief()
        assert rows
        assert set(rows[0]) == set(DAILY_BRIEF_X_FIELDS)
        blob = json.dumps(rows, ensure_ascii=False)
        assert SECRET_POST_ID not in blob
        assert "post_id" not in blob
        store.close()


def test_store_x_query_missing_table_soft_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        assert store.get_x_posts_for_daily_brief() == []
        store.close()


def test_daily_brief_does_not_call_x_api():
    gen_src = (ROOT / "src" / "news_archive" / "daily_briefs.py").read_text(encoding="utf-8")
    cli_src = (ROOT / "src" / "news_archive" / "daily_brief.py").read_text(encoding="utf-8")
    store_fn = (ROOT / "src" / "news_archive" / "store.py").read_text(encoding="utf-8")
    start = store_fn.index("def get_x_posts_for_daily_brief")
    end = store_fn.index("\n    def ", start + 10)
    for src in (gen_src, cli_src, store_fn[start:end]):
        lower = src.lower()
        assert "x_http_client" not in src
        assert "HomeTimeline" not in src
        assert "HomeLatestTimeline" not in src
        assert "graphql" not in lower
        assert "x_fetch" not in src
        assert "x_cli" not in src


def test_cli_same_day_x_writes_section():
    import io
    from contextlib import redirect_stderr, redirect_stdout

    import news_archive.daily_briefs as daily_mod

    saved_env = _clear_brief_env()
    os.environ[API_KEY_ENV] = "sk-test"
    os.environ[API_BASE_ENV] = "https://api.lkeap.cloud.tencent.com/plan/v3"
    orig = daily_mod.openai_complete

    def fake_complete(grouped, **_kwargs):
        return {
            "lede": "航天与 X 动态。",
            "sections": [
                {
                    "topic_id": "t1",
                    "title": "有稿将打模型",
                    "bullets": ["摘要句子足够长了。"],
                },
                {
                    "topic_id": X_SECTION_TOPIC_ID,
                    "title": X_SECTION_TITLE,
                    "bullets": ["FT 账号提到市场定价。"],
                },
            ],
        }

    daily_mod.openai_complete = fake_complete
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.sqlite3"
            store = Store(db_path)
            store.upsert(
                Article(
                    title="有稿将打模型",
                    published_at="2026-10-15T02:00:00+00:00",
                    url="https://z.com/1",
                    summary="摘要句子足够长了。",
                    source="36kr",
                    fetched_at="2026-10-15T03:00:00+00:00",
                    content_snapshot=SECRET_SNAPSHOT,
                    topic_id="t1",
                )
            )
            store.close()
            x_store = XStore(db_path)
            x_store.upsert(
                XPost(
                    post_id=SECRET_POST_ID,
                    author="FT",
                    url="https://x.com/FT/status/1",
                    text_snapshot="Markets rose as traders priced in a rate pause.",
                    posted_at="2026-10-14T16:30:00Z",
                    fetched_at="2026-10-15T03:00:00+00:00",
                    status="active",
                )
            )
            x_store.close()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = daily_brief_main(
                    ["--db", str(db_path), "--date", "2026-10-15", "--json"]
                )
            assert rc == 0
            saved = Store(db_path).get_daily_brief("2026-10-15")
            assert saved["status"] == "ok"
            assert _x_section_count(saved["sections"]) == 1
            blob = json.dumps(saved, ensure_ascii=False)
            _assert_public_only(blob)
            assert SECRET_SNAPSHOT not in (stdout.getvalue() + stderr.getvalue())
    finally:
        daily_mod.openai_complete = orig
        os.environ.pop(API_KEY_ENV, None)
        os.environ.pop(API_BASE_ENV, None)
        _restore_brief_env(saved_env)


if __name__ == "__main__":
    test_shanghai_date_uses_calendar_not_utc()
    test_articles_for_day_published_at_fallback_fetched_at()
    test_group_by_topic_and_single_other()
    test_sections_cap_eight_with_other_last()
    test_empty_day_status_empty()
    test_missing_key_status_failed()
    test_model_error_status_failed()
    test_ok_brief_records_default_model_when_unspecified()
    test_ok_brief_from_title_summary_only()
    test_store_daily_brief_query_omits_snapshot()
    test_cli_missing_key_exits_zero_and_writes_failed()
    test_cli_empty_day_exits_zero()
    test_cli_never_fails_on_corrupt_handler()
    test_workflow_wires_daily_brief_secrets_soft_fail()
    test_resolve_llm_config_requires_key_and_base()
    test_resolve_model_defaults_and_env_override()
    test_redact_secrets_never_keeps_values()
    test_model_error_redacts_secret_values()
    test_cli_stdout_never_prints_secret_values()
    test_input_fingerprint_stable_sorted_by_url()
    test_ok_same_fingerprint_kept_ok_skips_llm()
    test_ok_unchanged_rss_changed_x_updates_stable_x_kept_ok()
    test_ok_changed_article_set_updates_and_calls_llm()
    test_failed_or_empty_regenerated()
    test_today_same_as_other_days_no_force_refresh()
    test_store_migrates_input_fingerprint_column()
    test_x_posts_for_day_shanghai_and_active_only()
    test_day_with_x_has_dedicated_section()
    test_x_only_missing_config_failed_not_empty()
    test_day_without_x_omits_section()
    test_rss_sections_remain_when_x_present()
    test_x_links_cap_eight_and_bullets_cap_three()
    test_truncated_text_only_in_llm_input()
    test_fingerprint_input_includes_x_selected_set()
    test_store_x_query_omits_post_id_and_secrets()
    test_store_x_query_missing_table_soft_empty()
    test_daily_brief_does_not_call_x_api()
    test_cli_same_day_x_writes_section()
    print("✓ All daily brief tests passed")
