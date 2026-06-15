"""Tests for A.data.base — SQLiteDB connection handling."""

import sqlite3
from pathlib import Path

import pytest


def test_sqlitedb_connection_timeout():
    """SQLiteDB creates connections with a 5-second busy timeout.

    The ``timeout`` parameter to ``sqlite3.connect()`` sets the
    ``busy_timeout`` PRAGMA, which makes SQLite retry locked databases
    for the given number of seconds instead of immediately raising
    ``database is locked``.
    """
    from A.data.base import SQLiteDB

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        db = SQLiteDB(db_path)
        conn = db._get_conn()

        # Verify the timeout was set: PRAGMA busy_timeout returns ms
        (timeout_ms,) = conn.execute("PRAGMA busy_timeout").fetchone()
        assert timeout_ms == 5000, (
            f"Expected busy_timeout=5000ms, got {timeout_ms}"
        )

        db.close()
    finally:
        db_path.unlink(missing_ok=True)


# ── open_healthy_db tests ──────────────────────────────────────────────


def test_open_healthy_db_creates_new(tmp_path: Path):
    """open_healthy_db creates a valid database when file doesn't exist."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "new.db"
    db = open_healthy_db(db_path)
    try:
        # Verify it's a valid SQLite database
        row = db.execute_one("SELECT sqlite_version()")
        assert row is not None
    finally:
        db.close()


def test_open_healthy_db_healthy(tmp_path: Path):
    """open_healthy_db opens an existing healthy database."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "existing.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER)")
    conn.execute("INSERT INTO test VALUES (42)")
    conn.commit()
    conn.close()

    db = open_healthy_db(db_path)
    try:
        row = db.execute_one("SELECT id FROM test")
        assert row["id"] == 42
    finally:
        db.close()


def test_open_healthy_db_corrupted_raises(tmp_path: Path):
    """open_healthy_db raises RuntimeError when DB is too corrupted."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "corrupted.db"
    # Create a corrupted file
    db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)

    with pytest.raises(RuntimeError, match="corrupted"):
        open_healthy_db(db_path)


def test_open_healthy_db_wal_shm_repair(tmp_path: Path):
    """open_healthy_db recovers from stale WAL/SHM files."""
    from A.data.base import open_healthy_db
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        # Create a healthy DB
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()

        # Create stale WAL file
        wal_path = db_path.with_name(db_path.name + "-wal")
        wal_path.write_text("garbage")
        shm_path = db_path.with_name(db_path.name + "-shm")
        shm_path.write_text("garbage")

        # Should still open because repair deletes stale WAL/SHM
        db = open_healthy_db(db_path)
        try:
            row = db.execute_one("SELECT v FROM t")
            assert row["v"] == 1
        finally:
            db.close()

        # Verify stale files were cleaned up
        assert not wal_path.exists() or wal_path.stat().st_size == 0
    finally:
        db_path.unlink(missing_ok=True)
        wal_path = db_path.with_name(db_path.name + "-wal")
        wal_path.unlink(missing_ok=True)
        shm_path = db_path.with_name(db_path.name + "-shm")
        shm_path.unlink(missing_ok=True)


def test_open_healthy_db_non_existent_no_backup(tmp_path: Path):
    """open_healthy_db works with backup=False on non-existent DB."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "no_backup.db"
    db = open_healthy_db(db_path, backup=False)
    try:
        row = db.execute_one("PRAGMA journal_mode")
        assert row["journal_mode"] == "wal"
    finally:
        db.close()


def test_open_healthy_db_backup_not_created_on_new(tmp_path: Path):
    """open_healthy_db does not fail when no backup possible (new DB)."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "fresh.db"
    db = open_healthy_db(db_path)
    try:
        row = db.execute_one("SELECT 1 AS ok")
        assert row["ok"] == 1
    finally:
        db.close()


def test_open_healthy_db_healthy_readonly_check(tmp_path: Path):
    """open_healthy_db's health check uses a read-only connection."""
    from A.data.base import health_check

    db_path = tmp_path / "readonly_check.db"

    # Create healthy DB
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    # health_check should succeed
    assert health_check(db_path) is True


def test_open_healthy_db_wal_mode(tmp_path: Path):
    """Database opened via open_healthy_db has WAL mode enabled."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "wal_check.db"
    db = open_healthy_db(db_path)
    try:
        row = db.execute_one("PRAGMA journal_mode")
        # SQLite returns 'wal' for already-WAL databases
        assert row["journal_mode"] in ("wal", "delete")
    finally:
        db.close()
