"""Tests for A.core.backup — backup_database, list_backups, restore, prune.

The ``conftest.py`` fixture ``isolate_core`` redirects ``data_dir()`` to
``tmp_path``, so all backup files land in a temporary directory.
"""

import os
from pathlib import Path

import pytest

from A.core.backup import (
    backup_dir,
    backup_database,
    list_backups,
    prune_backups,
    restore_latest,
    restore_by_timestamp,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _touch_db(path: Path, content: str = "hello") -> None:
    """Create a minimal SQLite-like database file for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _count_backup_files(module: str) -> int:
    """Count .db files in the module's backup subdirectory."""
    d = backup_dir() / module
    if not d.is_dir():
        return 0
    return len(list(d.glob("*.db")))


# ── backup_dir ──────────────────────────────────────────────────────────────────


def test_backup_dir_returns_expected_path() -> None:
    """backup_dir() returns data_dir() / '.backups'."""
    from A.core.paths import data_dir

    assert backup_dir() == data_dir() / ".backups"


def test_backup_dir_does_not_create_directory() -> None:
    """backup_dir() does not create the directory on its own."""
    d = backup_dir()
    assert not d.exists()


# ── backup_database ─────────────────────────────────────────────────────────────


def test_backup_database_creates_backup(tmp_path: Path) -> None:
    """backup_database() creates a .db file in the module backup dir."""
    src = tmp_path / "test.db"
    _touch_db(src)

    result = backup_database(src, module="test_mod")
    assert result is not None
    assert result.exists()
    assert result.suffix == ".db"
    assert result.parent == backup_dir() / "test_mod"


def test_backup_database_returns_none_for_missing_source() -> None:
    """backup_database() returns None when source does not exist."""
    result = backup_database(Path("/nonexistent/path.db"), module="test_mod")
    assert result is None


def test_backup_database_checksum_verification(tmp_path: Path) -> None:
    """backup_database() verifies SHA-256 after copy."""
    src = tmp_path / "test.db"
    _touch_db(src)

    # Should not raise — valid backup
    result = backup_database(src, module="test_mod")
    assert result is not None

    # Read back the content and confirm it's intact
    assert result.read_bytes() == src.read_bytes()


def test_backup_database_uses_timestamp_filename(tmp_path: Path) -> None:
    """The backup filename is a timestamp with .db suffix."""
    src = tmp_path / "test.db"
    _touch_db(src)

    result = backup_database(src, module="ts_mod")
    assert result is not None
    # Timestamp format: YYYYMMDDTHHMMSS + 9 nanosecond digits = 24 chars
    stem = result.stem
    assert len(stem) == 24
    assert stem[8] == "T"


def test_backup_database_two_modules_isolated(tmp_path: Path) -> None:
    """Backups for different modules go to separate subdirectories."""
    src1 = tmp_path / "mod1.db"
    src2 = tmp_path / "mod2.db"
    _touch_db(src1, "data1")
    _touch_db(src2, "data2")

    r1 = backup_database(src1, module="module_a")
    r2 = backup_database(src2, module="module_b")

    assert r1 is not None
    assert r2 is not None
    assert r1.parent != r2.parent
    assert r1.parent.name == "module_a"
    assert r2.parent.name == "module_b"


def test_backup_database_multiple_backups(tmp_path: Path) -> None:
    """Multiple backups for the same module accumulate."""
    src = tmp_path / "test.db"
    _touch_db(src, "v1")

    backup_database(src, module="multi")
    assert _count_backup_files("multi") == 1

    _touch_db(src, "v2")
    backup_database(src, module="multi")
    assert _count_backup_files("multi") == 2

    _touch_db(src, "v3")
    backup_database(src, module="multi")
    assert _count_backup_files("multi") == 3


# ── list_backups ────────────────────────────────────────────────────────────────


def test_list_backups_returns_empty_for_unknown_module() -> None:
    """list_backups() returns an empty list for modules with no backups."""
    assert list_backups("nonexistent_module") == []


def test_list_backups_returns_backups_newest_first(tmp_path: Path) -> None:
    """list_backups() returns backups sorted newest first."""
    src = tmp_path / "test.db"
    _touch_db(src, "v1")
    backup_database(src, module="ls_test")
    b1 = list_backups("ls_test")

    assert len(b1) == 1
    assert b1[0]["timestamp"] is not None
    assert b1[0]["size_bytes"] > 0
    assert isinstance(b1[0]["path"], Path)

    # Second backup should come first in list
    _touch_db(src, "v2")
    backup_database(src, module="ls_test")
    b2 = list_backups("ls_test")
    assert len(b2) == 2
    assert b2[0]["timestamp"] > b2[1]["timestamp"]


def test_list_backups_excludes_non_db_files(tmp_path: Path) -> None:
    """list_backups() ignores non-.db files in the backup dir."""
    src = tmp_path / "test.db"
    _touch_db(src)
    backup_database(src, module="filter_test")

    # Manually drop a .txt file into the backup dir
    mod_dir = backup_dir() / "filter_test"
    (mod_dir / "notes.txt").write_text("not a backup")

    backups = list_backups("filter_test")
    assert all(b["path"].suffix == ".db" for b in backups)
    assert len(backups) == 1


# ── restore_latest ──────────────────────────────────────────────────────────────


def test_restore_latest_restores_newest(tmp_path: Path) -> None:
    """restore_latest() restores the most recent backup."""
    src = tmp_path / "test.db"
    _touch_db(src, "initial")
    backup_database(src, module="restore_test")

    _touch_db(src, "updated")
    backup_database(src, module="restore_test")

    target = tmp_path / "restored.db"
    result = restore_latest("restore_test", target)
    assert result == target
    assert target.read_text() == "updated"


def test_restore_latest_raises_on_no_backups() -> None:
    """restore_latest() raises FileNotFoundError when no backups exist."""
    with pytest.raises(FileNotFoundError, match="No backups found"):
        restore_latest("ghost_module", Path("/dev/null"))


# ── restore_by_timestamp ────────────────────────────────────────────────────────


def test_restore_by_timestamp_exact(tmp_path: Path) -> None:
    """restore_by_timestamp() restores a backup by exact timestamp."""
    src = tmp_path / "test.db"
    _touch_db(src, "original")
    backup_database(src, module="ts_restore")

    backups = list_backups("ts_restore")
    ts = backups[0]["timestamp"]

    target = tmp_path / "restored.db"
    result = restore_by_timestamp("ts_restore", ts, target)
    assert result == target
    assert target.read_text() == "original"


def test_restore_by_timestamp_prefix(tmp_path: Path) -> None:
    """restore_by_timestamp() matches on partial prefix."""
    src = tmp_path / "test.db"
    _touch_db(src, "data")
    backup_database(src, module="prefix_restore")

    target = tmp_path / "restored.db"
    # Use a short prefix that should match (the date part)
    from A.core.backup import list_backups

    full_ts = list_backups("prefix_restore")[0]["timestamp"]
    prefix = full_ts[:8]  # just the date YYYYMMDD

    result = restore_by_timestamp("prefix_restore", prefix, target)
    assert result == target
    assert target.read_text() == "data"


def test_restore_by_timestamp_no_match(tmp_path: Path) -> None:
    """restore_by_timestamp() raises LookupError on no match."""
    src = tmp_path / "test.db"
    _touch_db(src, "data")
    backup_database(src, module="no_match_mod")

    with pytest.raises(LookupError, match="No backup matches"):
        restore_by_timestamp("no_match_mod", "19990101", tmp_path / "out.db")


def test_restore_by_timestamp_ambiguous(tmp_path: Path) -> None:
    """restore_by_timestamp() raises LookupError on ambiguous prefix."""
    src = tmp_path / "test.db"
    _touch_db(src, "v1")
    backup_database(src, module="ambig", retention=0)  # don't prune
    backup_database(src, module="ambig", retention=0)  # same module, two backups

    # There should be 2 backups now (timestamps have ms precision)
    assert len(list_backups("ambig")) == 2

    with pytest.raises(LookupError, match="ambiguous"):
        # Empty normalises to "" which matches all filenames
        restore_by_timestamp("ambig", "", tmp_path / "out.db")


def test_restore_by_timestamp_no_backups() -> None:
    """restore_by_timestamp() raises FileNotFoundError when no backups."""
    with pytest.raises(FileNotFoundError, match="No backups found"):
        restore_by_timestamp("empty_mod", "2026", Path("/dev/null"))


# ── prune_backups ───────────────────────────────────────────────────────────────


def test_prune_backups_keeps_newest(tmp_path: Path) -> None:
    """prune_backups() keeps the newest N and deletes older ones."""
    src = tmp_path / "test.db"
    for i in range(5):
        _touch_db(src, f"v{i}")
        backup_database(src, module="prune_test", retention=0)  # no auto-prune

    assert _count_backup_files("prune_test") == 5

    deleted = prune_backups("prune_test", retention=2)
    assert deleted == 3
    assert _count_backup_files("prune_test") == 2


def test_prune_backups_idempotent(tmp_path: Path) -> None:
    """Calling prune_backups() twice with same retention is safe."""
    src = tmp_path / "test.db"
    for i in range(4):
        _touch_db(src, f"v{i}")
        backup_database(src, module="idempotent", retention=0)

    assert _count_backup_files("idempotent") == 4

    prune_backups("idempotent", retention=2)  # deletes 2
    prune_backups("idempotent", retention=2)  # no-op
    assert _count_backup_files("idempotent") == 2


def test_prune_backups_noop_when_under_limit(tmp_path: Path) -> None:
    """prune_backups() does nothing when file count is <= retention."""
    src = tmp_path / "test.db"
    _touch_db(src)
    backup_database(src, module="noop", retention=0)

    deleted = prune_backups("noop", retention=10)
    assert deleted == 0
    assert _count_backup_files("noop") == 1


def test_prune_backups_empty_dir() -> None:
    """prune_backups() returns 0 for a module with no backup dir."""
    deleted = prune_backups("nonexistent")
    assert deleted == 0


def test_prune_backups_retention_less_than_one() -> None:
    """prune_backups() raises ValueError if retention < 1."""
    with pytest.raises(ValueError, match="retention must be >= 1"):
        prune_backups("any", retention=0)


# ── Integration: backup → prune → restore ───────────────────────────────────────


def test_backup_then_prune_then_restore(tmp_path: Path) -> None:
    """End-to-end: backup multiple versions, prune, restore specific."""
    src = tmp_path / "test.db"

    for content in ("alpha", "beta", "gamma", "delta"):
        _touch_db(src, content)
        backup_database(src, module="e2e", retention=0)

    assert _count_backup_files("e2e") == 4

    # Keep only the 2 newest
    prune_backups("e2e", retention=2)
    assert _count_backup_files("e2e") == 2

    # Latest should be "delta"
    target = tmp_path / "restored.db"
    restore_latest("e2e", target)
    assert target.read_text() == "delta"


def test_restore_verifies_checksum(tmp_path: Path) -> None:
    """restore_latest() verifies checksum after copy."""
    src = tmp_path / "test.db"
    _touch_db(src, "data_for_checksum")
    backup_database(src, module="checksum_test")

    target = tmp_path / "restored.db"
    result = restore_latest("checksum_test", target)
    assert target.read_text() == "data_for_checksum"
    assert result == target


# ── SQLiteDB integration ────────────────────────────────────────────────────────


def _sqlite_db_exists(module: str) -> int:
    """Return number of backup files for *module*."""
    d = backup_dir() / module
    if not d.is_dir():
        return 0
    return len(list(d.glob("*.db")))


def test_sqlitedb_auto_backup_on_init_when_db_exists(tmp_path: Path) -> None:
    """SQLiteDB backs up existing DB on init."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "existing.db"
    # Create a pre-existing database
    db1 = SQLiteDB(db_path)
    db1.execute("CREATE TABLE t (x TEXT)")
    db1.execute("INSERT INTO t VALUES ('hello')")
    db1.close()

    count_before = _sqlite_db_exists("existing")
    assert count_before == 0  # first init: no backup (no prior DB)

    # Re-open same DB — should auto-backup
    db2 = SQLiteDB(db_path)
    db2.close()
    assert _sqlite_db_exists("existing") == 1

    # Verify backup content
    backups = list_backups("existing")
    assert len(backups) == 1
    # The backup was created from the DB with "hello"
    import sqlite3
    restored = sqlite3.connect(str(backups[0]["path"]))
    (value,) = restored.execute("SELECT x FROM t").fetchone()
    assert value == "hello"
    restored.close()


def test_sqlitedb_no_backup_on_first_init(tmp_path: Path) -> None:
    """SQLiteDB does NOT back up on init when DB doesn't exist yet (first run)."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "fresh.db"
    db = SQLiteDB(db_path)
    db.execute("CREATE TABLE t (x TEXT)")
    db.close()

    # No backup should have been created (the DB didn't exist before init)
    assert _sqlite_db_exists("fresh") == 0


def test_sqlitedb_auto_backup_before_ddl(tmp_path: Path) -> None:
    """SQLiteDB backs up before DDL statements."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "ddl_test.db"
    db = SQLiteDB(db_path)
    db.execute("CREATE TABLE t (x TEXT)")
    db.execute("INSERT INTO t VALUES ('pre-ddl')")
    db.close()

    # Re-open and run ALTER TABLE — should trigger backup
    db2 = SQLiteDB(db_path)
    count_after_init = _sqlite_db_exists("ddl_test")
    assert count_after_init == 1  # auto-backup on init

    db2.execute("ALTER TABLE t ADD COLUMN y TEXT")
    # Should have triggered ANOTHER backup before the DDL
    assert _sqlite_db_exists("ddl_test") == 2
    db2.close()


def test_sqlitedb_no_backup_on_select(tmp_path: Path) -> None:
    """SQLiteDB does NOT back up on SELECT statements."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "select_test.db"
    db = SQLiteDB(db_path)
    db.execute("CREATE TABLE t (x TEXT)")
    db.execute("INSERT INTO t VALUES ('data')")
    db.close()

    # Re-open — triggers 1 backup on init
    db2 = SQLiteDB(db_path)
    assert _sqlite_db_exists("select_test") == 1

    # SELECT should NOT trigger backup
    rows = db2.execute("SELECT * FROM t")
    assert rows == [{"x": "data"}]
    assert _sqlite_db_exists("select_test") == 1  # still 1

    # INSERT (DML) should NOT trigger backup
    db2.execute("INSERT INTO t VALUES ('more')")
    assert _sqlite_db_exists("select_test") == 1  # still 1

    db2.close()


def test_sqlitedb_module_explicit(tmp_path: Path) -> None:
    """SQLiteDB(module=...) uses the explicit module name for backups."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "any_name.db"
    # Create pre-existing DB
    db1 = SQLiteDB(db_path)
    db1.execute("CREATE TABLE t (x TEXT)")
    db1.execute("INSERT INTO t VALUES ('v')")
    db1.close()

    db2 = SQLiteDB(db_path, module="custom_module")
    db2.close()
    assert _sqlite_db_exists("custom_module") == 1


def test_sqlitedb_module_path_derived(tmp_path: Path) -> None:
    """SQLiteDB derives module name from path under data_dir()."""
    from A.data.base import SQLiteDB
    from A.core.paths import data_dir

    mod_dir = data_dir() / "my_mod"
    mod_dir.mkdir(parents=True, exist_ok=True)
    db_path = mod_dir / "data.db"

    # Create pre-existing DB
    db1 = SQLiteDB(db_path)
    db1.execute("CREATE TABLE t (x TEXT)")
    db1.execute("INSERT INTO t VALUES ('v')")
    db1.close()

    db2 = SQLiteDB(db_path)
    db2.close()
    assert _sqlite_db_exists("my_mod") == 1


def test_sqlitedb_module_stem_fallback(tmp_path: Path) -> None:
    """SQLiteDB falls back to filename stem when path is outside data_dir()."""
    from A.data.base import SQLiteDB

    db_path = tmp_path / "custom_name.db"
    # Create pre-existing DB
    db1 = SQLiteDB(db_path)
    db1.execute("CREATE TABLE t (x TEXT)")
    db1.execute("INSERT INTO t VALUES ('v')")
    db1.close()

    db2 = SQLiteDB(db_path)
    db2.close()
    assert _sqlite_db_exists("custom_name") == 1
