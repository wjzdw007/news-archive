"""P0 acceptance validation for news archive CI."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sources import SOURCES


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO-8601 datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        # Handle various ISO formats
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except (ValueError, AttributeError):
        return None


def check_duplicate_urls(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Check for duplicate URLs in database.
    
    Returns (passed, message).
    """
    cursor = conn.execute(
        "SELECT url, COUNT(*) as cnt FROM articles GROUP BY url HAVING cnt > 1"
    )
    duplicates = cursor.fetchall()
    
    if duplicates:
        urls = [row[0] for row in duplicates[:5]]  # Show first 5
        msg = f"FAIL: Found {len(duplicates)} duplicate URLs. Examples: {urls}"
        return False, msg
    
    return True, "PASS: No duplicate URLs found"


def check_required_fields(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Check required fields are non-null/non-empty for active articles.
    
    Required fields: title, url, source, fetched_at, status.
    content_snapshot can fall back to summary - treat both empty as bad.
    
    Returns (passed, message).
    """
    total = conn.execute("SELECT COUNT(*) FROM articles WHERE status='active'").fetchone()[0]
    
    if total == 0:
        return True, "PASS: No active articles to check"
    
    # Check each required field
    required_fields = ["title", "url", "source", "fetched_at", "status"]
    failures = []
    
    for field in required_fields:
        null_count = conn.execute(
            f"SELECT COUNT(*) FROM articles WHERE status='active' AND ({field} IS NULL OR {field} = '')"
        ).fetchone()[0]
        
        if null_count > 0:
            rate = (null_count / total) * 100
            # Zero tolerance for these critical fields
            failures.append(f"{field}: {null_count}/{total} ({rate:.1f}%) null/empty")
    
    # Special check for content_snapshot: allow empty only if summary exists
    empty_content = conn.execute(
        """
        SELECT COUNT(*) FROM articles 
        WHERE status='active' 
          AND (content_snapshot IS NULL OR content_snapshot = '')
          AND (summary IS NULL OR summary = '')
        """
    ).fetchone()[0]
    
    if empty_content > 0:
        rate = (empty_content / total) * 100
        failures.append(f"content_snapshot+summary both empty: {empty_content}/{total} ({rate:.1f}%)")
    
    if failures:
        msg = "FAIL: Required field validation failed:\n  " + "\n  ".join(failures)
        return False, msg
    
    return True, f"PASS: All required fields populated for {total} active articles"


def check_source_incremental(
    conn: sqlite3.Connection,
    run_stats: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check that sources are producing content.
    
    Fail if:
    - Any source had a fetch error (from run_stats)
    - Overall DB is empty
    - Zero inserts this run AND any source returned 0 items
    
    Returns (passed, message).
    """
    # Check for source errors from run stats
    if run_stats and run_stats.get("errors"):
        errors = run_stats["errors"]
        msg = f"FAIL: {len(errors)} source(s) had fetch errors: {list(errors.keys())}"
        return False, msg
    
    # Check overall DB not empty
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if total == 0:
        return False, "FAIL: Archive database is completely empty"
    
    # Check this run had inserts or all sources have existing articles
    if run_stats:
        inserted = run_stats.get("inserted", 0)
        sources_data = run_stats.get("sources", {})
        
        if inserted == 0:
            # Zero inserts this run - check if any source returned 0 items
            zero_sources = [
                sid for sid, data in sources_data.items()
                if data.get("fetched", 0) == 0
            ]
            if zero_sources:
                msg = f"FAIL: 0 articles inserted this run and {len(zero_sources)} source(s) returned 0 items: {zero_sources}"
                return False, msg
    
    # Check per-source: each configured source should have at least some articles
    source_ids = {s.id for s in SOURCES}
    db_counts = {}
    for source_id in source_ids:
        count = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE source = ?", (source_id,)
        ).fetchone()[0]
        db_counts[source_id] = count
    
    empty_sources = [sid for sid, count in db_counts.items() if count == 0]
    
    if empty_sources:
        msg = f"FAIL: {len(empty_sources)} configured source(s) have 0 total articles in DB: {empty_sources}"
        return False, msg
    
    return True, f"PASS: All {len(source_ids)} sources have content. Total articles: {total}"


