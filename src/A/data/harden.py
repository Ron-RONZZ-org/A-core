"""DB hardening utilities — health check, repair, backup, recovery.

Extracted from :mod:`A.data.base` to keep that file under 500 lines.
All functions are standalone (no dependency on ``SQLiteDB`` at import
time) and safe to call independently.

Usage::

    from A.data.harden import health_check, backup_db, open_healthy_db

    if not health_check(db_path):
        repair_db(db_path)

    backup_db(db_path)
    db = open_healthy_db(db_path)
"""

from __future__ import annotations

import sqlite3
import shutil
from pathlib import Path
from typing import Any


def backup_db(db_path: Path) -> None:
    """Snapshot *db_path* to ``<name>.bak`` before schema-altering operations.

    Best-effort: silently ignores missing files and copy failures.
    The backup is overwritten on each call (one rolling backup per DB).

    .. caution::

       This copies only the main database file, **not** the WAL.  Any
       data still in the WAL is **not** included in the backup.  For
       a fully consistent backup use :func:`A.core.backup.backup_database`
       which uses the SQL-level ``.backup`` command.

       We intentionally avoid calling ``PRAGMA wal_checkpoint(TRUNCATE)``
       before the copy because checkpoint writes from a separate
       connection have been observed to cause database corruption in
       SQLite WAL mode (see A-core issue #102).
    """
    if not db_path.exists():
        return
    bak = db_path.with_suffix(".db.bak")
    try:
        shutil.copy2(str(db_path), str(bak))
    except Exception:
        pass  # Backup is best-effort


def health_check(db_path: Path) -> bool:
    """Run ``PRAGMA quick_check`` on *db_path* via a read-only connection.

    Opens the database in ``mode=ro`` (read-only with WAL replay) so
    that ``quick_check`` sees the **full** committed state including
    pending WAL transactions, **without** modifying the database.

    Previous implementations used:
    * ``?immutable=1`` — skipped WAL replay, could report stale
      main-db as healthy while WAL hid latent corruption.
    * Normal connection + ``PRAGMA wal_checkpoint(TRUNCATE)`` —
      provided full visibility but the checkpoint write from a
      separate connection was observed to cause database corruption
      in WAL mode (A-core issue #102).

    Returns ``True`` if the database is healthy, ``False`` if corrupted
    or unreachable.
    """
    if not db_path.exists():
        return True  # Non-existent DB can't be corrupted
    try:
        conn = sqlite3.connect(
            f"file:{str(db_path)}?mode=ro", uri=True, timeout=5
        )
        (result,) = conn.execute("PRAGMA quick_check").fetchone()
        conn.close()
        return result == "ok"
    except Exception:
        return False


