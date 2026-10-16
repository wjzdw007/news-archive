"""CLI: fetch → dedupe → store → enrich missing snapshots → optional JSONL export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .briefs import (
    build_brief_for_topic,
    group_active_by_topic,
    topics_needing_briefs,
)
from .clustering import assign_topic_ids
from .enrich import enrich_store, write_job_summary
from .fetch import fetch_all
from .news_display import display_window_diversity
from .sources import SOURCES
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch P0 news feeds into SQLite")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/archive.sqlite3"),
        help="SQLite path (default: data/archive.sqlite3)",
    )
    parser.add_argument(
        "--export-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL export path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print run stats as JSON",
    )
    args = parser.parse_args(argv)

    store = Store(args.db)
    results = fetch_all(SOURCES)

    stats: dict[str, object] = {"sources": {}, "inserted": 0, "seen": 0, "errors": {}}
    for source_id, payload in results.items():
        if isinstance(payload, Exception):
            stats["errors"][source_id] = str(payload)  # type: ignore[index]
            continue
        inserted = 0
        for article in payload:
            stats["seen"] = int(stats["seen"]) + 1
            if store.upsert(article):
                inserted += 1
        stats["sources"][source_id] = {  # type: ignore[index]
            "fetched": len(payload),
            "inserted": inserted,
        }
        stats["inserted"] = int(stats["inserted"]) + inserted

    # Archive-first: fetch original page into private content_snapshot when
    # the snapshot is missing/unusable. Public summary stays ≤280; only fill
    # it when empty/<80. Soft-fail — never fail the RSS job.
    try:
        stats["enrich"] = enrich_store(store)
        try:
            diversity = None
            try:
                diversity = display_window_diversity(store.get_articles_for_news_list())
                stats["display_diversity"] = diversity
            except Exception as div_exc:  # noqa: BLE001 — board still writes enrich
                print(
                    f"enrich summary diversity soft-fail: {type(div_exc).__name__}",
                    file=sys.stderr,
                )
            write_job_summary(stats["enrich"], diversity=diversity)  # type: ignore[arg-type]
        except Exception as summary_exc:  # noqa: BLE001 — never fail fetch
            print(
                f"enrich summary soft-fail: {type(summary_exc).__name__}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 — isolate from persist / clustering
        stats["enrich_error"] = type(exc).__name__
        print(f"enrich soft-fail (job continues): {type(exc).__name__}", file=sys.stderr)

    # Self-heal rows that landed with both summary and snapshot empty
    # (empty RSS description + enrich backoff / budget). Title is already
    # required at ingest; public summary stays ≤280.
    healed = store.fill_empty_summaries_from_title()
    stats["healed_empty_summaries"] = healed
    if healed:
        print(f"healed_empty_summaries={healed} (title fallback)", file=sys.stderr)

    # Recluster: clear topic_ids not covered by an ok brief, then assign
    cleared = store.clear_topic_ids_without_ok_brief()
    stats["recluster_cleared"] = cleared
    articles = store.get_articles_for_clustering()
    clustered = assign_topic_ids(articles)
    url_to_topic = {a["url"]: a["topic_id"] for a in clustered if a.get("topic_id")}
    clustered_count = store.update_topic_ids(url_to_topic)
    stats["clustered"] = clustered_count

    # P2: multi-source topic briefs (rules-v1); failures never block persist
    brief_stats = {"generated": 0, "updated": 0, "kept_ok": 0, "failed": 0, "skipped": 0}
    try:
        arts = store.get_articles_for_briefs()
        by_topic = group_active_by_topic(arts)
        existing = store.get_topic_briefs()
        for tid in topics_needing_briefs(by_topic, existing):
            active = [a for a in by_topic[tid] if a.get("status") == "active"]
            try:
                brief = build_brief_for_topic(tid, active)
                action = store.upsert_topic_brief(brief)
                if brief["status"] == "failed":
                    brief_stats["failed"] += 1
                elif action == "updated":
                    brief_stats["updated"] += 1
                elif action == "kept_ok":
                    brief_stats["kept_ok"] += 1
                else:
                    brief_stats["generated"] += 1
            except Exception as exc:  # soft-fail per topic
                failed = build_brief_for_topic(tid, active)
                failed["status"] = "failed"
                failed["error"] = str(exc)
                failed["sources"] = []
                action = store.upsert_topic_brief(failed)
                brief_stats["failed"] += 1
                if action == "kept_ok":
                    brief_stats["kept_ok"] += 1
        brief_stats["skipped"] = max(0, len(by_topic) - brief_stats["generated"]
                                     - brief_stats["updated"] - brief_stats["failed"])
    except Exception as exc:
        stats["brief_error"] = str(exc)
    stats["briefs"] = brief_stats

    export_count = None
    if args.export_jsonl:
        export_count = store.export_jsonl(args.export_jsonl)

    store.close()

    if args.json:
        out = {
            **stats,
            "by_source_total": Store(args.db).count_by_source(),
            "export_count": export_count,
        }
        Store(args.db).close()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"seen={stats['seen']} inserted={stats['inserted']}")
        for sid, detail in stats["sources"].items():  # type: ignore[union-attr]
            print(f"  {sid}: fetched={detail['fetched']} inserted={detail['inserted']}")
        for sid, err in stats["errors"].items():  # type: ignore[union-attr]
            print(f"  ERROR {sid}: {err}", file=sys.stderr)
        if export_count is not None:
            print(f"exported={export_count} -> {args.export_jsonl}")

    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
