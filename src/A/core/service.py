"""CRUD service layer for A plugins.

Evidence-based design from autish-legacy (vorto_repo.py).

Usage:
    from A.core.service import CRUDService
    from A.data import SQLiteDB
    from A.data.search import FTSConfig

    # With FTS5 search
    config = FTSConfig(table="vorto", fts_columns=["teksto"])
    db = SQLiteDB("vorto.db")
    words = CRUDService(db, "vorto", fts_config=config)
    words.search_fts("hello")

    # Without FTS5
    words = CRUDService(db, "vorto")
    words.list()
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from A.data.base import SQLiteDB
from A.data.search import FTSConfig, build_fts_schema, build_search_query, build_index_sql
from A.core.undo import UndoManager, create_undo_operation


class CRUDService:
    """CRUD operations with soft-delete and undo support.

    Evidence-based from autish-legacy vorto_repo.py:
    - list, get, create, update, delete
    - Soft delete (rubujo table)
    - Undo stack
    - Auto timestamps (kreita_je, modifita_je)

    Extended with optional FTS5 full-text search.
    """

    def __init__(
        self,
        db: SQLiteDB,
        table: str,
        fts_config: FTSConfig | None = None,
        undo_size: int = 10,
    ):
        """
        Args:
            db: SQLiteDB instance
            table: Table name for CRUD operations
            fts_config: Optional FTS5 configuration for full-text search
            undo_size: Max size of undo stack (0 to disable)
        """
        self.db = db
        self.table = table
        self._trash_table = f"{table}_rubujo"
        self._fts_config = fts_config

        # Undo support
        self._undo_manager = UndoManager(max_size=undo_size, db=db) if undo_size > 0 else None

        if fts_config:
            self._ensure_fts()

    # --- FTS5 Methods ---

    def _ensure_fts(self) -> None:
        """Create FTS5 schema and populate if empty."""
        for stmt in build_fts_schema(self._fts_config):
            self.db.execute(stmt)

        # Populate FTS if empty
        count = self.db.execute_one(
            f"SELECT COUNT(*) AS cnt FROM {self._fts_config.fts_table}"
        )
        if count and count["cnt"] == 0:
            self._rebuild_fts()

    def _rebuild_fts(self) -> None:
        """Rebuild the entire FTS index from main table."""
        self.db.execute(
            f"INSERT INTO {self._fts_config.fts_table}"
            f"({self._fts_config.fts_table}) VALUES('rebuild')"
        )

    def _index_fts(self, uuid: str) -> None:
        """Index a single entry in FTS5."""
        if not self._fts_config:
            return
        # Get current values for FTS columns
        entry = self.db.execute_one(
            f"SELECT rowid, uuid, "
            f"{', '.join(self._fts_config.fts_columns)} "
            f"FROM {self.table} WHERE uuid = ?",
            (uuid,)
        )
        if not entry:
            return
        sql, params = build_index_sql(
            self._fts_config, uuid, dict(entry), entry["rowid"]
        )
        self.db.execute(sql, params)

    def _remove_from_fts(self, uuid: str) -> None:
        """Remove an entry from FTS5 index."""
        if not self._fts_config:
            return
        self.db.execute(
            f"INSERT INTO {self._fts_config.fts_table}"
            f"({self._fts_config.fts_table}, rowid) "
            f"VALUES('delete', "
            f"(SELECT rowid FROM {self.table} WHERE uuid = ?))",
            (uuid,)
        )

    # --- Basic List/Get/Search ---

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

    # --- Advanced Search Methods ---

    def search_fts(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        order_by: str = "relevance",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Full-text search via FTS5 with filters and sorting.

        Args:
            query: Search text (normalized automatically)
            filters: Exact match filters e.g. {"lingvo": "fr", "kategorio": "verbo"}
            order_by: "relevance" (BM25), "date", "date_asc", or column name
            limit: Max results
            offset: Pagination offset

        Returns:
            List of matching entries from main table

        Raises:
            ValueError: If FTS5 is not configured on this service
        """
        if not self._fts_config:
            raise ValueError(
                "FTS5 not configured for this service. "
                "Pass fts_config to constructor."
            )

        try:
            sql, params = build_search_query(
                self._fts_config, query, filters, order_by, limit, offset
            )
            return self.db.execute(sql, tuple(params))
        except Exception:
            # Fallback: LIKE search on first indexed column
            fallback_field = self._fts_config.fts_columns[0]
            return self.search(fallback_field, query, case_sensitive=False)[:limit]

    def search_fuzzy(
        self,
        query: str,
        field: str = "",
        threshold: float = 0.62,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fuzzy search using rapidfuzz (optional) with difflib fallback.

        Args:
            query: Search text
            field: Column to search (if empty, uses first FTS column or "teksto")
            threshold: Minimum similarity score (0.0-1.0)
            limit: Max results
        """
        # First pass: get candidates via FTS5 (fast narrowing)
        candidates = []
        if self._fts_config:
            candidates = self.search_fts(query, limit=limit * 3)
        else:
            target_field = field or "teksto"
            candidates = self.search(target_field, query, case_sensitive=False)[:limit * 3]

        if not candidates:
            return []

        # Try rapidfuzz (optional)
        try:
            from rapidfuzz import fuzz, process
            from A.utils.normalize import fold_search_text

            target_field = field or (
                self._fts_config.fts_columns[0] if self._fts_config else "teksto"
            )
            texts = [str(e.get(target_field, "")) for e in candidates]
            folded_query = fold_search_text(query)
            folded_texts = [fold_search_text(t) for t in texts]

            results = process.extract(
                folded_query,
                folded_texts,
                scorer=fuzz.ratio,
                limit=limit,
                score_cutoff=threshold * 100,  # rapidfuzz uses 0-100 scale
            )

            return [candidates[idx] for _, idx, _ in results]
        except ImportError:
            # Fall back to difflib (stdlib but slower)
            from difflib import SequenceMatcher

            target_field = field or (
                self._fts_config.fts_columns[0] if self._fts_config else "teksto"
            )
            scored = []
            for entry in candidates:
                text = str(entry.get(target_field, ""))
                score = SequenceMatcher(
                    None, query.casefold(), text.casefold()
                ).ratio()
                if score >= threshold:
                    scored.append((score, entry))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:limit]]

    def search_advanced(
        self,
        query: str = "",
        filters: dict[str, str] | None = None,
        fuzzy: bool = False,
        order_by: str = "relevance",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Combined search: FTS5 + filters + optional fuzzy scoring.

        Priority:
        1. FTS5 (fast, built-in)
        2. Optional fuzzy re-ranking (rapidfuzz if available)
        3. LIKE fallback
        """
        if not query and not filters:
            return self.list(order_by="kreita_je", desc=True, limit=limit)

        results = self.search_fts(query, filters, order_by, limit)

        if fuzzy and results and query:
            results = self.search_fuzzy(query, limit=limit)

        return results

    # --- CRUD Operations ---

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

        # FTS indexing after successful insert
        if self._fts_config:
            self._index_fts(data["uuid"])

        # Track for undo
        if self._undo_manager:
            self._undo_manager.push(create_undo_operation(
                operation_type="add",
                table=self.table,
                record_uuid=data["uuid"],
                new_data=data.copy(),
            ))

        return data

    def update(self, uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an entry, preserving creation timestamp."""
        # Get old data for undo tracking
        old_data = self.get(uuid)

        data["modifita_je"] = datetime.now(timezone.utc).isoformat()

        set_clauses = [f"{k} = ?" for k in data.keys()]
        values = list(data.values()) + [uuid]
        sql = f"UPDATE {self.table} SET {', '.join(set_clauses)} WHERE uuid = ?"

        with self.db.transaction() as conn:
            conn.execute(sql, values)

        # Re-index in FTS
        if self._fts_config:
            self._remove_from_fts(uuid)
            self._index_fts(uuid)

        # Track for undo
        if self._undo_manager and old_data:
            self._undo_manager.push(create_undo_operation(
                operation_type="modify",
                table=self.table,
                record_uuid=uuid,
                old_data=old_data,
                new_data=data,
            ))

        return {**self.get(uuid), **data}

    def delete(self, uuid: str, soft: bool = True) -> None:
        """Delete an entry.

        Args:
            uuid: Entry UUID
            soft: If True, move to trash table (rubujo). If False, permanent delete.
        """
        # Get old data for undo tracking
        old_data = self.get(uuid)

        if soft:
            self._move_to_trash(uuid)
        else:
            # Remove from FTS before hard delete
            if self._fts_config:
                self._remove_from_fts(uuid)
            sql = f"DELETE FROM {self.table} WHERE uuid = ?"
            with self.db.transaction() as conn:
                conn.execute(sql, (uuid,))

        # Track for undo
        if self._undo_manager and old_data:
            self._undo_manager.push(create_undo_operation(
                operation_type="delete",
                table=self.table,
                record_uuid=uuid,
                old_data=old_data,
            ))

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
        if self._undo_manager:
            self._undo_manager.clear()
        # Also clear legacy DB-based stack
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM undo_stack")

    def undo(self) -> dict[str, Any] | None:
        """Undo the last operation.

        Returns:
            The undone operation details, or None if nothing to undo or undo is disabled
        """
        if not self._undo_manager:
            return None

        operation = self._undo_manager.undo()
        if not operation:
            return None

        # Perform the actual undo based on operation type
        if operation.operation_type == "add":
            # Undo add = delete the record (hard delete to avoid nested tracking)
            sql = f"DELETE FROM {self.table} WHERE uuid = ?"
            with self.db.transaction() as conn:
                conn.execute(sql, (operation.record_uuid,))
            # Remove from FTS if enabled
            if self._fts_config:
                self._remove_from_fts(operation.record_uuid)

        elif operation.operation_type == "modify":
            # Undo modify = restore old data
            if operation.old_data:
                # Filter out auto-generated fields
                old_data = {k: v for k, v in operation.old_data.items()
                            if k not in ("uuid", "kreita_je")}
                old_data["modifita_je"] = datetime.now(timezone.utc).isoformat()
                set_clauses = [f"{k} = ?" for k in old_data.keys()]
                values = list(old_data.values()) + [operation.record_uuid]
                sql = f"UPDATE {self.table} SET {', '.join(set_clauses)} WHERE uuid = ?"
                with self.db.transaction() as conn:
                    conn.execute(sql, values)
                # Re-index in FTS
                if self._fts_config:
                    self._remove_from_fts(operation.record_uuid)
                    self._index_fts(operation.record_uuid)

        elif operation.operation_type == "delete":
            # Undo delete = restore the record
            if operation.old_data:
                # Restore with original creation time, remove trash fields
                restored = {k: v for k, v in operation.old_data.items()
                           if k != "forigita_je"}
                restored["modifita_je"] = datetime.now(timezone.utc).isoformat()
                columns = list(restored.keys())
                values = list(restored.values())
                placeholders = ", ".join(["?"] * len(columns))
                sql = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"
                with self.db.transaction() as conn:
                    conn.execute(sql, values)
                # Re-index in FTS
                if self._fts_config:
                    self._index_fts(restored["uuid"])

        return operation.to_dict()


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