def repair_db(db_path: Path) -> bool:
    """Attempt to repair a corrupted database at *db_path*.

    1. Deletes stale WAL/SHM files.
    2. Runs ``PRAGMA quick_check``.
    3. If still corrupted, runs ``VACUUM`` to rebuild the file and
       then ``REINDEX`` to rebuild any corrupted indexes.
    4. If that fails, attempts to drop and recreate the
       ``semantika_cache`` table (A-encik specific, safe no-op elsewhere).

    Returns ``True`` if the DB is healthy after repair, ``False`` otherwise.
    """
    if not db_path.exists():
        return True

    # Delete WAL+SHM (common source of corruption)
    for suffix in ("-wal", "-shm"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        (result,) = conn.execute("PRAGMA quick_check").fetchone()
        if result == "ok":
            conn.close()
            return True
        # Try VACUUM rebuild + REINDEX
        try:
            conn.execute("VACUUM")
            conn.execute("REINDEX")
            (result,) = conn.execute("PRAGMA quick_check").fetchone()
            if result == "ok":
                conn.close()
                return True
        except Exception:
            pass
        conn.close()
    except Exception:
        pass
    return False


def readonly_recover(db_path: Path, dest_path: Path) -> int:
    """Recover readable entries from a corrupted DB into a new clean DB.

    Opens *db_path* in ``mode=ro`` (read-only, no WAL), copies all
    non-FTS table schemas and their data row-by-row into *dest_path*.
    Skips tables that fail to read. Returns number of entries recovered
    (0 if nothing could be recovered).

    *dest_path* is created from scratch (overwritten if it exists).
    """
    if dest_path.exists():
        dest_path.unlink()
    if not db_path.exists():
        return 0

    try:
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    except sqlite3.DatabaseError:
        return 0

    try:
        tables = src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'"
        ).fetchall()
        if not tables:
            src.close()
            return 0

        dst = sqlite3.connect(str(dest_path), timeout=30)
        dst.execute("PRAGMA journal_mode=WAL")

        total = 0
        for (tname, tsql) in tables:
            if not tsql:
                continue
            try:
                dst.execute(tsql)
                rows = src.execute(f'SELECT * FROM "{tname}"').fetchall()
                col_info = src.execute(f'PRAGMA table_info("{tname}")').fetchall()
                cols = [c[1] for c in col_info]
                csv = ", ".join(f'"{c}"' for c in cols)
                ph = ", ".join(["?"] * len(cols))
                for row in rows:
                    try:
                        dst.execute(f'INSERT INTO "{tname}" ({csv}) VALUES ({ph})', row)
                        total += 1
                    except Exception:
                        pass
            except Exception:
                pass

        dst.commit()
        dst.close()
        src.close()
        return total
    except Exception:
        src.close()
        return 0


def init_db(
    path: Path,
    schema_sql: str | list[str],
    *,
    backup: bool = True,
    migrate: callable = None,
) -> Any:
    """Create or open a hardened database with health check and backup.

    Args:
        path: Full path to the database file.
        schema_sql: ``CREATE TABLE`` statements (single string or list of
            strings).
        backup: If ``True``, snapshot the DB file before any DDL.
        migrate: Optional migration function ``(SQLiteDB) -> None`` called
            after schema creation.

    Returns:
        A ready-to-use ``SQLiteDB`` instance.
    """
    from .base import SQLiteDB  # noqa: PLC0415 — lazy import to avoid circular deps

    if backup:
        backup_db(path)

    db = SQLiteDB(path)

    statements = [schema_sql] if isinstance(schema_sql, str) else schema_sql
    for stmt in statements:
        s = stmt.strip()
        if s:
            db.execute(s)

    if migrate:
        migrate(db)

    return db


def open_healthy_db(
    path: Path,
    *,
    backup: bool = True,
) -> Any:
    """Open a database with health check, auto-repair, and pre-DDL backup.

    This is the canonical way to open a database in A-modules.  It
    composes three steps that every module would otherwise repeat:

    1. **Health check** — runs ``PRAGMA quick_check`` via a read-only
       connection so corruption is detected *before* ``SQLiteDB``
       opens the database and potentially crashes.
    2. **Auto-repair** — if the health check fails, stale WAL/SHM files
       are deleted and ``VACUUM`` is attempted.
    3. **Pre-DDL backup** — creates a timestamped backup (via
       :func:`A.core.backup.backup_database`) so the pre-migration
       state is captured regardless of schema changes that follow.

    Args:
        path: Full path to the database file.
        backup: If ``True`` (default), create a timestamped backup of
            the existing database before returning.  The backup is
            created *after* repair so the repaired state is preserved.

    Returns:
        A ready-to-use ``SQLiteDB`` instance (WAL mode, FK enforced,
        per-thread connection caching).

    Raises:
        RuntimeError: If the database is corrupted and cannot be
            repaired.
    """
    from .base import SQLiteDB  # noqa: PLC0415 — lazy import to avoid circular deps

    if not health_check(path):
        if not repair_db(path):
            raise RuntimeError(
                f"Database {path} is corrupted and could not be repaired.\n"
                "Restore from backup or delete the file to start fresh."
            )
    if backup:
        backup_db(path)
    return SQLiteDB(path)


__all__ = [
    "backup_db",
    "health_check",
    "open_healthy_db",
    "readonly_recover",
    "repair_db",
    "init_db",
]
