"""Timestamped, checksum-verified database backups outside ``data_dir``.

Backup location::

    ~/.local/share/A/.backups/{module}/{timestamp}.db

This survives ``rm -rf`` of the module's data directory because
``.backups/`` lives directly under the A data root, not under the
individual module directory.

Typical usage::

    from A.core.backup import backup_database, list_backups, restore_latest

    # Auto-backup before a write operation
    backup_database(Path("~/.local/share/A/A-vorto/vorto.db"), module="A-vorto")

    # List available backups
    for b in list_backups("A-vorto"):
        print(b["timestamp"], b["size_bytes"])

    # Restore the newest backup
    restore_latest("A-vorto", Path("~/.local/share/A/A-vorto/vorto.db"))
"""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import Any

from A.core.paths import data_dir

# ── Internal helpers ──────────────────────────────────────────────────────────────

_BACKUP_SUBDIR = ".backups"


def _backup_dir() -> Path:
    """Return the root backup directory (``data_dir() / ".backups"``).

    The directory is **not** created automatically — callers are
    responsible for creating per-module subdirectories as needed.
    """
    return data_dir() / _BACKUP_SUBDIR


def _module_backup_dir(module: str) -> Path:
    """Return the per-module backup subdirectory.

    Args:
        module: Module name (e.g. ``"A-semantika"``, ``"vorto"``).

    Returns:
        ``_backup_dir() / module`` (not created automatically).
    """
    return _backup_dir() / module


def _timestamp() -> str:
    """Return a sortable ISO-like timestamp string for backup filenames.

    Format: ``YYYYMMDDTHHMMSSnnnnnnnnn`` (nanosecond precision; no
    colons, no spaces, safe for filenames).

    Example: ``"20260612T103042123456789"``

    Nanosecond precision guarantees unique filenames even when many
    backups are created in rapid succession (e.g. in tests).
    """
    t = time.time_ns()
    secs = t // 1_000_000_000
    nsec = t % 1_000_000_000
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime(secs)) + f"{nsec:09d}"


def _sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Reads the file in 8 KiB chunks to avoid loading large files into
    memory.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ── Public API ────────────────────────────────────────────────────────────────────


def backup_dir() -> Path:
    """Return the root backup directory.

    Returns:
        ``data_dir() / ".backups"``.  The directory is **not** created
        automatically — call :func:`backup_database` to create it on
        first use.
    """
    return _backup_dir()


def backup_database(
    db_path: Path,
    *,
    module: str = "unknown",
    retention: int = 10,
) -> Path | None:
    """Create a timestamped, checksum-verified backup of *db_path*.

    The backup is stored at::

        {backup_dir}/{module}/{timestamp}.db

    where ``backup_dir`` is :func:`backup_dir()` (typically
    ``~/.local/share/A/.backups/``).

    Workflow:

    1. Compute the SHA-256 hash of *db_path*.
    2. Copy the file to the per-module backup subdirectory with a
       timestamp filename.
    3. Verify the SHA-256 hash of the copy matches the source.
    4. Prune old backups for *module* down to *retention*.

    Args:
        db_path:   Path to the database file to back up.
        module:    Module name for organising backups into subdirectories.
        retention: Maximum number of backups to keep per module.
                   Older backups are pruned after a successful backup.
                   Set to 0 to disable pruning entirely.

    Returns:
        Path to the created backup file, or ``None`` if the source
        file does not exist.

    Raises:
        OSError: If the source file is unreadable, the backup directory
                 cannot be written, or the checksum of the copy does not
                 match the source.
    """
    if not db_path.exists():
        return None

    # 1. Compute source checksum
    src_checksum = _sha256(db_path)

    # 2. Prepare backup path
    mod_dir = _module_backup_dir(module)
    mod_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    backup_path = mod_dir / f"{ts}.db"

    shutil.copy2(str(db_path), str(backup_path))

    # 3. Verify copy
    dst_checksum = _sha256(backup_path)
    if dst_checksum != src_checksum:
        backup_path.unlink(missing_ok=True)
        raise OSError(
            f"Backup checksum mismatch for {db_path.name}: "
            f"source {src_checksum[:12]} != copy {dst_checksum[:12]}"
        )

    # 4. Prune old backups
    if retention > 0:
        prune_backups(module, retention=retention)

    return backup_path


def list_backups(module: str) -> list[dict[str, Any]]:
    """List available backups for *module*, newest first.

    Args:
        module: Module name to list backups for.

    Returns:
        A list of dicts, each with the following keys:

        - **path** (:class:`Path`) — Full path to the backup file.
        - **timestamp** (:class:`str`) — ISO timestamp extracted from
          the filename (e.g. ``"20260612T103042"``).
        - **size_bytes** (:class:`int`) — File size in bytes.
    """
    mod_dir = _module_backup_dir(module)
    if not mod_dir.is_dir():
        return []

    backups: list[dict[str, Any]] = []
    for p in sorted(mod_dir.iterdir(), reverse=True):
        if p.suffix != ".db":
            continue
        backups.append({
            "path": p,
            "timestamp": p.stem,
            "size_bytes": p.stat().st_size,
        })

    return backups


