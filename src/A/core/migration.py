"""Migration framework from autish to A-* modules.

Handles migration of data from legacy autish SQLite databases to A-* modules.

Usage:
    from A.core.migration import migrate_all, get_status, MigrationResult
    
    # Check migration status
    status = get_status()
    
    # Run all pending migrations
    results = migrate_all()
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from A.core.paths import data_dir
from A.core.paths import ensure_dirs as _ensure_dirs
from A.data.base import SQLiteDB


# Legacy autish data path
_LEGACY_AUTISH_DIR = Path.home() / ".local" / "share" / "autish"


# ══════════════════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class MigrationResult:
    """Result from a single migration."""

    module: str
    source_db: str
    target_table: str
    source_rows: int
    migrated_rows: int
    errors: list[str] = field(default_factory=list)
    skipped: bool = False
    skipped_reason: str = ""
    detail: str = ""  # Extra details like "keyring=2, contacts=148"

    @property
    def success(self) -> bool:
        """Check if migration succeeded."""
        return not self.skipped and not self.errors and self.migrated_rows > 0


@dataclass
class MigrationStatus:
    """Overall migration status for a module."""

    module: str
    available: bool  # Legacy DB exists
    migrated: bool  # Migration ran
    last_migration: str | None  # ISO timestamp
    source_rows: int
    migrated_rows: int


# ══════════════════════════════════════════════════════════════════════════════
# Migration registry
# ══════════════════════════════════════════════════════════════════════════════

# Registry: module_name -> migration function
_MIGRATIONS: dict[str, Callable[[], MigrationResult]] = {}


def get_status() -> dict[str, MigrationStatus]:
    """Get migration status for all modules.

    Returns:
        Dict mapping module name to MigrationStatus
    """
    status: dict[str, MigrationStatus] = {}

    for module, migrator in _MIGRATIONS.items():
        source_path = _LEGACY_AUTISH_DIR / _get_legacy_db_name(module)
        
        # Check if legacy DB exists
        available = source_path.exists()
        
        # Check migration state
        migrated = False
        last_migration = None
        source_rows = 0
        migrated_rows = 0
        
        if available:
            source_rows = _count_legacy_rows(module)

        # Check if already migrated (read from A migration state)
        state = _load_migration_state()
        if module in state:
            migrated = True
            last_migration = state[module].get("last_migration")
            migrated_rows = state[module].get("migrated_rows", 0)

        status[module] = MigrationStatus(
            module=module,
            available=available,
            migrated=migrated,
            last_migration=last_migration,
            source_rows=source_rows,
            migrated_rows=migrated_rows,
        )

    return status


def migrate_all(dry_run: bool = False) -> dict[str, MigrationResult]:
    """Run all pending migrations.

    Args:
        dry_run: If True, simulate migration without writing

    Returns:
        Dict mapping module name to MigrationResult
    """
    results: dict[str, MigrationResult] = {}

    for module, migrator in _MIGRATIONS.items():
        # Skip if already migrated
        state = _load_migration_state()
        if module in state and state[module].get("migrated"):
            continue

        # Run migration
        result = migrator()
        results[module] = result

        # Save state if not dry run
        if not dry_run and result.success:
            _save_migration_state(module, result)

    return results


def register_migration(
    module: str,
    legacy_db: str,
    target_table: str,
    migrator: Callable[[], MigrationResult],
) -> None:
    """Register a migration function.

    Args:
        module: A-* module name (e.g., "A-lien")
        legacy_db: Legacy database filename (e.g., "retposto.db")
        target_table: Target table in A-* database
        migrator: Callable that performs migration and returns MigrationResult
    """
    _MIGRATIONS[module] = migrator
    _LEGACY_DB_MAP[module] = legacy_db
    _TARGET_TABLE_MAP[module] = target_table


# Legacy DB name mapping
_LEGACY_DB_MAP: dict[str, str] = {}
_TARGET_TABLE_MAP: dict[str, str] = {}


def _get_legacy_db_name(module: str) -> str:
    """Get legacy database name for a module."""
    return _LEGACY_DB_MAP.get(module, f"{module}.db")


# ══════════════════════════════════════════════════════════════════════════════
# State tracking
# ══════════════════════════════════════════════════════════════════════════════

def _get_state_path() -> Path:
    """Get migration state file path."""
    _ensure_dirs()
    return data_dir() / "migration_state.json"


def _load_migration_state() -> dict:
    """Load migration state from disk."""
    path = _get_state_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_migration_state(module: str, result: MigrationResult) -> None:
    """Save migration state to disk."""
    state = _load_migration_state()
    state[module] = {
        "migrated": True,
        "last_migration": datetime.now(timezone.utc).isoformat(),
        "source_rows": result.source_rows,
        "migrated_rows": result.migrated_rows,
        "detail": result.detail,
        "errors": result.errors,
    }
    with open(_get_state_path(), "w") as f:
        json.dump(state, f, indent=2)


def _count_legacy_rows(module: str) -> int:
    """Count rows in legacy database."""
    legacy_db = _get_legacy_db_name(module)
    path = _LEGACY_AUTISH_DIR / legacy_db
    if not path.exists():
        return 0

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor if row[0] != "sqlite_sequence"]

        # Get count from main table
        table_name = _get_legacy_table_name(module)
        if table_name in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0] or 0
        return 0
    except Exception:
        return 0


def _get_legacy_table_name(module: str) -> str:
    """Get legacy table name for a module."""
    table_map = {
        "A-lien": "kontakto",  # Contacts in retposto.db
        "A-vorto": "vorto",
        "A-encik": "encik",
        "A-organizi": "event",  # Calendar events in kalendaro.db
    }
    return table_map.get(module, module.lower())


# ══════════════════════════════════════════════════════════════════════════════
# Exports
# ══════════════════════════════════════════════════════════════════════════════


__all__ = [
    "MigrationResult",
    "MigrationStatus",
    "get_status",
    "migrate_all",
    "register_migration",
]