"""CLI: generate daily_briefs rows.

Fetch/Persist stay on the soft-fail path (Persist is `if: always()` + fetch
success). Today's Shanghai-calendar brief ending failed — or any written
failed / LLM timeout — exits 1 so the brief *step* is red.

Hard invariant: never upsert status=failed over an existing status=ok row.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .daily_briefs import (
    API_BASE_ENV,
    API_KEY_ENV,
    day_input_fingerprint,
    generate_daily_brief,
    last_n_shanghai_dates,
    make_llm_fn,
    redact_secrets,
    resolve_llm_config,
    resolve_model,
    shanghai_calendar_date,
)
from .store import Store

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date_list(raw: str | None) -> list[str]:
    """Parse comma-separated YYYY-MM-DD. Empty / None → []."""
    if not raw or not str(raw).strip():
        return []
    dates: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        day = part.strip()
        if not day:
            continue
        if not DATE_RE.fullmatch(day):
            raise ValueError(f"invalid Shanghai date {day!r} (want YYYY-MM-DD)")
        if day not in seen:
            dates.append(day)
            seen.add(day)
    return dates


def written_failed_rows(results: list[dict]) -> list[dict]:
    return [row for row in results if row.get("status") == "failed"]


def protected_ok_rows(results: list[dict]) -> list[dict]:
    return [
        row
        for row in results
        if row.get("action") == "kept_ok" and (row.get("error") or row.get("protected"))
    ]


def brief_run_should_fail(stats: dict, today: str | None = None) -> bool:
    """True when the brief step must go red (visible; Persist still runs).

    - top-level CLI error
    - any date written as status=failed (no prior ok was kept)
    - today's Shanghai brief ended failed
    - LLM timeout/parse failed but we kept a prior ok (still must be visible)
    """
    if stats.get("error"):
        return True
    today = today or shanghai_calendar_date()
    for row in stats.get("results") or []:
        if row.get("status") == "failed":
            return True
        if row.get("date") == today and row.get("status") == "failed":
            return True
        if row.get("action") == "kept_ok" and (row.get("error") or row.get("protected")):
            return True
    return False


def render_brief_job_summary(stats: dict, today: str | None = None) -> str:
    """Markdown for GITHUB_STEP_SUMMARY. No secret values."""
    today = today or shanghai_calendar_date()
    results = stats.get("results") or []
    written = written_failed_rows(results)
    protected = protected_ok_rows(results)
    lines = [
        "## Daily brief",
        "",
        f"- **today (Asia/Shanghai):** {today}",
        f"- **config_present:** {bool(stats.get('config_present'))}",
        f"- **visible_failure:** {bool(stats.get('visible_failure'))}",
        "",
        "| date | status | action | error |",
        "| --- | --- | --- | --- |",
    ]
    if not results and stats.get("error"):
        lines.append(f"| — | error | — | {stats['error']} |")
    for row in results:
        err = (row.get("error") or "").replace("|", "/")
        extra = " protected ok" if row.get("protected") else ""
        lines.append(
            f"| {row.get('date')} | {row.get('status')} | "
            f"{row.get('action')}{extra} | {err} |"
        )
    if written:
        dates = ", ".join(row["date"] for row in written)
        lines.extend(
            [
                "",
                f"⚠ **Wrote status=failed** for {dates}. "
                "Site shows「当日摘要生成失败」for those days.",
            ]
        )
    if protected:
        dates = ", ".join(row["date"] for row in protected)
        lines.extend(
            [
                "",
                f"⚠ **Kept prior ok** (never overwrite ok with failed) for {dates}. "
                "LLM still failed — timeout/parse must stay visible.",
            ]
        )
    if stats.get("error"):
        lines.extend(["", f"⚠ **CLI error:** {stats['error']}"])
    if not written and not protected and not stats.get("error"):
        lines.extend(["", "Daily brief run wrote no failed rows."])
    lines.append("")
    return "\n".join(lines)


def write_brief_job_summary(
    stats: dict,
    path: str | Path | None = None,
    *,
    today: str | None = None,
) -> None:
    target = path if path is not None else os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    text = render_brief_job_summary(stats, today=today)
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def emit_brief_annotations(stats: dict, today: str | None = None) -> None:
    """Non-silent GitHub Actions annotations (::error / ::warning)."""
    today = today or shanghai_calendar_date()
    if stats.get("error"):
        print(
            f"::error title=Daily brief failed::{stats['error']}",
            file=sys.stderr,
        )
    for row in written_failed_rows(stats.get("results") or []):
        err = row.get("error") or "status=failed"
        print(
            f"::error title=Daily brief failed::{row.get('date')} {err}",
            file=sys.stderr,
        )
        if row.get("date") == today:
            print(
                f"::error title=Today's daily brief failed::"
                f"{today} ended status=failed — site shows「当日摘要生成失败」",
                file=sys.stderr,
            )
    for row in protected_ok_rows(stats.get("results") or []):
        err = row.get("error") or "LLM failed"
        print(
            f"::error title=Daily brief LLM failed (kept prior ok)::"
            f"{row.get('date')} {err}",
            file=sys.stderr,
        )


def generate_for_dates(
    store: Store,
    dates: list[str],
    *,
    llm_fn=None,
    model: str | None = None,
    missing_config: bool | None = None,
    deadline_s: float | None = None,
    monotonic=time.monotonic,
    backfill_failed: bool = False,
    retries: int | None = None,
    sleep_fn=None,
) -> list[dict]:
    """Generate briefs for dates. Missing key / LLM errors write failed/empty.

    Skip LLM (`kept_ok`) when an existing row is status=ok and the day's
    selected RSS + X fingerprint is unchanged — including today.

    `--backfill-failed` skips every existing ok row (only missing/failed/empty).
    Re-runs must never upsert failed over an existing ok for the same date.

    If `deadline_s` elapses, remaining dates are skipped without upsert
    (do not overwrite an existing ok brief). Fetch/persist stay green;
    the brief step still goes red when a generated day ends failed.
    """
    articles = store.get_articles_for_daily_brief()
    try:
        x_posts = store.get_x_posts_for_daily_brief()
    except Exception:
        # X Tab / x-fetch soft-fail: missing table or read error omits X, RSS still runs.
        x_posts = []
    config = resolve_llm_config()
    if llm_fn is None:
        llm_fn = make_llm_fn(config) if config else None
        if missing_config is None:
            missing_config = config is None
    elif missing_config is None:
        missing_config = False
    if not model:
        model = config["model"] if config else resolve_model()
    api_key = (config or {}).get("api_key") or ""
    results: list[dict] = []
    deadline_at = (
        monotonic() + deadline_s
        if deadline_s is not None and deadline_s > 0
        else None
    )

    for date in dates:
        if deadline_at is not None and monotonic() >= deadline_at:
            print(
                f"⚠ daily brief deadline ({deadline_s:.0f}s) reached; "
                f"skipping remaining days starting {date}",
                file=sys.stderr,
            )
            for skipped in dates[dates.index(date) :]:
                results.append(
                    {
                        "date": skipped,
                        "action": "skipped_deadline",
                        "status": "skipped",
                        "error": "daily brief deadline reached; skipped remaining days",
                    }
                )
            break
        fingerprint = day_input_fingerprint(articles, date, x_posts)
        existing = store.get_daily_brief(date)
        if existing and existing.get("status") == "ok":
            if backfill_failed:
                results.append(
                    {
                        "date": date,
                        "action": "skipped_ok",
                        "status": "ok",
                    }
                )
                continue
            if (existing.get("input_fingerprint") or "") == fingerprint:
                results.append(
                    {
                        "date": date,
                        "action": "kept_ok",
                        "status": "ok",
                    }
                )
                continue
        try:
            brief = generate_daily_brief(
                articles,
                date,
                x_posts=x_posts,
                llm_fn=llm_fn,
                model=model,
                missing_config=missing_config,
                retries=retries,
                sleep_fn=sleep_fn,
            )
        except Exception as exc:  # never break fetch/deploy
            brief = {
                "date": date,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "model": model,
                "lede": "",
                "sections": [],
                "error": redact_secrets(str(exc), api_key),
                "input_fingerprint": fingerprint,
            }
        if brief["status"] == "failed" and existing and existing.get("status") == "ok":
            print(
                f"⚠ daily brief {date} LLM failed; keeping existing ok row "
                f"(never overwrite ok with failed): "
                f"{redact_secrets(brief.get('error') or '', api_key)}",
                file=sys.stderr,
            )
        action = store.upsert_daily_brief(brief)
        stored_status = "ok" if action == "kept_ok" else brief["status"]
        row: dict[str, Any] = {
            "date": date,
            "action": action,
            "status": stored_status,
            "error": redact_secrets(brief.get("error") or "", api_key),
            "model": brief.get("model") or "",
        }
        if action == "kept_ok" and brief.get("status") == "failed":
            row["protected"] = True
        results.append(row)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Shanghai-calendar daily briefs. "
            "Never overwrites an existing status=ok row with failed. "
            "Today failed / written failed / LLM timeout exits 1 (brief step red; "
            "Persist still runs). "
            "QA/CEO backfill: --dates 2026-10-25,2026-10-24,2026-10-23,2026-10-21 "
            "--backfill-failed (failed/missing only)."
        )
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/archive.sqlite3"),
        help="SQLite path (default: data/archive.sqlite3)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Single YYYY-MM-DD (Asia/Shanghai). Default: last --days days.",
    )
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        help=(
            "Comma-separated YYYY-MM-DD (Asia/Shanghai), e.g. "
            "2026-10-25,2026-10-24,2026-10-23,2026-10-21"
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="How many Shanghai calendar days to cover (default 7).",
    )
    parser.add_argument(
        "--backfill-failed",
        action="store_true",
        help="Only generate missing/failed/empty dates; skip every existing ok.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON stats")
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=0,
        help="Wall-clock budget; remaining days skip without failing Persist.",
    )
    args = parser.parse_args(argv)

    stats: dict = {
        "ok": True,
        "secret_names": [API_KEY_ENV, API_BASE_ENV],
        "config_present": resolve_llm_config() is not None,
        "results": [],
        "error": None,
        "visible_failure": False,
        "backfill_failed": bool(args.backfill_failed),
    }
    today = shanghai_calendar_date()
    try:
        store = Store(args.db)
        if args.dates:
            dates = parse_date_list(args.dates)
        elif args.date:
            dates = [args.date]
        else:
            dates = last_n_shanghai_dates(max(1, args.days))
        stats["results"] = generate_for_dates(
            store,
            dates,
            deadline_s=args.deadline_seconds,
            backfill_failed=args.backfill_failed,
        )
        store.close()
    except Exception as exc:
        stats["error"] = redact_secrets(str(exc))
        print(f"⚠ daily brief soft-fail: {stats['error']}", file=sys.stderr)

    stats["visible_failure"] = brief_run_should_fail(stats, today=today)
    stats["ok"] = not stats["visible_failure"]
    write_brief_job_summary(stats, today=today)
    emit_brief_annotations(stats, today=today)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        if stats["error"]:
            print(f"daily-brief error={stats['error']}")
        for row in stats["results"]:
            extra = f" error={row['error']}" if row.get("error") else ""
            print(f"daily-brief {row['date']} status={row['status']} action={row['action']}{extra}")
        if not stats["config_present"]:
            print(
                f"⚠ {API_KEY_ENV} or {API_BASE_ENV} missing — wrote failed/empty "
                f"(brief step red if a day was written failed)",
                file=sys.stderr,
            )

    return 1 if stats["visible_failure"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
