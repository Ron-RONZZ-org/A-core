"""Bidirectional links module for A.

Provides adjacency list storage for cross-module links.
When entry A links to entry B, the link is stored and queryable
in both directions (outgoing from A, incoming to B).
"""

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
    
    def bulk_add_links(
        self,
        pairs: list[tuple[str, str]],
        source_type_default: str = "vorto",
        target_type: str | None = None,
    ) -> int:
        """Add multiple links in a single transaction.

        Args:
            pairs: List of ``(source_id, target_id)`` tuples.
            source_type_default: Entry type for source & target
                                 (default ``"vorto"``).
            target_type: Entry type for the target.
                         Defaults to ``source_type_default``.

        Returns:
            Number of links actually inserted (skips self-links
            and duplicate violations).
        """
        target_type = target_type or source_type_default
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        with self._connection() as conn:
            for source_id, target_id in pairs:
                if source_id == target_id:
                    continue  # Don't link to self
                try:
                    conn.execute(
                        """
                        INSERT INTO links
                            (source_type, source_id, target_type, target_id, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (source_type, source_id, target_type, target_id, now),
                    )
                    count += 1
                except Exception:
                    continue  # UNIQUE constraint or other
            conn.commit()

        return count

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


def bulk_add_links(
    pairs: list[tuple[str, str]],
    source_type_default: str = "vorto",
    target_type: str | None = None,
) -> int:
    """Add multiple links in batch.

    Args:
        pairs: List of ``(source_id, target_id)`` tuples.
        source_type_default: Entry type for source & target
                             (default ``"vorto"``).
        target_type: Entry type for the target.
                     Defaults to ``source_type_default``.

    Returns:
        Number of links actually inserted.
    """
    return get_links_db().bulk_add_links(pairs, source_type_default, target_type)