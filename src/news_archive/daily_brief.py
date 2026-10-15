"""CLI: generate daily_briefs rows. Always exits 0 (soft-fail)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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
)
from .store import Store


def generate_for_dates(
    store: Store,
    dates: list[str],
    *,
    llm_fn=None,
    model: str | None = None,
    missing_config: bool | None = None,
) -> list[dict]:
    """Generate briefs for dates. Missing key / LLM errors write failed/empty.

    Skip LLM (`kept_ok`) when an existing row is status=ok and the day's
    selected RSS + X fingerprint is unchanged — including today.
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

    for date in dates:
        fingerprint = day_input_fingerprint(articles, date, x_posts)
        existing = store.get_daily_brief(date)
        if (
            existing
            and existing.get("status") == "ok"
            and (existing.get("input_fingerprint") or "") == fingerprint
        ):
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
        action = store.upsert_daily_brief(brief)
        results.append(
            {
                "date": date,
                "action": action,
                "status": brief["status"],
                "error": redact_secrets(brief.get("error") or "", api_key),
                "model": brief.get("model") or "",
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Shanghai-calendar daily briefs (soft-fail)."
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
        "--days",
        type=int,
        default=7,
        help="How many Shanghai calendar days to cover (default 7).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON stats")
    args = parser.parse_args(argv)

    stats: dict = {
        "ok": True,
        "secret_names": [API_KEY_ENV, API_BASE_ENV],
        "config_present": resolve_llm_config() is not None,
        "results": [],
        "error": None,
    }
    try:
        store = Store(args.db)
        dates = [args.date] if args.date else last_n_shanghai_dates(max(1, args.days))
        stats["results"] = generate_for_dates(store, dates)
        store.close()
    except Exception as exc:
        stats["error"] = redact_secrets(str(exc))
        print(f"⚠ daily brief soft-fail: {stats['error']}", file=sys.stderr)

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
                f"⚠ {API_KEY_ENV} or {API_BASE_ENV} missing — wrote failed/empty, job still ok",
                file=sys.stderr,
            )

    return 0  # never fail the workflow


if __name__ == "__main__":
    raise SystemExit(main())
