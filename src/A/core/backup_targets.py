"""Backup target discovery for A-sekurkopio.

Uses ``A.backup`` entry points plus a convention-based fallback (scan of
``data_dir()``) to discover all A-module database files that should be
backed up.

Entry point pattern (in an A-module's ``pyproject.toml``)::

    [project.entry-points."A.backup"]
    vorto = "A_vorto.data.storage:get_backup_targets"

The referenced callable must return ``list[BackupTarget]``.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from A.core.paths import data_dir


@dataclass(frozen=True)
class BackupTarget:
    """A single file that should be backed up (or restored).

    Attributes:
        path:     Absolute filesystem path to the file to back up.
        category: ``"data"`` for user data (restore to ``data_dir``),
                  ``"config"`` for config-like data (restore to
                  ``config_dir``).
        module:   Canonical module name (e.g. ``"vorto"``, ``"sistemo"``).
        label:    Short human-readable description
                  (e.g. ``"Vorto database"``).
    """

    path: Path
    category: str = "data"
    module: str = ""
    label: str = ""


# ── Module-level caches ────────────────────────────────────────────────────────

_backup_targets: list[BackupTarget] | None = None
_discovered_factories: dict[str, Callable[[], list[BackupTarget]]] = {}


# ── Convention-based fallback ──────────────────────────────────────────────────

def _scan_data_dir(claimed_modules: set[str]) -> list[BackupTarget]:
    """Scan ``data_dir()`` for ``*.db`` files not claimed by entry points.

    Heuristic:
        ``vorto.db``       → module ``vorto``, category ``data``.
        ``medio/medio.db`` → module ``medio``, category ``data``.
    """
    found: list[BackupTarget] = []
    d = data_dir()
    if not d.is_dir():
        return found

    for p in sorted(d.rglob("*.db")):
        rel = p.relative_to(d)
        parts = rel.parts
        if len(parts) == 1:
            name = p.stem  # flat: vorto.db → vorto
        else:
            name = parts[0]  # subdir: medio/medio.db → medio

        if name in claimed_modules:
            continue  # already covered by entry point
        found.append(
            BackupTarget(
                path=p,
                category="data",
                module=name,
                label=f"{name} database (auto-discovered)",
            )
        )
    return found


# ── Entry-point discovery ──────────────────────────────────────────────────────

def _discover_entry_points() -> dict[str, Callable[[], list[BackupTarget]]]:
    """Discover and cache ``A.backup`` entry points."""
    if _discovered_factories:
        return _discovered_factories

    try:
        eps = importlib.metadata.entry_points(group="A.backup")
    except TypeError:
        # Python < 3.10
        eps = importlib.metadata.entry_points().get("A.backup", [])

    factories: dict[str, Callable[[], list[BackupTarget]]] = {}
    for ep in eps:
        try:
            fn = ep.load()
            if callable(fn):
                factories[ep.name] = fn
        except Exception:
            pass  # one module failure never blocks others

    _discovered_factories.update(factories)
    return factories


# ── Public API ─────────────────────────────────────────────────────────────────

def get_backup_targets(
    *, include_data_dir_scan: bool = True
) -> list[BackupTarget]:
    """Return all discoverable backup targets across installed A-modules.

    Loads targets from ``A.backup`` entry points (if the module declares
    one), then optionally supplements with a scan of ``data_dir()`` for
    any ``*.db`` files that were not already claimed by an entry point.

    Args:
        include_data_dir_scan: Whether to scan ``data_dir()`` for
            unregistered modules.  Default ``True``.

    Returns:
        A deduplicated list of :class:`BackupTarget`.  Entry-point targets
        always take precedence over scan-based targets.
    """
    global _backup_targets
    if _backup_targets is not None:
        return _backup_targets

    factories = _discover_entry_points()

    # Collect entry-point targets
    ep_targets: list[BackupTarget] = []
    claimed_modules: set[str] = set()
    for name, factory in factories.items():
        try:
            targets = factory()
            for t in targets:
                claimed_modules.add(t.module or name)
            ep_targets.extend(targets)
        except Exception:
            pass  # per-module isolation

    # Scan fallback
    scanned: list[BackupTarget] = []
    if include_data_dir_scan:
        scanned = _scan_data_dir(claimed_modules)

    _backup_targets = ep_targets + scanned
    return _backup_targets


def clear_cache() -> None:
    """Clear cached targets (for testing)."""
    global _backup_targets, _discovered_factories
    _backup_targets = None
    _discovered_factories.clear()


__all__ = [
    "BackupTarget",
    "get_backup_targets",
    "clear_cache",
]
