"""Undo system for operations tracking.

Usage:
    from A.core.undo import UndoManager, UndoOperation

    manager = UndoManager(max_size=10)
    manager.push(UndoOperation(
        operation_type="add",
        table="vorto",
        record_uuid="abc-123",
        new_data={"teksto": "hello"},
    ))
    op = manager.undo()  # Returns and removes last operation
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

OperationType = Literal["add", "modify", "delete"]


@dataclass
class UndoOperation:
    """Represents a single operation that can be undone."""

    operation_type: OperationType
    table: str
    record_uuid: str
    old_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "operation_type": self.operation_type,
            "table": self.table,
            "record_uuid": self.record_uuid,
            "old_data": self.old_data,
            "new_data": self.new_data,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UndoOperation:
        """Create from dict (with JSON deserialization)."""
        return cls(
            operation_type=data["operation_type"],
            table=data["table"],
            record_uuid=data["record_uuid"],
            old_data=data.get("old_data"),
            new_data=data.get("new_data"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class UndoManager:
    """In-memory undo stack with configurable size.

    Uses deque with maxlen for O(1) push/pop operations.
    Optionally syncs to database for crash recovery.

    Args:
        max_size: Maximum number of operations to track (default 10)
        db: Optional SQLiteDB for persistent storage
    """

    def __init__(self, max_size: int = 10, db=None):
        self._stack: deque[UndoOperation] = deque(maxlen=max_size)
        self._db = db

    def push(self, operation: UndoOperation) -> None:
        """Add operation to undo stack.
        
        Args:
            operation: The operation to track
        """
        self._stack.append(operation)
        
        # Optional: persist to DB
        if self._db:
            self._persist_operation(operation)

    def undo(self) -> UndoOperation | None:
        """Pop and return the last operation.
        
        Returns:
            The last operation, or None if stack is empty
        """
        try:
            return self._stack.pop()
        except IndexError:
            return None

    def peek(self) -> UndoOperation | None:
        """View the last operation without removing it.
        
        Returns:
            The last operation, or None if stack is empty
        """
        try:
            return self._stack[-1]
        except IndexError:
            return None

    def clear(self) -> None:
        """Clear all operations from the stack."""
        self._stack.clear()
        if self._db:
            self._db.execute("DELETE FROM undo_operations")

    def __len__(self) -> int:
        """Return current stack size."""
        return len(self._stack)

    def __bool__(self) -> bool:
        """Return True if stack has operations."""
        return bool(self._stack)

    # --- DB Persistence ---

    def _ensure_table(self) -> None:
        """Create undo operations table if not exists."""
        if not self._db:
            return
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS undo_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_uuid TEXT NOT NULL,
                old_data TEXT,
                new_data TEXT,
                timestamp TEXT NOT NULL
            )
        """)

    def _persist_operation(self, operation: UndoOperation) -> None:
        """Persist operation to database."""
        if not self._db:
            return
        self._ensure_table()
        self._db.execute(
            """INSERT INTO undo_operations 
               (operation_type, table_name, record_uuid, old_data, new_data, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                operation.operation_type,
                operation.table,
                operation.record_uuid,
                json.dumps(operation.old_data) if operation.old_data else None,
                json.dumps(operation.new_data) if operation.new_data else None,
                operation.timestamp.isoformat(),
            ),
        )

    def load_from_db(self) -> None:
        """Load operations from database (newest first)."""
        if not self._db:
            return
        self._ensure_table()
        rows = self._db.execute(
            "SELECT * FROM undo_operations ORDER BY id DESC"
        )
        self._stack.clear()
        for row in rows:
            self._stack.append(
                UndoOperation(
                    operation_type=row["operation_type"],
                    table=row["table_name"],
                    record_uuid=row["record_uuid"],
                    old_data=json.loads(row["old_data"]) if row["old_data"] else None,
                    new_data=json.loads(row["new_data"]) if row["new_data"] else None,
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
            )
        # Trim to maxlen
        while len(self._stack) > self._stack.maxlen:
            self._stack.remove(self._stack[0])


def create_undo_operation(
    operation_type: OperationType,
    table: str,
    record_uuid: str,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
) -> UndoOperation:
    """Convenience function to create an UndoOperation.
    
    Args:
        operation_type: Type of operation ("add", "modify", "delete")
        table: Table name
        record_uuid: UUID of the affected record
        old_data: Previous state (for modify/delete)
        new_data: New state (for add/modify)
        
    Returns:
        UndoOperation instance
    """
    return UndoOperation(
        operation_type=operation_type,
        table=table,
        record_uuid=record_uuid,
        old_data=old_data,
        new_data=new_data,
    )