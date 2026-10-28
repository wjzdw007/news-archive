"""Pack / restore the data-branch archive under GitHub's 100MiB blob limit.

Covers the Persist hotfix for run 40500314784 (100.75MiB raw sqlite):
- gzip pack + restore round-trip
- legacy uncompressed blob still restores
- split parts concat + restore
- persist checkout dance leaves the live DB on the original ref
- workflows call the shared script and never git-add the raw sqlite
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "data_branch_archive.sh"
DAILY = ROOT / ".github" / "workflows" / "daily-fetch.yml"
X_FETCH = ROOT / ".github" / "workflows" / "x-fetch.yml"
PAGES = ROOT / ".github" / "workflows" / "deploy-pages.yml"
GITHUB_BLOB_LIMIT = 100 * 1024 * 1024


def _run(args: list[str], *, cwd: Path, env: dict | None = None, check: bool = True):
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        args,
        cwd=cwd,
        env=full_env,
        check=check,
        capture_output=True,
        text=True,
    )


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd=cwd)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@example.com")
    (root / "README").write_text("main\n", encoding="utf-8")
    # Restore script is invoked by relative path in workflows; copy it in.
    scripts = root / "scripts"
    scripts.mkdir()
    scripts.joinpath("data_branch_archive.sh").write_bytes(SCRIPT.read_bytes())
    scripts.joinpath("data_branch_archive.sh").chmod(0o755)
    _git(root, "add", "README", "scripts/data_branch_archive.sh")
    _git(root, "commit", "-m", "main")


def _make_db(path: Path, *, n: int = 20, blob: str = "snapshot body ") -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE articles (url TEXT PRIMARY KEY, title TEXT, content_snapshot TEXT)"
    )
    conn.executemany(
        "INSERT INTO articles VALUES (?, ?, ?)",
        [(f"https://ex/{i}", f"t{i}", f"{blob}{i}" * 8) for i in range(n)],
    )
    conn.commit()
    conn.close()
    return n


def _count(path: Path) -> int:
    conn = sqlite3.connect(path)
    n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return int(n)


def _pack(db: Path, out: Path, *, split_bytes: int | None = None) -> dict:
    env = {}
    if split_bytes is not None:
        env["ARCHIVE_SPLIT_BYTES"] = str(split_bytes)
    _run([str(SCRIPT), "pack", str(db), str(out)], cwd=ROOT, env=env)
    return json.loads((out / "PACK_META.json").read_text(encoding="utf-8"))


def test_pack_restore_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "archive.sqlite3"
        n = _make_db(db)
        raw = db.stat().st_size
        packed_dir = tmp_path / "packed"
        meta = _pack(db, packed_dir)

        assert meta["files"] == ["archive.sqlite3.gz"]
        assert meta["split"] is False
        assert meta["raw_bytes"] == raw
        assert 0 < meta["packed_bytes"] < GITHUB_BLOB_LIMIT
        gz = packed_dir / "archive.sqlite3.gz"
        assert gz.stat().st_size == meta["packed_bytes"]
        assert gz.stat().st_size < raw or raw < 4096

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        _git(repo, "checkout", "--orphan", "data")
        _run(["git", "rm", "-rf", "."], cwd=repo, check=False)
        (repo / "data").mkdir()
        (repo / "data" / "archive.sqlite3.gz").write_bytes(gz.read_bytes())
        _git(repo, "add", "data/archive.sqlite3.gz")
        _git(repo, "commit", "-m", "packed")
        _git(repo, "checkout", "main")

        dest = repo / "data" / "archive.sqlite3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = _run(
            ["bash", "scripts/data_branch_archive.sh", "restore", str(dest)],
            cwd=repo,
        )
        assert dest.is_file(), result.stdout + result.stderr
        assert _count(dest) == n
        conn = sqlite3.connect(dest)
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        assert ok == "ok"
        print(f"✓ gzip round-trip packed={meta['packed_bytes']} raw={raw} rows={n}")


def test_restore_legacy_raw_blob():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        db = tmp_path / "src.sqlite3"
        n = _make_db(db, n=7)
        _git(repo, "checkout", "--orphan", "data")
        _run(["git", "rm", "-rf", "."], cwd=repo, check=False)
        (repo / "data").mkdir()
        (repo / "data" / "archive.sqlite3").write_bytes(db.read_bytes())
        _git(repo, "add", "data/archive.sqlite3")
        _git(repo, "commit", "-m", "legacy raw")
        _git(repo, "checkout", "main")

        dest = repo / "restored.sqlite3"
        _run(
            ["bash", "scripts/data_branch_archive.sh", "restore", str(dest)],
            cwd=repo,
        )
        assert _count(dest) == n
        print("✓ legacy uncompressed data/archive.sqlite3 still restores")


def test_restore_split_parts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "archive.sqlite3"
        # Unique incompressible rows so gzip stays above the tiny split threshold.
        n = 12
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE articles (url TEXT PRIMARY KEY, title TEXT, content_snapshot TEXT)"
        )
        conn.executemany(
            "INSERT INTO articles VALUES (?, ?, ?)",
            [
                (f"https://ex/{i}", f"t{i}", os.urandom(1200).hex())
                for i in range(n)
            ],
        )
        conn.commit()
        conn.close()
        packed_dir = tmp_path / "packed"
        meta = _pack(db, packed_dir, split_bytes=400)
        assert meta["split"] is True
        assert len(meta["files"]) >= 2
        for name in meta["files"]:
            assert (packed_dir / name).stat().st_size < GITHUB_BLOB_LIMIT

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        _git(repo, "checkout", "--orphan", "data")
        _run(["git", "rm", "-rf", "."], cwd=repo, check=False)
        data_dir = repo / "data"
        data_dir.mkdir()
        for name in meta["files"]:
            (data_dir / name).write_bytes((packed_dir / name).read_bytes())
            _git(repo, "add", f"data/{name}")
        _git(repo, "commit", "-m", "split")
        _git(repo, "checkout", "main")

        dest = repo / "data" / "archive.sqlite3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _run(
            ["bash", "scripts/data_branch_archive.sh", "restore", str(dest)],
            cwd=repo,
        )
        assert _count(dest) == n
        print(f"✓ split restore files={meta['files']} rows={n}")


def test_persist_checkout_dance_restores_live_db():
    """After checkout data (src gone), trap-equivalent copy leaves DB on main."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        (repo / "src" / "news_archive").mkdir(parents=True)
        (repo / "src" / "news_archive" / "__init__.py").write_text("", encoding="utf-8")
        _git(repo, "add", "src")
        _git(repo, "commit", "-m", "src")

        live = repo / "data" / "archive.sqlite3"
        n = _make_db(live)
        runner_temp = tmp_path / "rt"
        runner_temp.mkdir()
        (runner_temp / "archive.sqlite3").write_bytes(live.read_bytes())
        _pack(runner_temp / "archive.sqlite3", runner_temp / "packed")

        _git(repo, "checkout", "--orphan", "data")
        _run(["git", "rm", "-rf", "."], cwd=repo, check=False)
        assert not (repo / "src").exists()

        # Same as workflow trap restore_workspace: force back to main + recopy.
        _git(repo, "checkout", "-f", "main")
        (repo / "data").mkdir(exist_ok=True)
        (repo / "data" / "archive.sqlite3").write_bytes(
            (runner_temp / "archive.sqlite3").read_bytes()
        )
        assert (repo / "src" / "news_archive").is_dir()
        assert _count(repo / "data" / "archive.sqlite3") == n
        print("✓ persist checkout dance leaves src/ + live sqlite on original ref")


