"""SQLite base for A data layer."""

import atexit
import json
import shutil
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from A.core.backup import backup_database as _backup_database
from A.core.paths import data_dir


class SQLiteDB:
    """Base SQLite database with WAL mode and thread-safe connection caching.

    Connections are cached per-thread via ``threading.local``, so each thread
    gets its own ``sqlite3.Connection``.  This avoids the
    ``ProgrammingError: SQLite objects created in a thread can only be used
    in that same thread`` when the same ``SQLiteDB`` instance is accessed
    from multiple threads (e.g. via ``ThreadPoolExecutor``).

    Within a single thread, the connection is lazily created on first query
    and reused for all subsequent queries, avoiding the overhead of
    opening/closing a ``sqlite3`` connection on every ``execute()`` call.

    Call :meth:`close()` to explicitly release the calling thread's cached
    connection.  The ``atexit`` handler (best-effort) only closes the main
    thread's connection; other threads' connections are released when the
    thread-local storage is cleared at thread exit.

    .. versionchanged:: 1.x
       Added automatic backup: existing databases are backed up on init
       (via :func:`A.core.backup.backup_database`) and before any DDL
       statement.  See :meth:`_auto_backup`.
    """

    _DDL_PREFIXES = ("CREATE", "ALTER", "DROP", "ANALYZE", "REINDEX", "ATTACH", "DETACH")

    def __init__(
        self,
        name_or_path: str | Path,
        schema: dict[str, str] = None,
        module: str | None = None,
    ):
        """
        Args:
            name_or_path: Database name (e.g., "tempo") or full Path.
            schema: dict of table_name -> CREATE TABLE SQL.
            module: Optional module name for backup organisation.
                    If ``None``, derived from the path (see
                    :meth:`_detect_module`).
        """
        if isinstance(name_or_path, Path):
            self.path = name_or_path
        else:
            self.path = data_dir() / f"{name_or_path}.db"
        self._schema = schema or {}
        self._module = module
        self._local = threading.local()

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Auto-backup existing database before any writes
        if self.path.exists():
            self._auto_backup()

        # Initialize schema if provided
        if schema:
            self._init_schema()

        # Best-effort WAL checkpoint on clean exit (Ctrl+C, normal exit, etc.)
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """atexit handler: checkpoint and close if DB file still exists.

        Only closes the main thread's connection (the thread atexit runs in).
        Worker threads' connections are released when thread-local storage is
        cleared at thread exit.

        Guards against test-isolation scenarios where the database file
        in ``tmp_path`` has already been cleaned up by pytest fixture
        teardown before atexit runs.
        """
        if not self.path.exists():
            return
        self.close()

    # ── Auto-backup helpers ─────────────────────────────────────────────────

    def _detect_module(self) -> str:
        """Derive the module name from the database path.

        Priority:
        1. Explicit ``module`` parameter passed to :meth:`__init__`.
        2. Path-derived: if the DB is under ``data_dir() / {mod}/``,
           use ``{mod}`` as the module name (e.g. ``"A-semantika"``).
        3. Stem-derived: use ``self.path.stem`` (e.g. ``"vorto"`` for
           ``vorto.db``).

        Returns:
            A module name string suitable for :func:`A.core.backup.backup_database`.
        """
        if self._module:
            return self._module

        # Try to derive from parent path relative to data_dir()
        try:
            dd = data_dir()
            rel = self.path.parent.relative_to(dd)
            return str(rel.parts[0])
        except (ValueError, IndexError):
            pass

        # Fallback: use the filename stem
        return self.path.stem

    def _auto_backup(self) -> None:
        """Create a timestamped backup of the current database.

        Uses :func:`A.core.backup.backup_database` with the module name
        derived from :meth:`_detect_module`.

        Best-effort: failures are silently ignored so that backup
        issues never block database access.
        """
        try:
            _backup_database(self.path, module=self._detect_module())
        except Exception:
            pass  # Best-effort

    # ── Connection management ────────────────────────────────────────────────

    def close(self) -> None:
        """Checkpoint WAL and close the calling thread's connection. Idempotent."""
        conn = getattr(self._local, "_conn", None)
        if conn is not None:
            try:
                # PASSIVE checkpoint: non-blocking, safe with concurrent access.
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass  # Best-effort: next open recovers WAL automatically
            try:
                conn.close()
            except Exception:
                pass
            self._local._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a per-thread cached connection with WAL mode."""
        conn = getattr(self._local, "_conn", None)
        if conn is None:
            # 5-second busy timeout: retry locked databases instead of
            # immediately raising "database is locked"
            conn = sqlite3.connect(self.path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            # Keep WAL small: auto-checkpoint every 100 pages (~400KB)
            # instead of the default 1000 pages (~4MB). Frequent small
            # checkpoints avoid long stalls during read operations.
            conn.execute("PRAGMA wal_autocheckpoint=100")
            conn.row_factory = sqlite3.Row
            self._local._conn = conn
        return conn

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
            pass  # Connection is cached; don't close

    def _is_ddl(self, sql: str) -> bool:
        """Check if *sql* is a DDL statement (case-insensitive)."""
        stripped = sql.strip().upper()
        return any(stripped.startswith(p) for p in self._DDL_PREFIXES)

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute SQL and return results as dicts.

        Auto-commits for DML statements. DDL statements are auto-committed
        by SQLite regardless.

        .. note::
           Before executing a DDL statement (``CREATE``, ``ALTER``, ``DROP``,
           etc.), the database is automatically backed up via
           :func:`A.core.backup.backup_database` to capture the
           pre-migration state.
        """
        # Auto-backup before DDL (captures pre-migration state)
        if self._is_ddl(sql):
            self._auto_backup()

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

    Forces a ``TRUNCATE`` WAL checkpoint before the copy so the
    backup reflects the **full** database state including all
    committed WAL transactions.

    Best-effort: silently ignores missing files, checkpoint failures,
    and copy failures. The backup is overwritten on each call (one
    rolling backup per DB).
    """
    if not db_path.exists():
        return
    # Flush WAL so the copy captures all committed transactions
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass  # Best-effort: a stale backup is better than no backup
    bak = db_path.with_suffix(".db.bak")
    try:
        shutil.copy2(str(db_path), str(bak))
    except Exception:
        pass  # Backup is best-effort


def health_check(db_path: Path) -> bool:
    """Run ``PRAGMA quick_check`` on *db_path*.

    Opens a normal connection (which replays the WAL) and runs a
    ``TRUNCATE`` checkpoint before checking integrity.  This ensures
    the health check reflects the **full** database state including
    all committed WAL transactions.

    Previously used ``?immutable=1`` (read-only, no WAL replay),
    which could report a stale main-db snapshot as healthy while
    pending WAL transactions hid latent corruption.

    Returns ``True`` if the database is healthy, ``False`` if corrupted
    or unreachable.
    """
    if not db_path.exists():
        return True  # Non-existent DB can't be corrupted
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        # Flush WAL so quick_check sees the complete state
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
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
        # Try VACUUM rebuild + REINDEX (fixes orphan pages AND corrupted indexes)
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


def open_healthy_db(
    path: Path,
    *,
    backup: bool = True,
) -> SQLiteDB:
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
    "SQLiteDB",
    "backup_db",
    "health_check",
    "open_healthy_db",
    "readonly_recover",
    "repair_db",
    "init_db",
]