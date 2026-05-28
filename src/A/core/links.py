"""Bidirectional links module for A.

Provides adjacency list storage for cross-module links.
When entry A links to entry B, the link is stored and queryable
in both directions (outgoing from A, incoming to B).
"""

import functools
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from A.data.base import SQLiteDB

# Module identifier for links table
LINKS_DB = "links"

# Links table schema
LINKS_SCHEMA = {
    "links": """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_type, source_id, target_type, target_id)
        );
        CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_type, target_id);
    """
}


def _retry_on_lock(
    retries: int = 10,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
):
    """Decorator: retry a method on ``sqlite3.OperationalError`` (DB locked).

    Does **not** close the cached connection — a busy timeout does not
    corrupt it.  The same connection is reused for each retry, and SQLite's
    internal busy handler exits as soon as the lock is released (not after
    the full timeout).

    Args:
        retries: Max retries (default 10, for 11 total attempts).
        base_delay: Initial delay in seconds (doubles each attempt).
        max_delay: Cap for exponential backoff (default 10s).
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    return method(self, *args, **kwargs)
                except sqlite3.OperationalError as exc:
                    last_exc = exc
                    if attempt < retries:
                        delay = min(max_delay, base_delay * (2**attempt))
                        time.sleep(delay)
            msg = (
                f"Database locked after {retries + 1} attempts ({retries} retries). "
                f"Close other A terminals and try again."
            )
            raise RuntimeError(msg) from last_exc

        return wrapper

    return decorator


@dataclass
class Link:
    """Represents a directed link between two entries."""
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


class LinksDB(SQLiteDB):
    """Database for managing bidirectional links."""
    
    def __init__(self):
        super().__init__(LINKS_DB, LINKS_SCHEMA)
    
    @_retry_on_lock()
    def add_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> Link | None:
        """Add a bidirectional link between two entries.
        
        Args:
            source_type: Type of source (e.g., 'vorto', 'encik')
            source_id: UUID of source entry
            target_type: Type of target
            target_id: UUID of target entry
            
        Returns:
            Link object if created, None if already exists
        """
        if source_id == target_id:
            return None  # Don't link to self
            
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO links (source_type, source_id, target_type, target_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (source_type, source_id, target_type, target_id, now)
                )
                conn.commit()
            return Link(source_type, source_id, target_type, target_id, now)
        except Exception:
            # Already exists or other error
            return None

    @_retry_on_lock()
    def bulk_add_links(
        self,
        links: list[tuple[str, str, str, str]],
        source_type_default: str | None = None,
        target_type_default: str | None = None,
    ) -> int:
        """Add multiple links in a single transaction (batch insert).

        Self-links (same source and target ID) are silently skipped.

        Args:
            links: Each tuple is ``(source_id, target_id)`` or
                   ``(source_type, source_id, target_type, target_id)``.
                   If 2-tuples are given, ``source_type_default`` and
                   ``target_type_default`` are used.
            source_type_default: Default source type for 2-tuple entries.
            target_type_default: Default target type for 2-tuple entries.

        Returns:
            Number of links actually inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows: list[tuple[str, str, str, str, str]] = []
        for entry in links:
            if len(entry) == 2:
                sid, tid = entry
                st = source_type_default or "vorto"
                tt = target_type_default or "vorto"
            else:
                st, sid, tt, tid = entry
            if sid != tid:
                rows.append((st, sid, tt, tid, now))

        if not rows:
            return 0

        with self._connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO links
                    (source_type, source_id, target_type, target_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return conn.total_changes
    
    @_retry_on_lock()
    def remove_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> bool:
        """Remove a link between two entries.
        
        Args:
            source_type: Type of source
            source_id: UUID of source entry
            target_type: Type of target
            target_id: UUID of target entry
            
        Returns:
            True if removed, False if not found
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM links 
                WHERE source_type = ? AND source_id = ? 
                  AND target_type = ? AND target_id = ?
                """,
                (source_type, source_id, target_type, target_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_outgoing(
        self,
        source_type: str,
        source_id: str,
    ) -> list[Link]:
        """Get all outgoing links from an entry.
        
        Args:
            source_type: Type of source
            source_id: UUID of source entry
            
        Returns:
            List of Link objects
        """
        results = self.execute(
            """
            SELECT source_type, source_id, target_type, target_id, created_at
            FROM links
            WHERE source_type = ? AND source_id = ?
            ORDER BY created_at DESC
            """,
            (source_type, source_id)
        )
        return [Link(**r) for r in results]
    
    def get_incoming(
        self,
        target_type: str,
        target_id: str,
    ) -> list[Link]:
        """Get all incoming links to an entry (backlinks).
        
        Args:
            target_type: Type of target
            target_id: UUID of target entry
            
        Returns:
            List of Link objects pointing to this entry
        """
        results = self.execute(
            """
            SELECT source_type, source_id, target_type, target_id, created_at
            FROM links
            WHERE target_type = ? AND target_id = ?
            ORDER BY created_at DESC
            """,
            (target_type, target_id)
        )
        return [Link(**r) for r in results]
    
    def get_links(
        self,
        source_type: str,
        source_id: str,
    ) -> dict[str, list[Link]]:
        """Get both outgoing and incoming links for an entry.
        
        Args:
            source_type: Type of entry
            source_id: UUID of entry
            
        Returns:
            Dict with 'outgoing' and 'incoming' lists
        """
        return {
            "outgoing": self.get_outgoing(source_type, source_id),
            "incoming": self.get_incoming(source_type, source_id),
        }
    
    def link_exists(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> bool:
        """Check if a link exists.
        
        Args:
            source_type: Type of source
            source_id: UUID of source entry
            target_type: Type of target
            target_id: UUID of target entry
            
        Returns:
            True if link exists
        """
        result = self.execute_one(
            """
            SELECT 1 FROM links
            WHERE source_type = ? AND source_id = ?
              AND target_type = ? AND target_id = ?
            """,
            (source_type, source_id, target_type, target_id)
        )
        return result is not None
    
    @_retry_on_lock()
    def remove_all_for_entry(
        self,
        entry_type: str,
        entry_id: str,
    ) -> int:
        """Remove all links associated with an entry (both as source and target).
        
        Useful when deleting an entry.
        
        Args:
            entry_type: Type of entry
            entry_id: UUID of entry
            
        Returns:
            Number of links removed
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM links
                WHERE (source_type = ? AND source_id = ?)
                   OR (target_type = ? AND target_id = ?)
                """,
                (entry_type, entry_id, entry_type, entry_id)
            )
            conn.commit()
            return cursor.rowcount
    
    def update_target(
        self,
        old_target_id: str,
        new_target_id: str,
        target_type: str,
    ) -> int:
        """Update all links pointing to old target to point to new target.
        
        Useful when merging entries.
        
        Args:
            old_target_id: Old UUID
            new_target_id: New UUID
            target_type: Type of target entries
            
        Returns:
            Number of links updated
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE links
                SET target_id = ?
                WHERE target_type = ? AND target_id = ?
                """,
                (new_target_id, target_type, old_target_id)
            )
            conn.commit()
            return cursor.rowcount
    
    def get_linked_entries(
        self,
        entry_type: str,
        entry_id: str,
    ) -> dict[str, list[str]]:
        """Get all linked entry IDs grouped by type.
        
        Args:
            entry_type: Type of entry
            entry_id: UUID of entry
            
        Returns:
            Dict mapping target_type -> list of target_ids
        """
        outgoing = self.get_outgoing(entry_type, entry_id)
        incoming = self.get_incoming(entry_type, entry_id)
        
        result: dict[str, set] = {}
        
        for link in outgoing:
            if link.target_type not in result:
                result[link.target_type] = set()
            result[link.target_type].add(link.target_id)
        
        for link in incoming:
            if link.source_type not in result:
                result[link.source_type] = set()
            result[link.source_type].add(link.source_id)
        
        return {k: list(v) for k, v in result.items()}


# Module-level singleton
_links_db: LinksDB | None = None


def get_links_db() -> LinksDB:
    """Get the links database instance."""
    global _links_db
    if _links_db is None:
        _links_db = LinksDB()
    return _links_db


# Convenience functions
def add_link(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
) -> Link | None:
    """Add a bidirectional link."""
    return get_links_db().add_link(source_type, source_id, target_type, target_id)


def bulk_add_links(
    links: list[tuple[str, str, str, str]],
    source_type_default: str | None = None,
    target_type_default: str | None = None,
) -> int:
    """Add multiple links in a single transaction."""
    return get_links_db().bulk_add_links(
        links,
        source_type_default=source_type_default,
        target_type_default=target_type_default,
    )


def remove_link(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
) -> bool:
    """Remove a link."""
    return get_links_db().remove_link(source_type, source_id, target_type, target_id)


def get_outgoing(
    source_type: str,
    source_id: str,
) -> list[Link]:
    """Get outgoing links from an entry."""
    return get_links_db().get_outgoing(source_type, source_id)


def get_incoming(
    target_type: str,
    target_id: str,
) -> list[Link]:
    """Get incoming links to an entry."""
    return get_links_db().get_incoming(target_type, target_id)


def get_links(
    entry_type: str,
    entry_id: str,
) -> dict[str, list[Link]]:
    """Get all links for an entry."""
    return get_links_db().get_links(entry_type, entry_id)


def link_exists(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
) -> bool:
    """Check if a link exists."""
    return get_links_db().link_exists(source_type, source_id, target_type, target_id)


def remove_all_for_entry(
    entry_type: str,
    entry_id: str,
) -> int:
    """Remove all links for an entry."""
    return get_links_db().remove_all_for_entry(entry_type, entry_id)


def get_linked_entries(
    entry_type: str,
    entry_id: str,
) -> dict[str, list[str]]:
    """Get all linked entry IDs."""
    return get_links_db().get_linked_entries(entry_type, entry_id)