def restore_latest(module: str, target_path: Path) -> Path:
    """Restore the newest backup for *module* to *target_path*.

    The restored file is checksum-verified after the copy.

    Args:
        module:      Module name to restore from.
        target_path: Destination path for the restored database.

    Returns:
        *target_path* on success.

    Raises:
        FileNotFoundError: If no backups exist for *module*.
        OSError: If the restore file cannot be read or written, or
                 the checksum verification fails.
    """
    backups = list_backups(module)
    if not backups:
        raise FileNotFoundError(
            f"No backups found for module '{module}'"
        )

    latest = backups[0]  # newest first (list_backups sorts descending)
    return _restore_file(latest["path"], target_path)


def restore_by_timestamp(
    module: str,
    timestamp_prefix: str,
    target_path: Path,
) -> Path:
    """Restore a specific backup matching *timestamp_prefix*.

    Accepts partial timestamps — the prefix is matched case-insensitively
    as a substring against backup filenames.  For example, ``"2026-06"``
    matches ``"20260612T103042"``.

    Args:
        module:           Module name to restore from.
        timestamp_prefix: ISO timestamp prefix (may be partial).
        target_path:      Destination path for the restored database.

    Returns:
        *target_path* on success.

    Raises:
        FileNotFoundError: If no backups exist for *module*.
        LookupError: If *timestamp_prefix* matches zero or more than one
                     backup.
        OSError: If the restore file cannot be read or written, or the
                 checksum verification fails.
    """
    backups = list_backups(module)
    if not backups:
        raise FileNotFoundError(
            f"No backups found for module '{module}'"
        )

    # Normalise prefix: strip non-alphanumeric chars, lower-case
    normalized = "".join(c for c in timestamp_prefix if c.isalnum()).lower()

    matches = [
        b for b in backups
        if normalized in b["timestamp"].lower()
    ]

    if not matches:
        raise LookupError(
            f"No backup matches timestamp prefix '{timestamp_prefix}' "
            f"for module '{module}'"
        )
    if len(matches) > 1:
        raise LookupError(
            f"Timestamp prefix '{timestamp_prefix}' is ambiguous for "
            f"module '{module}': matches {len(matches)} backups. "
            f"Use a more specific prefix."
        )

    return _restore_file(matches[0]["path"], target_path)


def _restore_file(backup_path: Path, target_path: Path) -> Path:
    """Copy *backup_path* to *target_path* with checksum verification.

    Args:
        backup_path: Source backup file.
        target_path: Destination path.

    Returns:
        *target_path* on success.

    Raises:
        OSError: If the copy or checksum verification fails.
    """
    src_checksum = _sha256(backup_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(backup_path), str(target_path))

    dst_checksum = _sha256(target_path)
    if dst_checksum != src_checksum:
        target_path.unlink(missing_ok=True)
        raise OSError(
            f"Restore checksum mismatch for {target_path.name}: "
            f"source {src_checksum[:12]} != copy {dst_checksum[:12]}"
        )

    return target_path


def prune_backups(module: str, *, retention: int = 10) -> int:
    """Prune old backups for *module*, keeping the newest *retention*.

    Backups are identified by ``.db`` files in the module's backup
    subdirectory, sorted by filename (timestamp) descending (newest
    first).  The newest *retention* files are preserved; the rest are
    deleted.

    This function is idempotent — calling it multiple times with the
    same *retention* has no additional effect after the first call.

    Args:
        module:    Module name to prune backups for.
        retention: Number of newest backups to keep.  Must be >= 1.

    Returns:
        Number of backup files deleted.

    Raises:
        ValueError: If *retention* is less than 1.
    """
    if retention < 1:
        raise ValueError(
            f"retention must be >= 1, got {retention}"
        )

    mod_dir = _module_backup_dir(module)
    if not mod_dir.is_dir():
        return 0

    all_backups = sorted(
        [p for p in mod_dir.iterdir() if p.suffix == ".db"],
        reverse=True,
    )

    if len(all_backups) <= retention:
        return 0

    to_delete = all_backups[retention:]
    deleted = 0
    for p in to_delete:
        try:
            p.unlink()
            deleted += 1
        except OSError:
            pass  # best-effort per-file deletion

    return deleted


__all__ = [
    "backup_dir",
    "backup_database",
    "list_backups",
    "restore_latest",
    "restore_by_timestamp",
    "prune_backups",
]
