"""SQLite base for A data layer."""
 
import atexit
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from A.core.backup import backup_database as _backup_database
from A.core.paths import data_dir

# Re-export DB hardening utilities from the dedicated module.
# These were moved to keep this file under 500 lines.
from A.data.harden import (  # noqa: F401 — public API re-export
    backup_db,
    health_check,
    init_db,
    open_healthy_db,
    readonly_recover,
    repair_db,
)


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

        # Best-effort WAL checkpoint on clean exit
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
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            self._local._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a per-thread cached connection with WAL mode."""
        conn = getattr(self._local, "_conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
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
        """Backward-compatible context manager wrapping _get_conn()."""
        conn = self._get_conn()
        try:
            yield conn
        finally:
            pass

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
        """Context manager that yields a connection with auto-commit."""
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


__all__ = [
    "SQLiteDB",
    "backup_db",
    "health_check",
    "open_healthy_db",
    "readonly_recover",
    "repair_db",
    "init_db",
]
