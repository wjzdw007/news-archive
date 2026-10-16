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


def _latency_skip_details(
    skipped_no_published: int,
    skipped_parse_error: int,
    skipped_old: int,
    skipped_first_ingest: int,
) -> list[str]:
    """Human-readable skip counts for latency SLA messages."""
    details: list[str] = []
    if skipped_no_published:
        details.append(f"{skipped_no_published} no published_at")
    if skipped_parse_error:
        details.append(f"{skipped_parse_error} parse errors")
    if skipped_old:
        details.append(f"{skipped_old} republished (>24h old)")
    if skipped_first_ingest:
        details.append(f"{skipped_first_ingest} first-ingest backfill")
    return details


def check_fetch_latency(
    conn: sqlite3.Connection,
    run_stats: dict[str, Any] | None = None,
    previous_run_meta: dict[str, Any] | None = None,
) -> tuple[bool, str, bool]:
    """Check fetch latency SLA: published_at → fetched_at should be ≤ 4 hours.
    
    Strategy: Check only articles inserted during THIS run (incremental inserts).
    Identifies this run's articles by finding the most recent fetched_at timestamp.
    Fail if >10% of articles with parseable published_at exceed 4h latency.
    
    Consecutive failure policy:
    - Single round or small violation count → WARN (soft), return True
    - TWO consecutive rounds both failed → FAIL (hard), return False
    - Soft WARN still returns sla_violated=True so LAST_RUN records
      latency_sla_passed=false; a second genuine violation then hard-fails.
    
    Rationale: First-run backfills of old stock items (e.g., week-old RSS feeds)
    would show high latency by design. We only measure freshness on new incremental
    content, not historical imports. Brand-new sources are the same class of
    backfill: if a source has no row with fetched_at older than this run's
    latest_fetch_at, those first-ingest articles are excluded from the SLA
    denominator (same spirit as the >24h skip). Established sources keep the
    4h / >10% / consecutive policy unchanged.
    
    Returns (passed, message, sla_violated).
    - passed: whether to pass this check (may be True even if SLA violated, for single round)
    - message: human-readable result
    - sla_violated: whether >10% threshold was actually exceeded (for metadata tracking)
    """
    # Determine if this run inserted any articles
    inserted = run_stats.get("inserted", 0) if run_stats else 0
    
    if inserted == 0:
        return True, "PASS: No new articles inserted this run (nothing to check)", False
    
    # Find the most recent fetched_at timestamp (this run's batch)
    latest_fetch_cursor = conn.execute(
        "SELECT MAX(fetched_at) FROM articles"
    )
    latest_fetch_at = latest_fetch_cursor.fetchone()[0]
    
    if not latest_fetch_at:
        return True, "PASS: No articles in database", False
    
    # Query articles from this run's batch only
    cursor = conn.execute(
        """
        SELECT published_at, fetched_at, url, source
        FROM articles 
        WHERE fetched_at = ?
        """,
        (latest_fetch_at,),
    )
    
    rows = cursor.fetchall()
    
    if not rows:
        return True, "PASS: No articles from this run to check", False
    
    # A source is first-ingest this run if it has no row older than this batch.
    first_ingest_sources = {
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT a.source
            FROM articles a
            WHERE a.fetched_at = ?
              AND NOT EXISTS (
                  SELECT 1 FROM articles b
                  WHERE b.source = a.source
                    AND b.fetched_at < ?
              )
            """,
            (latest_fetch_at, latest_fetch_at),
        )
    }
    
    violations = []
    skipped_no_published = 0
    skipped_parse_error = 0
    skipped_old = 0
    skipped_first_ingest = 0
    
    for row in rows:
        # Brand-new source first ingest = backfill; exclude from SLA denominator.
        if row[3] in first_ingest_sources:
            skipped_first_ingest += 1
            continue
        
        # Skip if published_at is missing (don't count as failure)
        if not row[0] or row[0].strip() == "":
            skipped_no_published += 1
            continue
        
        pub_at = parse_iso_datetime(row[0])
        fetch_at = parse_iso_datetime(row[1])
        
        # Skip if parse failed (don't count as failure)
        if not pub_at or not fetch_at:
            skipped_parse_error += 1
            continue
        
        # Skip articles that were >24h old when fetched (republished content)
        age_at_fetch = (fetch_at - pub_at).total_seconds() / 3600
        if age_at_fetch > 24:
            skipped_old += 1
            continue
        
        # Check 4-hour SLA
        if age_at_fetch > 4.0:
            violations.append((row[0], row[1], age_at_fetch, row[2]))
    
    checked = (
        len(rows)
        - skipped_no_published
        - skipped_parse_error
        - skipped_old
        - skipped_first_ingest
    )
    skip_details = _latency_skip_details(
        skipped_no_published,
        skipped_parse_error,
        skipped_old,
        skipped_first_ingest,
    )
    inline_skip = f" Skipped: {', '.join(skip_details)}." if skip_details else ""
    block_skip = f"\n  Skipped: {', '.join(skip_details)}." if skip_details else ""
    
    if checked == 0:
        skip_msg = ", ".join(skip_details) if skip_details else "nothing checkable"
        return True, f"PASS: No checkable articles this run ({skip_msg})", False
    
    violation_rate = (len(violations) / checked) * 100
    
    # Check if >10% exceed SLA
    if violation_rate > 10.0:
        # Show worst 3 violations
        worst = sorted(violations, key=lambda x: x[2], reverse=True)[:3]
        examples = [
            f"{pub} → {fetch} ({lat:.1f}h) [{url}]"
            for pub, fetch, lat, url in worst
        ]
        
        # Check consecutive failure: did previous run also fail latency?
        prev_failed = (
            previous_run_meta 
            and previous_run_meta.get("latency_sla_passed") is False
        )
        
        if prev_failed:
            # TWO consecutive rounds failed → FAIL (hard)
            msg = (
                f"FAIL: TWO CONSECUTIVE ROUNDS exceeded latency SLA.\n"
                f"  This run: {len(violations)}/{checked} ({violation_rate:.1f}%) articles exceed 4h.\n"
                f"  Previous run also failed latency check.\n"
                f"  Examples from this run:\n    " + "\n    ".join(examples)
                + block_skip
            )
            return False, msg, True  # Failed, and SLA violated
        else:
            # Single round failure → WARN (soft), do not fail.
            # sla_violated remains True so a second real violation hard-fails.
            msg = (
                f"WARN: {len(violations)}/{checked} ({violation_rate:.1f}%) articles "
                f"from this run exceed 4h SLA. Examples:\n  " + "\n  ".join(examples) +
                f"\n  ⚠ Single-round violation (not consecutive) - NOT failing the run."
                + block_skip
            )
            print(f"\n{'='*60}", file=sys.stderr)
            print("WARNING: Latency SLA violated but NOT failing (single round)", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            return True, msg, True  # Soft pass, but SLA violated
    
    msg = (
        f"PASS: {checked - len(violations)}/{checked} articles within 4h SLA. "
        f"{len(violations)} violations ({violation_rate:.1f}%) below 10% threshold."
        + inline_skip
    )
    
    return True, msg, False  # Passed, SLA not violated


def load_previous_run_meta() -> dict[str, Any] | None:
    """Try to load previous run metadata from data branch LAST_RUN.json.
    
    Returns None if not available or parse fails.
    """
    try:
        # Try git show to read from data branch without checking it out
        import subprocess
        result = subprocess.run(
            ["git", "show", "data:data/LAST_RUN.json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"Info: Could not load previous run meta from data branch: {e}", file=sys.stderr)
    return None


def validate(
    db_path: Path,
    stats_path: Path | None = None,
    output_meta_path: Path | None = None,
) -> int:
    """Run all P0 acceptance checks.
    
    Returns 0 on success, 1 on failure.
    
    If output_meta_path is provided, writes validation metadata JSON including
    latency_sla_passed for use by next run's consecutive check.
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
    
    # Load previous run metadata for consecutive latency check
    previous_run_meta = load_previous_run_meta()
    
    # Run checks: regular checks return (passed, message), latency returns (passed, message, sla_violated)
    regular_checks = [
        ("Duplicate URLs", lambda: check_duplicate_urls(conn)),
        ("Required Fields", lambda: check_required_fields(conn)),
        ("Source Incremental", lambda: check_source_incremental(conn, run_stats)),
    ]
    
    results = []
    all_passed = True
    latency_sla_passed = True  # Track for output meta
    
    print("=== P0 Acceptance Validation ===\n")
    
    # Run regular checks
    for name, check_fn in regular_checks:
        passed, message = check_fn()
        results.append((name, passed, message))
        all_passed = all_passed and passed
        
        status = "✓" if passed else "✗"
        print(f"[{status}] {name}")
        print(f"    {message}\n")
    
    # Run latency check (returns 3-tuple)
    latency_passed, latency_message, sla_violated = check_fetch_latency(conn, run_stats, previous_run_meta)
    results.append(("Fetch Latency SLA", latency_passed, latency_message))
    all_passed = all_passed and latency_passed
    # Intentional: soft WARN still stores false so the next real violation hard-fails.
    latency_sla_passed = not sla_violated  # True if SLA not violated
    
    status = "✓" if latency_passed else "✗"
    print(f"[{status}] Fetch Latency SLA")
    print(f"    {latency_message}\n")
    
    conn.close()
    
    # Write validation metadata for next run's consecutive check
    if output_meta_path:
        try:
            meta = {
                "latency_sla_passed": latency_sla_passed,
                "all_checks_passed": all_passed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            output_meta_path.write_text(json.dumps(meta, indent=2))
        except Exception as e:
            print(f"Warning: Could not write validation meta: {e}", file=sys.stderr)
    
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
    parser.add_argument(
        "--output-meta",
        type=Path,
        help="Output validation metadata JSON (for consecutive latency check)",
    )
    
    args = parser.parse_args(argv)
    return validate(args.db, args.stats, args.output_meta)


if __name__ == "__main__":
    raise SystemExit(main())
