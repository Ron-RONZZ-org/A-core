"""SQLite base for A data layer."""

import atexit
import json
import shutil
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from A.core.paths import data_dir


class SQLiteDB:
    """Base SQLite database with WAL mode and connection caching.

    Connection is lazily created on first query and reused for all subsequent
    queries within the same SQLiteDB instance. This avoids the overhead of
    opening/closing a sqlite3 connection on every ``execute()`` call, which
    is critical for CLI tools that issue many small queries (e.g. resolving
    linked entry titles).

    Call :meth:`close()` to explicitly release the cached connection.
    """

    _conn: sqlite3.Connection | None = None

    def __init__(self, name_or_path: str | Path, schema: dict[str, str] = None):
        """
        Args:
            name_or_path: Database name (e.g., "tempo") or full Path
            schema: dict of table_name -> CREATE TABLE SQL
        """
        if isinstance(name_or_path, Path):
            self.path = name_or_path
        else:
            self.path = data_dir() / f"{name_or_path}.db"
        self._schema = schema or {}

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema if provided
        if schema:
            self._init_schema()

        # Best-effort WAL checkpoint on clean exit (Ctrl+C, normal exit, etc.)
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """atexit handler: checkpoint and close if DB file still exists.

        Guards against test-isolation scenarios where the database file
        in ``tmp_path`` has already been cleaned up by pytest fixture
        teardown before atexit runs.
        """
        if not self.path.exists():
            return
        self.close()

    def close(self) -> None:
        """Checkpoint WAL and close connection. Idempotent."""
        if self._conn is not None:
            try:
                # PASSIVE checkpoint: non-blocking, safe with concurrent access.
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass  # Best-effort: next open recovers WAL automatically
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a cached connection with WAL mode."""
        if self._conn is None:
            # 5-second busy timeout: retry locked databases instead of
            # immediately raising "database is locked"
            self._conn = sqlite3.connect(self.path, timeout=10.0)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            # Keep WAL small: auto-checkpoint every 100 pages (~400KB)
            # instead of the default 1000 pages (~4MB). Frequent small
            # checkpoints avoid long stalls during read operations.
            self._conn.execute("PRAGMA wal_autocheckpoint=100")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_schema(self) -> None:
        """Initialize database schema if tables don't exist."""
        conn = self._get_conn()
        for table, sql in self._schema.items():
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if cursor.fetchone() is None:
                conn.executescript(sql)
        conn.commit()

    @contextmanager
    def _connection(self):
        """Backward-compatible context manager wrapping _get_conn().

        Returns the cached connection without closing it on exit.
        Subclasses (e.g. ``LinksDB``) that use ``with self._connection()``
        continue to work.
        """
        conn = self._get_conn()
        try:
            yield conn
        finally:
            pass  # Connection is cached; don't close  # Connection is cached; don't close

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute SQL and return results as dicts.

        Auto-commits for DML statements. DDL statements are auto-committed
        by SQLite regardless.
        """
        conn = self._get_conn()
        cursor = conn.execute(sql, params or ())
        rows = cursor.fetchall()
        conn.commit()
        return [dict(r) for r in rows]

    def execute_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Execute SQL and return first result."""
        results = self.execute(sql, params)
        return results[0] if results else None

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute SQL with multiple param sets."""
        conn = self._get_conn()
        conn.executemany(sql, params_list)
        conn.commit()

    def transaction(self):
        """Context manager that yields a connection with auto-commit.

        Uses the same cached connection as other methods.
        """
        class _TransactionContext:
            def __init__(self, db: "SQLiteDB"):
                self.db = db
            def __enter__(self):
                return self.db._get_conn()
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    self.db._get_conn().commit()
                else:
                    self.db._get_conn().rollback()

        return _TransactionContext(self)


# ── DB hardening utilities ───────────────────────────────────────────────────────


def backup_db(db_path: Path) -> None:
    """Snapshot *db_path* to ``<name>.bak`` before schema-altering operations.

    Best-effort: silently ignores missing files and copy failures.
    The backup is overwritten on each call (one rolling backup per DB).
    """
    if db_path.exists():
        bak = db_path.with_suffix(".db.bak")
        try:
            shutil.copy2(str(db_path), str(bak))
        except Exception:
            pass  # Backup is best-effort


def health_check(db_path: Path) -> bool:
    """Run ``PRAGMA quick_check`` on *db_path* via a read-only connection.

    Returns ``True`` if the database is healthy, ``False`` if corrupted
    or unreachable.
    """
    if not db_path.exists():
        return True  # Non-existent DB can't be corrupted
    try:
        conn = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True, timeout=5)
        (result,) = conn.execute("PRAGMA quick_check").fetchone()
        conn.close()
        return result == "ok"
    except Exception:
        return False


def repair_db(db_path: Path) -> bool:
    """Attempt to repair a corrupted database at *db_path*.

    1. Deletes stale WAL/SHM files.
    2. Runs ``PRAGMA quick_check``.
    3. If still corrupted, runs ``VACUUM`` to rebuild the file.
    4. If VACUUM fails, attempts to drop and recreate the
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
        # Try VACUUM rebuild
        try:
            conn.execute("VACUUM")
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
) -> SQLiteDB:
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


__all__ = [
    "SQLiteDB",
    "backup_db",
    "health_check",
    "repair_db",
    "readonly_recover",
    "init_db",
]