def test_live_artifact_gzip_under_github_limit():
    """The 100.75MiB artifact from run 40500314784 must pack under 100MiB."""
    live = Path("/tmp/archive-artifact/news-archive-40500314784/archive.sqlite3")
    if not live.is_file():
        print("⚠ live artifact missing locally; skip size-headroom check")
        return
    with tempfile.TemporaryDirectory() as tmp:
        meta = _pack(live, Path(tmp) / "packed")
    assert meta["packed_bytes"] < GITHUB_BLOB_LIMIT
    assert meta["split"] is False
    assert meta["files"] == ["archive.sqlite3.gz"]
    # VACUUM-only left the live file at ~98MiB — not a durable fix.
    assert meta["vacuum_bytes"] > 90 * 1024 * 1024
    headroom = GITHUB_BLOB_LIMIT - meta["packed_bytes"]
    print(
        f"✓ live artifact packed={meta['packed_bytes']} "
        f"vacuum={meta['vacuum_bytes']} headroom={headroom}"
    )


def test_workflows_use_shared_pack_restore():
    daily = DAILY.read_text(encoding="utf-8")
    x_fetch = X_FETCH.read_text(encoding="utf-8")
    pages = PAGES.read_text(encoding="utf-8")
    for name, yml in (
        ("daily-fetch", daily),
        ("x-fetch", x_fetch),
        ("deploy-pages", pages),
    ):
        assert "scripts/data_branch_archive.sh restore" in yml, name
    for name, yml in (("daily-fetch", daily), ("x-fetch", x_fetch)):
        assert "scripts/data_branch_archive.sh pack" in yml, name
        assert "restore_workspace" in yml, name
        assert "trap restore_workspace EXIT" in yml, name
        persist_at = yml.index("- name: Persist")
        persist = yml[persist_at : persist_at + 8000]
        assert "git add data/archive.sqlite3 " not in persist, name
        assert "archive.sqlite3.gz" in persist, name
    assert "git show data:data/archive.sqlite3 >" not in daily
    assert "git show data:data/archive.sqlite3 >" not in x_fetch
    assert "git show data:data/archive.sqlite3 >" not in pages
    print("✓ workflows pack gzip / restore shared script; no raw sqlite push")


if __name__ == "__main__":
    test_pack_restore_round_trip()
    test_restore_legacy_raw_blob()
    test_restore_split_parts()
    test_persist_checkout_dance_restores_live_db()
    test_live_artifact_gzip_under_github_limit()
    test_workflows_use_shared_pack_restore()
    print("✓ data-branch archive pack/restore tests PASSED")
