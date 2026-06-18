"""SQLite base for A data layer."""
 
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Any

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

    """

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

        # Initialize schema if provided
        if schema:
            self._init_schema()

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
