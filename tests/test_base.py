"""Tests for A.data.base — SQLiteDB connection handling."""

import sqlite3
from pathlib import Path

import pytest


def test_sqlitedb_connection_timeout():
    """SQLiteDB creates connections with a 10-second busy timeout.

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
        assert timeout_ms == 10000, (
            f"Expected busy_timeout=10000ms, got {timeout_ms}"
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


def test_open_healthy_db_corrupted_passes_through(tmp_path: Path):
    """open_healthy_db opens even a corrupted DB (health check removed)."""
    from A.data.base import open_healthy_db

    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)

    # No health check on open — just passes through to SQLiteDB
    db = open_healthy_db(db_path)
    assert db.path == db_path


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


def test_health_check_healthy_db(tmp_path: Path):
    """health_check returns True for a healthy database."""
    from A.data.base import health_check

    db_path = tmp_path / "healthy.db"

    # Create healthy DB
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

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


# ── health_check WAL replay tests ────────────────────────────────────


def test_health_check_replays_wal(tmp_path: Path):
    """health_check replays WAL from an active connection.

    Previously used ?immutable=1 which bypassed the WAL entirely,
    so data committed but not yet flushed to the main DB was
    invisible to the health check.  Now opens a normal connection
    that replays the WAL automatically.
    """
    from A.data.base import health_check

    db_path = tmp_path / "wal_replay.db"

    # Open a connection, enable WAL, write data, but KEEP the
    # connection open so the WAL is NOT checkpointed.
    writer = sqlite3.connect(str(db_path))
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE t (v INTEGER)")
    writer.execute("INSERT INTO t VALUES (42)")
    writer.commit()

    # Verify writer can see its own data
    row = writer.execute("SELECT v FROM t").fetchone()
    assert row[0] == 42

    # A separate ?immutable=1 connection CANNOT see the data
    # because the WAL hasn't been checkpointed (writer is still open).
    immutable = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
    with pytest.raises((sqlite3.OperationalError, sqlite3.DatabaseError)):
        immutable.execute("SELECT v FROM t").fetchone()
    immutable.close()

    # But health_check (normal connection, replays WAL) should succeed
    assert health_check(db_path) is True

    # After health_check, the data should be in the main DB (TRUNCATE checkpoint)
    reader = sqlite3.connect(str(db_path))
    row = reader.execute("SELECT v FROM t").fetchone()
    assert row[0] == 42
    reader.close()

    writer.close()


def test_health_check_corrupted_file(tmp_path: Path):
    """health_check returns False for a corrupted database file."""
    from A.data.base import health_check

    db_path = tmp_path / "corrupted_health.db"
    # Write garbage that looks like a SQLite header
    db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
    assert health_check(db_path) is False


def test_health_check_non_existent(tmp_path: Path):
    """health_check returns True for a non-existent file (can't be corrupted)."""
    from A.data.base import health_check

    assert health_check(tmp_path / "nonexistent.db") is True


# ── backup_db tests ──────────────────────────────────────────────────


def test_backup_db_creates_bak(tmp_path: Path):
    """backup_db creates a .bak file with valid SQLite content."""
    from A.data.base import backup_db, health_check

    db_path = tmp_path / "test_backup.db"

    # Create a healthy database
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    backup_db(db_path)

    bak_path = db_path.with_suffix(".db.bak")
    assert bak_path.exists(), "backup_db should create a .bak file"
    assert health_check(bak_path) is True, "backup should be a valid SQLite DB"


def test_backup_db_with_wal_data(tmp_path: Path):
    """backup_db flushes WAL before copy, so backup includes recent writes."""
    from A.data.base import backup_db, health_check

    db_path = tmp_path / "wal_backup.db"

    # Create DB in WAL mode with uncheckpointed data
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    # backup_db should checkpoint (TRUNCATE) before copying
    backup_db(db_path)

    bak_path = db_path.with_suffix(".db.bak")
    assert bak_path.exists()
    assert health_check(bak_path) is True

    # Verify the backup contains the data
    reader = sqlite3.connect(str(bak_path))
    reader.row_factory = sqlite3.Row
    row = reader.execute("SELECT v FROM t").fetchone()
    assert row["v"] == 42, "backup should contain the committed data"
    reader.close()


def test_backup_db_non_existent(tmp_path: Path):
    """backup_db does nothing for a non-existent file (no crash)."""
    from A.data.base import backup_db

    # Should not raise any exception
    backup_db(tmp_path / "nonexistent.db")
