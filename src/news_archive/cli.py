"""CLI: fetch → dedupe → store → enrich missing snapshots → optional JSONL export."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .briefs import (
    build_brief_for_topic,
    group_active_by_topic,
    topics_needing_briefs,
)
from .clustering import (
    CLUSTER_DEADLINE_S,
    CLUSTER_MAX_CANDIDATES,
    RECLUSTER_LOOKBACK_HOURS,
    assign_topic_ids,
)
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
    t0 = time.monotonic()
    timings: dict[str, float] = {}
    results = fetch_all(SOURCES)
    timings["rss_s"] = time.monotonic() - t0
    print(f"INFO fetch_phase rss_s={timings['rss_s']:.1f}", file=sys.stderr)

    stats: dict[str, object] = {"sources": {}, "inserted": 0, "seen": 0, "errors": {}}
    t_upsert = time.monotonic()
    for source_id, payload in results.items():
        if isinstance(payload, Exception):
            # Per-source isolation in fetch_all: record + WARN, never hard-fail
            # the CLI. A single flaky feed (e.g. people.com.cn read timeout)
            # must not skip Persist of the sources that did succeed.
            stats["errors"][source_id] = str(payload)  # type: ignore[index]
            print(
                f"WARN {source_id}: RSS source soft-fail (job continues): {payload}",
                file=sys.stderr,
            )
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
    timings["upsert_s"] = time.monotonic() - t_upsert
    print(f"INFO fetch_phase upsert_s={timings['upsert_s']:.1f}", file=sys.stderr)

    # Archive-first: fetch original page into private content_snapshot when
    # the snapshot is missing/unusable. Public summary stays ≤280; only fill
    # it when empty/<80. Soft-fail — never fail the RSS job.
    t_enrich = time.monotonic()
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
    timings["enrich_s"] = time.monotonic() - t_enrich
    print(f"INFO fetch_phase enrich_s={timings['enrich_s']:.1f}", file=sys.stderr)

    # After enrich / before validate: drop stuck both-empty active rows
    # (e.g. nyt_business live-blog already on the data branch). Idempotent.
    purged = store.purge_both_empty_active()
    stats["purged_both_empty"] = purged
    print(f"purged_both_empty={purged}", file=sys.stderr)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        out = Path(summary_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as handle:
            handle.write("\n## Thin-row heal\n\n")
            handle.write(f"- **deleted both-empty active rows:** {purged}\n")

    # Recluster only the live window. Clearing every orphan topic_id (most
    # singletons have no ok brief) made assign_topic_ids O(n²) on the whole
    # archive and cancelled Fetch at 45m before Persist.
    t_cluster = time.monotonic()
    already_open = store.count_active_without_topic()
    clear_budget = max(0, CLUSTER_MAX_CANDIDATES - already_open)
    cleared = store.clear_topic_ids_without_ok_brief(
        lookback_hours=RECLUSTER_LOOKBACK_HOURS,
        max_clear=clear_budget,
    )
    stats["recluster_cleared"] = cleared
    stats["recluster_lookback_hours"] = RECLUSTER_LOOKBACK_HOURS
    articles = store.get_articles_for_clustering()
    candidate_urls = {
        a["url"]
        for a in articles
        if a.get("status") == "active" and not a.get("topic_id")
    }
    clustered = assign_topic_ids(
        articles,
        max_candidates=CLUSTER_MAX_CANDIDATES,
        deadline_s=CLUSTER_DEADLINE_S,
    )
    url_to_topic = {
        a["url"]: a["topic_id"]
        for a in clustered
        if a.get("topic_id") and a["url"] in candidate_urls
    }
    clustered_count = store.update_topic_ids(url_to_topic)
    stats["clustered"] = clustered_count
    stats["cluster_candidates"] = len(candidate_urls)
    timings["cluster_s"] = time.monotonic() - t_cluster
    print(
        f"INFO fetch_phase cluster_s={timings['cluster_s']:.1f} "
        f"cleared={cleared} candidates={len(candidate_urls)} "
        f"clustered={clustered_count}",
        file=sys.stderr,
    )

    # P2: multi-source topic briefs (rules-v1); failures never block persist
    t_briefs = time.monotonic()
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
    timings["briefs_s"] = time.monotonic() - t_briefs
    print(f"INFO fetch_phase briefs_s={timings['briefs_s']:.1f}", file=sys.stderr)

    export_count = None
    t_export = time.monotonic()
    if args.export_jsonl:
        export_count = store.export_jsonl(args.export_jsonl)
    timings["export_s"] = time.monotonic() - t_export
    timings["total_s"] = time.monotonic() - t0
    print(f"INFO fetch_phase export_s={timings['export_s']:.1f}", file=sys.stderr)
    print(f"INFO fetch_phase total_s={timings['total_s']:.1f}", file=sys.stderr)
    stats["timings"] = {k: round(v, 3) for k, v in timings.items()}

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
            print(f"  WARN {sid}: {err}", file=sys.stderr)
        if export_count is not None:
            print(f"exported={export_count} -> {args.export_jsonl}")

    # Isolated per-source fetch exceptions are soft-fail (enrich-style):
    # exit 0 so GitHub Actions still runs P0 acceptance + Persist.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
