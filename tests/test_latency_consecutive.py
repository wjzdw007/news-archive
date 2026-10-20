"""Test latency SLA consecutive failure detection."""

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_archive.sources import SOURCES
from news_archive.validate import check_fetch_latency, previous_run_had_latency_miss


def _insert_article(
    conn: sqlite3.Connection,
    *,
    url: str,
    title: str,
    published_at: str,
    fetched_at: str,
    source: str,
) -> None:
    conn.execute(
        """
        INSERT INTO articles (url, title, published_at, fetched_at, source, summary, content_snapshot, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (url, title, published_at, fetched_at, source, "Summary", "Content", "active"),
    )


def create_test_db_with_violations(
    db_path: Path,
    violation_hours: list[float],
    *,
    source: str = "test_source",
    established: bool = True,
    extra_this_run: list[tuple[float, str]] | None = None,
) -> None:
    """Create a test database with articles that have specified latency violations.
    
    Args:
        db_path: Path to create the SQLite database
        violation_hours: List of hours for each article's latency (e.g., [8.5, 9.0, 2.0])
        source: Source id for the primary this-run batch
        established: If True, seed a prior row so `source` is not first-ingest
        extra_this_run: Additional (hours, source_id) rows sharing this run's fetched_at
    """
    conn = sqlite3.connect(db_path)
    
    # Create schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            summary TEXT,
            content_snapshot TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    
    # Use a fixed fetched_at time for all articles
    fetched_at = datetime.now(timezone.utc)
    fetched_at_str = fetched_at.isoformat()
    old_fetched_at = fetched_at - timedelta(days=1)
    
    # Insert articles with specified latency
    for i, hours in enumerate(violation_hours):
        published_at = fetched_at - timedelta(hours=hours)
        _insert_article(
            conn,
            url=f"https://example.com/article-{i}",
            title=f"Test Article {i}",
            published_at=published_at.isoformat(),
            fetched_at=fetched_at_str,
            source=source,
        )
    
    if extra_this_run:
        for i, (hours, extra_source) in enumerate(extra_this_run):
            published_at = fetched_at - timedelta(hours=hours)
            _insert_article(
                conn,
                url=f"https://example.com/extra-{extra_source}-{i}",
                title=f"Extra {extra_source} Article {i}",
                published_at=published_at.isoformat(),
                fetched_at=fetched_at_str,
                source=extra_source,
            )
    
    if established:
        # Prior row so this source is established (not first-ingest backfill)
        prior_published = old_fetched_at - timedelta(hours=2)
        _insert_article(
            conn,
            url=f"https://example.com/prior-{source}",
            title=f"Prior {source} Article",
            published_at=prior_published.isoformat(),
            fetched_at=old_fetched_at.isoformat(),
            source=source,
        )
    
    # Add at least one article for each configured source to pass Source Incremental check
    sources = [s.id for s in SOURCES]
    for j, configured_source in enumerate(sources):
        # Use older fetched_at so they don't interfere with latency check
        old_published_at = old_fetched_at - timedelta(hours=2)
        _insert_article(
            conn,
            url=f"https://example.com/old-{configured_source}-{j}",
            title=f"Old {configured_source} Article",
            published_at=old_published_at.isoformat(),
            fetched_at=old_fetched_at.isoformat(),
            source=configured_source,
        )
    
    conn.commit()
    conn.close()


def create_stats_json(stats_path: Path, inserted: int) -> None:
    """Create a test run stats JSON file."""
    stats = {
        "inserted": inserted,
        "updated": 0,
        "seen": inserted,
        "sources": {
            "test_source": {
                "fetched": inserted,
                "inserted": inserted,
            }
        },
        "errors": {},
    }
    stats_path.write_text(json.dumps(stats, indent=2))


def setup_git_with_last_run(
    git_dir: Path,
    latency_passed: bool,
    *,
    soft_miss: bool | None = None,
) -> None:
    """Set up a git repo with a data branch containing LAST_RUN.json."""
    subprocess.run(["git", "init"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "--orphan", "data"], cwd=git_dir, check=True, capture_output=True)
    
    data_dir = git_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    last_run = {
        "run_id": "test-12345",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_sla_passed": latency_passed,
    }
    if soft_miss is not None:
        last_run["latency_soft_miss"] = soft_miss
    (data_dir / "LAST_RUN.json").write_text(json.dumps(last_run, indent=2))
    
    subprocess.run(["git", "add", "data/LAST_RUN.json"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Previous run"], cwd=git_dir, check=True, capture_output=True)


def test_single_round_violation():
    """Test single round violation: should WARN but pass."""
    print("\n" + "="*70)
    print("TEST 1: Single Round Violation (should WARN but pass)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Set up git repo with previous run that PASSED
        setup_git_with_last_run(tmpdir, latency_passed=True)
        
        # Create DB with 15% violations (>10% threshold)
        # 15 articles: 13 within 4h, 2 violate (8.5h and 9h)
        db_path = tmpdir / "test.sqlite3"
        violations = [8.5, 9.0] + [2.0] * 13  # 2 violations, 13 ok
        create_test_db_with_violations(db_path, violations)
        
        # Create stats
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(violations))
        
        # Create output meta path
        meta_path = tmpdir / "validation-meta.json"
        
        # Run validation
        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")
        
        # Check exit code (should be 0 - soft pass)
        assert result.returncode == 0, f"Expected exit 0 (soft pass), got {result.returncode}"
        
        # Check that WARN is in output
        assert "WARN:" in result.stdout, "Expected WARN message in output"
        assert "Single-round violation" in result.stdout, "Expected single-round message"
        
        # Check metadata: one soft miss must not red persist / arm via passed=false
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is True, (
            "Single soft miss must keep latency_sla_passed=true (job green on persist)"
        )
        assert meta["latency_soft_miss"] is True, (
            "Single large-N miss must set latency_soft_miss so the next miss can consecutive-fail"
        )
        
        print("\n✓ TEST 1 PASSED: Single round violation warned but did not fail")


def test_consecutive_violation():
    """Test consecutive violation: should FAIL."""
    print("\n" + "="*70)
    print("TEST 2: Consecutive Violation (should FAIL)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Set up git repo with previous run that FAILED
        setup_git_with_last_run(tmpdir, latency_passed=False)
        
        # Create DB with 15% violations (>10% threshold)
        db_path = tmpdir / "test.sqlite3"
        violations = [8.5, 9.0] + [2.0] * 13  # 2 violations, 13 ok
        create_test_db_with_violations(db_path, violations)
        
        # Create stats
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(violations))
        
        # Create output meta path
        meta_path = tmpdir / "validation-meta.json"
        
        # Run validation
        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")
        
        # Check exit code (should be 1 - hard fail)
        assert result.returncode == 1, f"Expected exit 1 (hard fail), got {result.returncode}"
        
        # Check that FAIL and CONSECUTIVE are in output
        assert "FAIL:" in result.stdout or "FAIL:" in result.stderr, "Expected FAIL message"
        assert "TWO CONSECUTIVE ROUNDS" in result.stdout or "TWO CONSECUTIVE ROUNDS" in result.stderr, "Expected consecutive message"
        
        # Check metadata
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is False, "Expected latency_sla_passed=false in metadata"
        assert meta["latency_soft_miss"] is True
        
        print("\n✓ TEST 2 PASSED: Consecutive violation caused hard failure")


def test_pass_after_previous_failure():
    """Test pass after previous failure: should PASS and reset."""
    print("\n" + "="*70)
    print("TEST 3: Pass After Previous Failure (should PASS and reset)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Set up git repo with previous run that FAILED
        setup_git_with_last_run(tmpdir, latency_passed=False)
        
        # Create DB with NO violations (all within 4h)
        db_path = tmpdir / "test.sqlite3"
        violations = [2.0] * 15  # All ok
        create_test_db_with_violations(db_path, violations)
        
        # Create stats
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(violations))
        
        # Create output meta path
        meta_path = tmpdir / "validation-meta.json"
        
        # Run validation
        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")
        
        # Check exit code (should be 0 - pass)
        assert result.returncode == 0, f"Expected exit 0 (pass), got {result.returncode}"
        
        # Check that PASS is in output
        assert "PASS:" in result.stdout, "Expected PASS message"
        assert "WARN:" not in result.stdout, "Should not have WARN for passing run"
        
        # Check metadata
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is True, "Expected latency_sla_passed=true in metadata"
        assert meta["latency_soft_miss"] is False
        
        print("\n✓ TEST 3 PASSED: Passed after previous failure, reset consecutive count")


def test_new_source_first_ingest_not_hard_fail():
    """New-source first ingest in the 4–24h window must not hard-fail SLA."""
    print("\n" + "="*70)
    print("TEST 4: New source first-ingest 4-24h stock (should PASS, not hard-fail)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Prior run failed — the incident pattern (soft WARN then new-source backfill)
        setup_git_with_last_run(tmpdir, latency_passed=False)
        
        db_path = tmpdir / "test.sqlite3"
        # 13 articles aged ~17h: would be 100% SLA violations if counted
        first_ingest_hours = [17.0 + (i * 0.1) for i in range(13)]
        create_test_db_with_violations(
            db_path,
            first_ingest_hours,
            source="new_rss_source",
            established=False,
        )
        
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(first_ingest_hours))
        meta_path = tmpdir / "validation-meta.json"
        
        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")
        
        assert result.returncode == 0, (
            f"Expected exit 0 (new-source backfill skipped), got {result.returncode}"
        )
        assert "TWO CONSECUTIVE ROUNDS" not in result.stdout
        assert "TWO CONSECUTIVE ROUNDS" not in result.stderr
        combined = result.stdout + result.stderr
        assert "first-ingest backfill" in combined, "Expected first-ingest skip in message"
        assert "13 first-ingest backfill" in combined
        
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is True, (
            "First-ingest-only backfill must not mark latency_sla_passed=false"
        )
        assert meta["latency_soft_miss"] is False
        
        print("\n✓ TEST 4 PASSED: New source first-ingest skipped, did not hard-fail")


def test_new_source_does_not_mask_established_consecutive_fail():
    """Established-source consecutive violations still hard-fail beside new-source stock."""
    print("\n" + "="*70)
    print("TEST 5: Established consecutive violations still FAIL (new-source stock ignored)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        setup_git_with_last_run(tmpdir, latency_passed=False)
        
        db_path = tmpdir / "test.sqlite3"
        established_hours = [8.5, 9.0] + [2.0] * 13  # 2/15 = 13.3% > 10%
        new_source_hours = [(17.5, "new_rss_source")] * 13
        create_test_db_with_violations(
            db_path,
            established_hours,
            source="test_source",
            established=True,
            extra_this_run=new_source_hours,
        )
        
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(established_hours) + len(new_source_hours))
        meta_path = tmpdir / "validation-meta.json"
        
        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")
        
        assert result.returncode == 1, (
            f"Expected exit 1 (established consecutive fail), got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "TWO CONSECUTIVE ROUNDS" in combined
        assert "13 first-ingest backfill" in combined, "New-source rows should still be skipped"
        # Denominator is established rows only (15), not 15+13
        assert "2/15" in combined
        
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is False
        assert meta["latency_soft_miss"] is True
        
        print("\n✓ TEST 5 PASSED: Established consecutive fail unchanged by new-source stock")


def _assert_latency_check(
    db_path: Path,
    *,
    inserted: int,
    prev_passed: bool,
) -> tuple[bool, str, bool]:
    """Call check_fetch_latency directly (unit, no CLI / git)."""
    conn = sqlite3.connect(db_path)
    try:
        return check_fetch_latency(
            conn,
            run_stats={"inserted": inserted},
            previous_run_meta={"latency_sla_passed": prev_passed},
        )
    finally:
        conn.close()


def test_small_sample_prev_failed_is_soft_warn():
    """checked=3 + previous latency_sla_passed=false → WARN, job green, trap not armed."""
    print("\n" + "="*70)
    print("TEST 6: Small sample (checked=3) with prev failed (should WARN, job green)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Direct unit check: 2/3 = 66% would exceed 10%, but N<10 must not hard-fail.
        db_path = tmpdir / "unit.sqlite3"
        hours = [8.5, 9.0, 2.0]
        create_test_db_with_violations(db_path, hours)

        passed, message, sla_violated = _assert_latency_check(
            db_path, inserted=len(hours), prev_passed=False
        )
        print("unit passed:", passed)
        print("unit sla_violated:", sla_violated)
        print("unit message:\n", message)

        assert passed is True, "Small-N must not hard-fail even if previous run failed"
        assert sla_violated is False, (
            "Small-N must not arm consecutive trap (sla_violated stays false)"
        )
        assert "WARN:" in message
        assert "checked < 10" in message
        assert "TWO CONSECUTIVE ROUNDS" not in message

        # Job-level: validate CLI exit 0 (green) even with LAST_RUN latency_sla_passed=false
        setup_git_with_last_run(tmpdir, latency_passed=False)
        cli_db = tmpdir / "cli.sqlite3"
        create_test_db_with_violations(cli_db, hours)
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(hours))
        meta_path = tmpdir / "validation-meta.json"

        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(cli_db),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )

        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")

        assert result.returncode == 0, (
            f"Expected exit 0 (job green on small-N), got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "WARN:" in combined
        assert "TWO CONSECUTIVE ROUNDS" not in combined
        assert "checked < 10" in combined

        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is True, (
            "Small-N WARN must not write latency_sla_passed=false "
            "(that would arm the next run's consecutive hard-fail)"
        )
        assert meta["latency_soft_miss"] is False, (
            "Small-N must not set latency_soft_miss (trap stays unarmed)"
        )
        assert meta["all_checks_passed"] is True

        print("\n✓ TEST 6 PASSED: checked=3 + prev failed → soft WARN, job green, trap not armed")


def test_large_n_first_miss_soft_warn_unit():
    """checked>=10 + prev passed + >10% → WARN, sla_violated True, job still green."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "unit.sqlite3"
        hours = [8.5, 9.0] + [2.0] * 8
        create_test_db_with_violations(db_path, hours)
        passed, message, sla_violated = _assert_latency_check(
            db_path, inserted=len(hours), prev_passed=True
        )
        assert passed is True
        assert sla_violated is True
        assert "Single-round violation" in message
        assert "TWO CONSECUTIVE ROUNDS" not in message
    print("✓ large-N first miss: passed=True, sla_violated=True")


def test_large_n_prev_failed_still_hard_fail():
    """checked>=10 + prev failed + >10% still consecutive hard FAIL."""
    print("\n" + "="*70)
    print("TEST 7: Large sample (checked=10) with prev failed and >10% (should FAIL)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Boundary: checked=10, 2/10=20% > 10%, previous failed → hard fail
        db_path = tmpdir / "unit.sqlite3"
        hours = [8.5, 9.0] + [2.0] * 8
        create_test_db_with_violations(db_path, hours)

        passed, message, sla_violated = _assert_latency_check(
            db_path, inserted=len(hours), prev_passed=False
        )
        print("unit passed:", passed)
        print("unit sla_violated:", sla_violated)
        print("unit message:\n", message)

        assert passed is False, "checked>=10 + prev failed + >10% must hard-fail"
        assert sla_violated is True
        assert "TWO CONSECUTIVE ROUNDS" in message
        assert "2/10" in message

        setup_git_with_last_run(tmpdir, latency_passed=False)
        cli_db = tmpdir / "cli.sqlite3"
        create_test_db_with_violations(cli_db, hours)
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(hours))
        meta_path = tmpdir / "validation-meta.json"

        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(cli_db),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )

        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")

        assert result.returncode == 1, (
            f"Expected exit 1 (hard fail on large-N consecutive), got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "FAIL:" in combined
        assert "TWO CONSECUTIVE ROUNDS" in combined
        assert "2/10" in combined

        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is False
        assert meta["latency_soft_miss"] is True
        assert meta["all_checks_passed"] is False

        print("\n✓ TEST 7 PASSED: checked=10 + prev failed + >10% → still hard FAIL")


def test_previous_run_had_latency_miss_helper():
    """New soft_miss flag, legacy passed=false, and a clean pass."""
    assert previous_run_had_latency_miss(None) is False
    assert previous_run_had_latency_miss({"latency_sla_passed": True}) is False
    assert previous_run_had_latency_miss(
        {"latency_sla_passed": True, "latency_soft_miss": False}
    ) is False
    assert previous_run_had_latency_miss(
        {"latency_sla_passed": True, "latency_soft_miss": True}
    ) is True
    # Consecutive hard-fail persist still counts as a miss next round.
    assert previous_run_had_latency_miss(
        {"latency_sla_passed": False, "latency_soft_miss": True}
    ) is True
    # Legacy LAST_RUN (run 39299196711): passed=false, no soft_miss key.
    assert previous_run_had_latency_miss({"latency_sla_passed": False}) is True
    # New schema: passed=false without soft_miss should not happen, but if
    # soft_miss is explicitly false, do not treat as a miss.
    assert previous_run_had_latency_miss(
        {"latency_sla_passed": False, "latency_soft_miss": False}
    ) is False
    print("✓ previous_run_had_latency_miss helper")


def test_consecutive_via_soft_miss_keeps_passed_true_on_first():
    """Previous latency_sla_passed=true + latency_soft_miss=true → consecutive FAIL."""
    print("\n" + "="*70)
    print("TEST 8: Consecutive via latency_soft_miss (previous passed still true)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        setup_git_with_last_run(tmpdir, latency_passed=True, soft_miss=True)

        db_path = tmpdir / "test.sqlite3"
        hours = [8.5, 9.0] + [2.0] * 13
        create_test_db_with_violations(db_path, hours)
        stats_path = tmpdir / "stats.json"
        create_stats_json(stats_path, len(hours))
        meta_path = tmpdir / "validation-meta.json"

        result = subprocess.run(
            [
                "python3", "-m", "news_archive.validate",
                "--db", str(db_path),
                "--stats", str(stats_path),
                "--output-meta", str(meta_path),
            ],
            cwd=tmpdir,
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
            capture_output=True,
            text=True,
        )

        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        print(f"\nExit code: {result.returncode}")

        assert result.returncode == 1, (
            f"Expected exit 1 (consecutive via soft_miss), got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "TWO CONSECUTIVE ROUNDS" in combined

        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is False
        assert meta["latency_soft_miss"] is True

        print("\n✓ TEST 8 PASSED: previous soft_miss + this large-N miss → hard FAIL")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Testing Latency SLA Consecutive Failure Detection")
    print("="*70)
    
    try:
        test_single_round_violation()
        test_consecutive_violation()
        test_pass_after_previous_failure()
        test_new_source_first_ingest_not_hard_fail()
        test_new_source_does_not_mask_established_consecutive_fail()
        test_small_sample_prev_failed_is_soft_warn()
        test_large_n_first_miss_soft_warn_unit()
        test_large_n_prev_failed_still_hard_fail()
        test_previous_run_had_latency_miss_helper()
        test_consecutive_via_soft_miss_keeps_passed_true_on_first()
        
        print("\n" + "="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
