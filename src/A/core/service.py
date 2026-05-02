"""CRUD service layer for A plugins.

Evidence-based design from autish-legacy (vorto_repo.py).

Usage:
    from A.core.service import CRUDService
    from A.data import SQLiteDB

    db = SQLiteDB("vorto.db")
    words = CRUDService(db, "vorto")
    words.list()
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from A.data.base import SQLiteDB


class CRUDService:
    """CRUD operations with soft-delete and undo support.
    
    Evidence-based from autish-legacy vorto_repo.py:
    - list, get, create, update, delete
    - Soft delete (rubujo table)
    - Undo stack
    - Auto timestamps (kreita_je, modifita_je)
    """

    def __init__(self, db: SQLiteDB, table: str):
        """
        Args:
            db: SQLiteDB instance
            table: Table name for CRUD operations
        """
        self.db = db
        self.table = table
        self._trash_table = f"{table}_rubujo"

    def list(
        self,
        order_by: str = "kreita_je",
        desc: bool = False,
        limit: int = None,
    ) -> list[dict[str, Any]]:
        """List all entries, optionally ordered and limited."""
        order = "DESC" if desc else "ASC"
        sql = f"SELECT * FROM {self.table} ORDER BY {order_by} {order}"
        if limit:
            sql += f" LIMIT {limit}"
        return self.db.execute(sql)

    def get(self, uuid: str) -> dict[str, Any] | None:
        """Get a single entry by UUID."""
        return self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE uuid = ?", (uuid,)
        )

    def get_by_field(self, field: str, value: Any) -> dict[str, Any] | None:
        """Get a single entry by any field."""
        return self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE {field} = ?", (value,)
        )

    def search(
        self, field: str, query: str, case_sensitive: bool = False
    ) -> list[dict[str, Any]]:
        """Search entries by field containing query."""
        if case_sensitive:
            sql = f"SELECT * FROM {self.table} WHERE {field} LIKE ?"
        else:
            sql = f"SELECT * FROM {self.table} WHERE LOWER({field}) LIKE LOWER(?)"
        return self.db.execute(sql, (f"%{query}%",))

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new entry with auto-generated UUID and timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        data["uuid"] = data.get("uuid") or str(uuid.uuid4())
        data["kreita_je"] = data.get("kreita_je", now)
        data["modifita_je"] = now

        # Build insert statement
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.db.transaction() as conn:
            conn.execute(sql, values)

        return data

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an entry, preserving creation timestamp."""
        data["modifita_je"] = datetime.now(timezone.utc).isoformat()

        set_clauses = [f"{k} = ?" for k in data.keys()]
        values = list(data.values()) + [uuid]
        sql = f"UPDATE {self.table} SET {', '.join(set_clauses)} WHERE uuid = ?"

        with self.db.transaction() as conn:
            conn.execute(sql, values)

        return {**self.get(uuid), **data}

    def delete(self, uuid: str, soft: bool = True) -> None:
        """Delete an entry.
        
        Args:
            uuid: Entry UUID
            soft: If True, move to trash table (rubujo). If False, permanent delete.
        """
        if soft:
            self._move_to_trash(uuid)
        else:
            sql = f"DELETE FROM {self.table} WHERE uuid = ?"
            with self.db.transaction() as conn:
                conn.execute(sql, (uuid,))

    def _move_to_trash(self, uuid: str) -> None:
        """Move entry to trash table."""
        entry = self.get(uuid)
        if not entry:
            return

        # Add deletion timestamp
        entry["forigita_je"] = datetime.now(timezone.utc).isoformat()

        # Remove modifita_je (not applicable in trash)
        entry.pop("modifita_je", None)

        # Insert into trash table
        columns = list(entry.keys())
        values = list(entry.values())
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO {self._trash_table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.db.transaction() as conn:
            conn.execute(sql, values)

        # Delete from main table
        delete_sql = f"DELETE FROM {self.table} WHERE uuid = ?"
        conn.execute(delete_sql, (uuid,))

    def restore(self, uuid: str) -> dict[str, Any] | None:
        """Restore entry from trash."""
        sql = f"SELECT * FROM {self._trash_table} WHERE uuid = ?"
        entry = self.db.execute_one(sql, (uuid,))
        if not entry:
            return None

        # Add modification timestamp
        entry["modifita_je"] = datetime.now(timezone.utc).isoformat()
        entry.pop("forigita_je", None)

        # Insert back to main table
        columns = list(entry.keys())
        values = list(entry.values())
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.db.transaction() as conn:
            conn.execute(insert_sql, values)

        # Delete from trash
        delete_sql = f"DELETE FROM {self._trash_table} WHERE uuid = ?"
        conn.execute(delete_sql, (uuid,))

        return entry

    def empty_trash(self, days: int = 30) -> int:
        """Permanently delete entries from trash older than days.
        
        Args:
            days: Delete entries older than this many days
            
        Returns:
            Number of entries deleted
        """
        cutoff = datetime.now(timezone.utc).isoformat()
        sql = f"DELETE FROM {self._trash_table} WHERE forigita_je < datetime(?, ?)"
        
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (cutoff, f"-{days} days"))
            return cursor.rowcount

    # Undo stack operations
    def load_undo_stack(self) -> list[dict[str, Any]]:
        """Load the undo stack."""
        return self.db.execute(
            f"SELECT operation, data, timestamp FROM undo_stack ORDER BY id ASC"
        )

    def push_undo(self, operation: str, data: dict[str, Any]) -> None:
        """Push an operation onto the undo stack."""
        sql = "INSERT INTO undo_stack (operation, data, timestamp) VALUES (?, ?, ?)"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self.db.transaction() as conn:
            conn.execute(sql, (operation, json.dumps(data), timestamp))

    def clear_undo_stack(self) -> None:
        """Clear the undo stack."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM undo_stack")


# Convenience function for quick service creation
def create_service(name: str, table: str) -> CRUDService:
    """Create a CRUDService for the given table.
    
    Args:
        name: Database name (without .db extension)
        table: Table name
        
    Returns:
        CRUDService instance
    """
    db = SQLiteDB(name)
    return CRUDService(db, table)