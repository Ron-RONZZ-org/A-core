"""Tests for A.data.base — SQLiteDB connection handling."""

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
