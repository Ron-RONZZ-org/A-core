"""SQLite base for A data layer."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from A.core.paths import data_dir


class SQLiteDB:
    """Base SQLite database with WAL mode."""
    
    def __init__(self, name: str, schema: dict[str, str] = None):
        """
        Args:
            name: Database name (e.g., "tempo")
            schema: dict of table_name -> CREATE TABLE SQL
        """
        self.path = data_dir() / f"{name}.db"
        self._schema = schema or {}
        
        # Initialize schema if this is a new database
        if schema and not self.path.exists():
            self._init_schema()
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._connection() as conn:
            for table, sql in self._schema.items():
                conn.execute(sql)
            conn.commit()
    
    @contextmanager
    def _connection(self):
        """Get a connection with WAL mode."""
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        
        # Always use Row factory for dict-like access
        conn.row_factory = sqlite3.Row
        
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self):
        """Auto-commit transaction context."""
        with self._connection() as conn:
            yield conn
            conn.commit()
    
    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute SQL and return results as dicts."""
        with self._connection() as conn:
            cursor = conn.execute(sql, params or ())
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    
    def execute_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Execute SQL and return first result."""
        results = self.execute(sql, params)
        return results[0] if results else None
    
    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute SQL with multiple param sets."""
        with self._connection() as conn:
            conn.executemany(sql, params_list)
            conn.commit()