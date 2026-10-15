"""P2 topic_briefs acceptance tests (rules-v1, no LLM)."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_archive.briefs import (
    build_brief_for_topic,
    extract_bullets,
    group_active_by_topic,
    topics_needing_briefs,
)
from news_archive.schema import Article
from news_archive.store import Store


def _now(offset_h: float = 0.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_h)).isoformat()


def test_extract_bullets_no_invent():
    assert extract_bullets(None) == []
    assert extract_bullets("") == []
    bullets = extract_bullets("第一句内容足够长了。第二句也足够长了。第三句继续。第四句忽略。")
    assert 1 <= len(bullets) <= 3
    assert all("编造" not in b for b in bullets)


def test_acceptance_1_two_source_brief():
    articles = [
        {
            "url": "https://a.com/1",
            "title": "SpaceX发射成功",
            "published_at": _now(),
            "summary": "SpaceX今日成功发射火星探测器，任务按计划进行。",
            "content_snapshot": "SpaceX今日成功发射火星探测器，任务按计划进行。地面站确认信号正常。",
            "source": "36kr",
            "status": "active",
            "topic_id": "t1",
        },
        {
            "url": "https://b.com/1",
            "title": "SpaceX 发射成功",
            "published_at": _now(1),
            "summary": "报道称SpaceX完成发射。",
            "content_snapshot": "报道称SpaceX完成发射。多位分析师表示这是重要里程碑。",
            "source": "tmtpost",
            "status": "active",
            "topic_id": "t1",
        },
    ]
    brief = build_brief_for_topic("t1", articles)
    assert brief["status"] == "ok"
    assert len(brief["sources"]) == 2
    assert {s["source"] for s in brief["sources"]} == {"36kr", "tmtpost"}
    assert len(brief["article_urls"]) == 2
    print("✓ Acceptance 1: two-source brief")


def test_acceptance_2_single_source_skip():
    by_topic = {
        "solo": [
            {
                "url": "https://a.com/solo",
                "title": "独源稿",
                "published_at": _now(),
                "source": "36kr",
                "status": "active",
                "topic_id": "solo",
            }
        ]
    }
    need = topics_needing_briefs(by_topic, {})
    assert "solo" not in need
    print("✓ Acceptance 2: single-source skipped")


def test_acceptance_3_update_on_new_source():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        t = "topic-update"
        a1 = Article(
            title="事件A",
            published_at=_now(),
            url="https://a.com/1",
            summary="要点一足够长的句子。",
            source="36kr",
            fetched_at=_now(),
            content_snapshot="要点一足够长的句子。补充一句。",
            status="active",
            topic_id=t,
        )
        a2 = Article(
            title="事件A报道",
            published_at=_now(1),
            url="https://b.com/1",
            summary="要点二足够长的句子。",
            source="tmtpost",
            fetched_at=_now(),
            content_snapshot="要点二足够长的句子。再补一句。",
            status="active",
            topic_id=t,
        )
        store.upsert(a1)
        store.upsert(a2)
        arts = store.get_articles_for_briefs()
        by_topic = group_active_by_topic(arts)
        brief = build_brief_for_topic(t, by_topic[t])
        store.upsert_topic_brief(brief)
        assert len(store.get_topic_briefs()[t]["sources"]) == 2

        a3 = Article(
            title="事件A第三源",
            published_at=_now(2),
            url="https://c.com/1",
            summary="第三源足够长的句子内容。",
            source="geekpark",
            fetched_at=_now(),
            content_snapshot="第三源足够长的句子内容。额外细节。",
            status="active",
            topic_id=t,
        )
        store.upsert(a3)
        arts = store.get_articles_for_briefs()
        by_topic = group_active_by_topic(arts)
        existing = store.get_topic_briefs()
        need = topics_needing_briefs(by_topic, existing)
        assert t in need
        brief2 = build_brief_for_topic(t, [a for a in by_topic[t] if a["status"] == "active"])
        store.upsert_topic_brief(brief2)
        saved = store.get_topic_briefs()[t]
        assert len(saved["sources"]) == 3
        assert "https://c.com/1" in saved["article_urls"]
        store.close()
    print("✓ Acceptance 3: brief updates with third source")


def test_acceptance_4_fail_soft():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        # persist still works
        art = Article(
            title="ok",
            published_at=_now(),
            url="https://x.com/1",
            summary="s",
            source="36kr",
            fetched_at=_now(),
            content_snapshot="body",
            status="active",
            topic_id="tf",
        )
        assert store.upsert(art)
        arts = [
            {
                "url": "https://a.com/1",
                "title": "A",
                "published_at": _now(),
                "summary": "长句子内容用于测试失败路径一二。",
                "content_snapshot": "长句子内容用于测试失败路径一二。",
                "source": "36kr",
                "status": "active",
                "topic_id": "tf",
            },
            {
                "url": "https://b.com/1",
                "title": "B",
                "published_at": _now(),
                "summary": "另一源长句子内容用于测试。",
                "content_snapshot": "另一源长句子内容用于测试。",
                "source": "tmtpost",
                "status": "active",
                "topic_id": "tf",
            },
        ]
        ok = build_brief_for_topic("tf", arts)
        store.upsert_topic_brief(ok)
        failed = build_brief_for_topic("tf", arts, force_fail=True)
        action = store.upsert_topic_brief(failed)
        assert action == "kept_ok"
        saved = store.get_topic_briefs()["tf"]
        assert saved["status"] == "ok"
        assert saved.get("last_error")
        # no prior: insert failed
        failed2 = build_brief_for_topic("tf2", arts, force_fail=True)
        failed2["topic_id"] = "tf2"
        store.upsert_topic_brief(failed2)
        assert store.get_topic_briefs()["tf2"]["status"] == "failed"
        store.close()
    print("✓ Acceptance 4: fail soft, keep ok brief")


def test_acceptance_5_p0_p1_schema():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.sqlite3")
        art = Article(
            title="T",
            published_at=_now(),
            url="https://z.com/1",
            summary="s",
            source="36kr",
            fetched_at=_now(),
            content_snapshot="c",
            status="active",
            topic_id=None,
        )
        assert store.upsert(art)
        assert not store.upsert(art)  # dedup
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert "articles" in names and "topic_briefs" in names
        store.close()
    print("✓ Acceptance 5: P0/P1 schema intact + topic_briefs")


if __name__ == "__main__":
    test_extract_bullets_no_invent()
    test_acceptance_1_two_source_brief()
    test_acceptance_2_single_source_skip()
    test_acceptance_3_update_on_new_source()
    test_acceptance_4_fail_soft()
    test_acceptance_5_p0_p1_schema()
    print("\n✅ All brief tests PASSED")
