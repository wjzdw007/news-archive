"""Test latency SLA consecutive failure detection."""

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_archive.sources import SOURCES


def create_test_db_with_violations(db_path: Path, violation_hours: list[float]) -> None:
    """Create a test database with articles that have specified latency violations.
    
    Args:
        db_path: Path to create the SQLite database
        violation_hours: List of hours for each article's latency (e.g., [8.5, 9.0, 2.0])
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
    
    # Insert articles with specified latency
    for i, hours in enumerate(violation_hours):
        published_at = fetched_at - timedelta(hours=hours)
        conn.execute(
            """
            INSERT INTO articles (url, title, published_at, fetched_at, source, summary, content_snapshot, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"https://example.com/article-{i}",
                f"Test Article {i}",
                published_at.isoformat(),
                fetched_at_str,
                "test_source",
                f"Summary {i}",
                f"Content {i}",
                "active",
            ),
        )
    
    # Add at least one article for each configured source to pass Source Incremental check
    sources = [s.id for s in SOURCES]
    for j, source in enumerate(sources):
        # Use older fetched_at so they don't interfere with latency check
        old_fetched_at = fetched_at - timedelta(days=1)
        old_published_at = old_fetched_at - timedelta(hours=2)
        conn.execute(
            """
            INSERT INTO articles (url, title, published_at, fetched_at, source, summary, content_snapshot, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"https://example.com/old-{source}-{j}",
                f"Old {source} Article",
                old_published_at.isoformat(),
                old_fetched_at.isoformat(),
                source,
                f"Old summary from {source}",
                f"Old content from {source}",
                "active",
            ),
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


def setup_git_with_last_run(git_dir: Path, latency_passed: bool) -> None:
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
        
        # Check metadata
        meta = json.loads(meta_path.read_text())
        assert meta["latency_sla_passed"] is False, "Expected latency_sla_passed=false in metadata"
        
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
        
        print("\n✓ TEST 3 PASSED: Passed after previous failure, reset consecutive count")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Testing Latency SLA Consecutive Failure Detection")
    print("="*70)
    
    try:
        test_single_round_violation()
        test_consecutive_violation()
        test_pass_after_previous_failure()
        
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
