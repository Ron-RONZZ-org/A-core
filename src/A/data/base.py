"""SQLite base for A data layer."""

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

    def close(self) -> None:
        """Close the cached connection, if open. Idempotent."""
        if self._conn is not None:
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
            self._conn = sqlite3.connect(self.path, timeout=5.0)
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
            pass  # Connection is cached; don't close

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