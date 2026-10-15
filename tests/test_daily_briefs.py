"""Daily brief generation: Shanghai day, topic grouping, soft-fail, no snapshot."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_archive.daily_brief import main as daily_brief_main
from news_archive.daily_briefs import (
    API_BASE_ENV,
    API_KEY_ENV,
    DAILY_BRIEF_ARTICLE_FIELDS,
    DEFAULT_MODEL,
    MODEL_ENV,
    OTHER_TITLE,
    SECTIONS_MAX,
    articles_for_day,
    generate_daily_brief,
    group_sections,
    redact_secrets,
    resolve_llm_config,
    resolve_model,
    shanghai_calendar_date,
)
from news_archive.schema import Article
from news_archive.store import Store

ROOT = Path(__file__).parent.parent
SECRET_SNAPSHOT = "SECRET_SNAPSHOT_BODY_SHOULD_NEVER_LEAK"


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
    print("✓ All daily brief tests passed")