def check_fetch_latency(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Check fetch latency SLA: published_at → fetched_at should be ≤ 4 hours.
    
    Strategy: Check articles fetched in the last 6 hours (this run window + buffer).
    Fail if >10% of articles with parseable published_at exceed 4h latency.
    Exclude articles >24h old at fetch time (likely republished content).
    
    Returns (passed, message).
    """
    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=now.hour - 6, minute=0, second=0, microsecond=0)
    
    cursor = conn.execute(
        """
        SELECT published_at, fetched_at 
        FROM articles 
        WHERE fetched_at >= ? 
          AND published_at IS NOT NULL 
          AND published_at != ''
        """,
        (window_start.isoformat(),),
    )
    
    rows = cursor.fetchall()
    
    if not rows:
        return True, "PASS: No recent articles with published_at to check"
    
    violations = []
    parse_errors = 0
    skipped_old = 0
    
    for row in rows:
        pub_at = parse_iso_datetime(row[0])
        fetch_at = parse_iso_datetime(row[1])
        
        if not pub_at or not fetch_at:
            parse_errors += 1
            continue
        
        # Skip articles that were >24h old when fetched (republished content)
        age_at_fetch = (fetch_at - pub_at).total_seconds() / 3600
        if age_at_fetch > 24:
            skipped_old += 1
            continue
        
        # Check 4-hour SLA
        if age_at_fetch > 4.0:
            violations.append((row[0], row[1], age_at_fetch))
    
    checked = len(rows) - parse_errors - skipped_old
    if checked == 0:
        return True, "PASS: No recent articles to check for latency"
    
    violation_rate = (len(violations) / checked) * 100
    
    # Fail if >10% exceed SLA
    if violation_rate > 10.0:
        # Show worst 3 violations
        worst = sorted(violations, key=lambda x: x[2], reverse=True)[:3]
        examples = [f"{pub} → {fetch} ({lat:.1f}h)" for pub, fetch, lat in worst]
        msg = (
            f"FAIL: {len(violations)}/{checked} ({violation_rate:.1f}%) articles "
            f"exceed 4h SLA. Examples:\n  " + "\n  ".join(examples)
        )
        return False, msg
    
    msg = (
        f"PASS: {checked - len(violations)}/{checked} articles within 4h SLA. "
        f"{len(violations)} violations ({violation_rate:.1f}%) below 10% threshold."
    )
    if skipped_old:
        msg += f" Skipped {skipped_old} republished (>24h old at fetch)."
    
    return True, msg


def validate(
    db_path: Path,
    stats_path: Path | None = None,
) -> int:
    """Run all P0 acceptance checks.
    
    Returns 0 on success, 1 on failure.
    """
    if not db_path.exists():
        print("FAIL: Database file does not exist:", db_path, file=sys.stderr)
        return 1
    
    conn = sqlite3.connect(db_path)
    
    run_stats = None
    if stats_path and stats_path.exists():
        try:
            run_stats = json.loads(stats_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not parse stats file: {e}", file=sys.stderr)
    
    checks = [
        ("Duplicate URLs", lambda: check_duplicate_urls(conn)),
        ("Required Fields", lambda: check_required_fields(conn)),
        ("Source Incremental", lambda: check_source_incremental(conn, run_stats)),
        ("Fetch Latency SLA", lambda: check_fetch_latency(conn)),
    ]
    
    results = []
    all_passed = True
    
    print("=== P0 Acceptance Validation ===\n")
    
    for name, check_fn in checks:
        passed, message = check_fn()
        results.append((name, passed, message))
        all_passed = all_passed and passed
        
        status = "✓" if passed else "✗"
        print(f"[{status}] {name}")
        print(f"    {message}\n")
    
    conn.close()
    
    if all_passed:
        print("=== All P0 acceptance checks PASSED ===")
        return 0
    else:
        failed = [name for name, passed, _ in results if not passed]
        print(f"=== FAILED {len(failed)} check(s): {', '.join(failed)} ===", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate P0 acceptance criteria")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/archive.sqlite3"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--stats",
        type=Path,
        default=Path("data/run-stats.json"),
        help="Optional run stats JSON for source checks",
    )
    
    args = parser.parse_args(argv)
    return validate(args.db, args.stats)


if __name__ == "__main__":
    raise SystemExit(main())
