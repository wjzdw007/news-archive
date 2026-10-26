"""CLI: generate daily_briefs rows.

Older Shanghai days stay soft-fail. The current Shanghai day must not be
green-washed: failed / skipped / missing today exits non-zero so the
workflow check can turn the run red. Never write mock ok content.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .daily_briefs import (
    API_BASE_ENV,
    API_KEY_ENV,
    LLM_RETRY_BACKOFF_S,
    OLDER_LLM_ATTEMPTS,
    TODAY_LLM_ATTEMPTS,
    day_input_fingerprint,
    generate_daily_brief,
    is_retryable_llm_error,
    last_n_shanghai_dates,
    make_llm_fn,
    prioritize_failed_backfill,
    redact_secrets,
    resolve_llm_config,
    resolve_model,
    shanghai_calendar_date,
    today_status_is_success,
)
from .store import Store


def _failed_row(date: str, *, model: str, fingerprint: str, error: str) -> dict:
    return {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "model": model,
        "lede": "",
        "sections": [],
        "error": error,
        "input_fingerprint": fingerprint,
    }


def write_today_status_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def append_github_output(today: str, status: str | None) -> None:
    dest = os.environ.get("GITHUB_OUTPUT")
    if not dest:
        return
    with open(dest, "a", encoding="utf-8") as fh:
        fh.write(f"today_date={today}\n")
        fh.write(f"today_status={status or 'missing'}\n")


def emit_today_failure_annotation(today: str, status: str, error: str = "") -> None:
    extra = f" error={error}" if error else ""
    print(
        f"::error::Today's daily brief (Shanghai {today}) status={status}{extra}",
        file=sys.stderr,
    )


def today_status_payload(
    *,
    today: str,
    status: str,
    error: str = "",
    ok: bool | None = None,
) -> dict:
    resolved_ok = today_status_is_success(status) if ok is None else ok
    return {
        "date": today,
        "status": status,
        "error": error or "",
        "ok": resolved_ok,
    }


def record_today_status(
    *,
    today: str,
    status: str,
    error: str = "",
    status_path: Path | None = None,
    ok: bool | None = None,
) -> dict:
    payload = today_status_payload(
        today=today, status=status, error=error, ok=ok
    )
    if status_path is not None:
        write_today_status_file(status_path, payload)
    append_github_output(today, status)
    return payload


def evaluate_today_exit(
    *,
    today: str,
    dates: list[str],
    results: list[dict],
    fatal_error: str | None,
) -> tuple[int, str, str]:
    """Return (exit_code, today_status, error). Older-only runs stay 0."""
    if today not in dates:
        return 0, "not_requested", ""
    if fatal_error:
        return 1, "missing", fatal_error
    for row in results:
        if row.get("date") != today:
            continue
        status = str(row.get("status") or "missing")
        error = str(row.get("error") or "")
        if today_status_is_success(status):
            return 0, status, error
        return 1, status, error
    return 1, "missing", ""


def generate_for_dates(
    store: Store,
    dates: list[str],
    *,
    llm_fn=None,
    model: str | None = None,
    missing_config: bool | None = None,
    deadline_s: float | None = None,
    monotonic=time.monotonic,
    sleep=time.sleep,
    today: str | None = None,
    today_attempts: int = TODAY_LLM_ATTEMPTS,
    older_attempts: int = OLDER_LLM_ATTEMPTS,
    retry_backoff_s: float = LLM_RETRY_BACKOFF_S,
    status_path: Path | None = None,
) -> list[dict]:
    """Generate briefs for dates. Missing key / LLM errors write failed/empty.

    Skip LLM (`kept_ok`) when an existing row is status=ok — historical
    ok days are never regenerated (only fill failed/missing/empty).
    Today may refresh when the RSS+X fingerprint changed, but a failed
    or empty result must not overwrite that ok row.

    Today is generated first, with retries on transient LKEAP errors.
    Then failed/empty/missing historical days are backfilled (one-shot)
    before already-ok days. If `deadline_s` elapses, remaining dates are
    skipped without upsert; an existing ok brief stays ok.

    Never writes mock/ok content to hide a failure.
    """
    today = today or shanghai_calendar_date()

    def _existing_status(date: str) -> str | None:
        row = store.get_daily_brief(date)
        if row is None:
            return None
        status = row.get("status")
        return str(status) if status else None

    dates = prioritize_failed_backfill(list(dates), today, _existing_status)
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

    def _note_today(status: str, error: str = "") -> None:
        if status_path is None and not os.environ.get("GITHUB_OUTPUT"):
            return
        record_today_status(
            today=today, status=status, error=error, status_path=status_path
        )

    def _skip_remaining(start_date: str) -> None:
        print(
            f"⚠ daily brief deadline ({deadline_s:.0f}s) reached; "
            f"skipping remaining days starting {start_date}",
            file=sys.stderr,
        )
        remaining = dates[dates.index(start_date) :]
        for skipped in remaining:
            existing_ok = store.get_daily_brief(skipped)
            if existing_ok and existing_ok.get("status") == "ok":
                results.append(
                    {
                        "date": skipped,
                        "action": "kept_ok",
                        "status": "ok",
                    }
                )
                if skipped == today:
                    _note_today("ok")
                continue
            results.append(
                {
                    "date": skipped,
                    "action": "skipped_deadline",
                    "status": "skipped",
                    "error": "daily brief deadline reached; skipped remaining days",
                }
            )
        if today in remaining:
            today_row = next(r for r in results if r.get("date") == today)
            if today_row.get("status") != "ok":
                _note_today(
                    "skipped",
                    "daily brief deadline reached; skipped remaining days",
                )

    for date in dates:
        if deadline_at is not None and monotonic() >= deadline_at:
            _skip_remaining(date)
            break
        fingerprint = day_input_fingerprint(articles, date, x_posts)
        existing = store.get_daily_brief(date)
        existing_ok = bool(existing and existing.get("status") == "ok")
        same_fp = (
            existing_ok
            and (existing.get("input_fingerprint") or "") == fingerprint
        )
        # Historical ok: only fill failed/missing. Today ok + same fingerprint:
        # skip. Today ok + changed fingerprint: try refresh, never clobber.
        if existing_ok and (same_fp or date != today):
            results.append(
                {
                    "date": date,
                    "action": "kept_ok",
                    "status": "ok",
                }
            )
            if date == today:
                _note_today("ok")
            continue

        attempts = today_attempts if date == today else older_attempts
        if missing_config:
            attempts = 1
        attempts = max(1, attempts)
        brief = None
        for attempt in range(1, attempts + 1):
            if deadline_at is not None and monotonic() >= deadline_at:
                if brief is None:
                    _skip_remaining(date)
                    brief = None
                break
            try:
                brief = generate_daily_brief(
                    articles,
                    date,
                    x_posts=x_posts,
                    llm_fn=llm_fn,
                    model=model,
                    missing_config=missing_config,
                )
            except Exception as exc:  # never invent ok content
                brief = _failed_row(
                    date,
                    model=model,
                    fingerprint=fingerprint,
                    error=redact_secrets(str(exc), api_key),
                )
            if brief.get("status") != "failed":
                break
            error = brief.get("error") or ""
            if (
                attempt < attempts
                and date == today
                and is_retryable_llm_error(error)
            ):
                print(
                    f"⚠ daily brief {date} attempt {attempt}/{attempts} "
                    f"failed; retrying: {redact_secrets(error, api_key)}",
                    file=sys.stderr,
                )
                if retry_backoff_s > 0:
                    sleep(retry_backoff_s * attempt)
                continue
            break

        if brief is None:
            break
        if existing_ok and brief.get("status") != "ok":
            print(
                f"⚠ daily brief {date} failed after ok; keeping existing ok "
                f"({redact_secrets(brief.get('error') or '', api_key)})",
                file=sys.stderr,
            )
            results.append(
                {
                    "date": date,
                    "action": "kept_ok",
                    "status": "ok",
                    "error": redact_secrets(brief.get("error") or "", api_key),
                }
            )
            if date == today:
                _note_today("ok")
            continue
        action = store.upsert_daily_brief(brief)
        row = {
            "date": date,
            "action": action,
            "status": brief["status"],
            "error": redact_secrets(brief.get("error") or "", api_key),
            "model": brief.get("model") or "",
        }
        results.append(row)
        if date == today:
            _note_today(brief["status"], row.get("error") or "")
    return results


def _load_status_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def run_check_today(args: argparse.Namespace) -> int:
    """Hard-fail if the current Shanghai day's brief is failed or missing."""
    today = shanghai_calendar_date()
    payload = None
    if args.status_file:
        payload = _load_status_file(args.status_file)
    if payload is None and args.db and Path(args.db).exists():
        try:
            store = Store(args.db)
            row = store.get_daily_brief(today)
            store.close()
        except Exception as exc:
            print(
                f"⚠ daily brief check-today could not read db: "
                f"{redact_secrets(str(exc))}",
                file=sys.stderr,
            )
            row = None
        if row:
            payload = today_status_payload(
                today=today,
                status=str(row.get("status") or "missing"),
                error=str(row.get("error") or ""),
            )
    status = str((payload or {}).get("status") or "missing")
    date = str((payload or {}).get("date") or today)
    error = str((payload or {}).get("error") or "")
    if today_status_is_success(status):
        print(f"daily-brief check-today date={date} status={status}")
        return 0
    emit_today_failure_annotation(date, status, error)
    print(f"daily-brief check-today date={date} status={status}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Shanghai-calendar daily briefs. Today failed/missing "
            "exits non-zero; older days remain soft-fail."
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
        "--days",
        type=int,
        default=7,
        help="How many Shanghai calendar days to cover (default 7).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON stats")
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=0,
        help="Wall-clock budget; remaining older days skip without failing today.",
    )
    parser.add_argument(
        "--write-status",
        type=Path,
        default=None,
        help="Write today's status JSON as soon as today is generated.",
    )
    parser.add_argument(
        "--check-today",
        action="store_true",
        help="Exit 1 if today's Shanghai brief is failed or missing. No generate.",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help="Status JSON written by --write-status (used with --check-today).",
    )
    args = parser.parse_args(argv)

    if args.check_today:
        return run_check_today(args)

    today = shanghai_calendar_date()
    dates = [args.date] if args.date else last_n_shanghai_dates(max(1, args.days))
    stats: dict = {
        "ok": False,
        "secret_names": [API_KEY_ENV, API_BASE_ENV],
        "config_present": resolve_llm_config() is not None,
        "today": today,
        "today_status": None,
        "results": [],
        "error": None,
    }
    try:
        store = Store(args.db)
        stats["results"] = generate_for_dates(
            store,
            dates,
            deadline_s=args.deadline_seconds,
            status_path=args.write_status,
            today=today,
        )
        store.close()
    except Exception as exc:
        stats["error"] = redact_secrets(str(exc))
        print(f"⚠ daily brief soft-fail: {stats['error']}", file=sys.stderr)

    exit_code, today_status, today_error = evaluate_today_exit(
        today=today,
        dates=dates,
        results=stats["results"],
        fatal_error=stats["error"],
    )
    stats["today_status"] = today_status
    stats["ok"] = exit_code == 0
    record_today_status(
        today=today,
        status=today_status,
        error=today_error or (stats["error"] or ""),
        status_path=args.write_status,
        ok=stats["ok"],
    )

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        if stats["error"]:
            print(f"daily-brief error={stats['error']}")
        for row in stats["results"]:
            extra = f" error={row['error']}" if row.get("error") else ""
            print(
                f"daily-brief {row['date']} status={row['status']} "
                f"action={row['action']}{extra}"
            )
        if not stats["config_present"]:
            print(
                f"⚠ {API_KEY_ENV} or {API_BASE_ENV} missing — wrote failed/empty; "
                f"today exits non-zero",
                file=sys.stderr,
            )

    if exit_code != 0:
        emit_today_failure_annotation(
            today, today_status, today_error or (stats["error"] or "")
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
