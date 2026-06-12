"""XDG Trash integration for A-core.

Provides file-level deletion safety by moving files and directories to the
standard `XDG Trash <https://specifications.freedesktop.org/trash-spec/trashspec-latest.html>`_
instead of permanently deleting them.

Trash location::

    $XDG_DATA_HOME/Trash/files/          — actual files
    $XDG_DATA_HOME/Trash/info/           — .trashinfo metadata

where ``$XDG_DATA_HOME`` defaults to ``~/.local/share``.

Example::

    from A.core.trash import move_to_trash, list_trash, empty_trash

    # Move file to trash
    info_path = move_to_trash(Path("/path/to/file.db"))
    print(f"Trashed at {info_path}")

    # List all trashed items
    for item in list_trash():
        print(item["original_path"], item["deleted_at"])

    # Empty trash
    deleted = empty_trash()
    print(f"Deleted {deleted} items permanently")
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from A.core.paths import config_dir, data_dir, state_dir

# ── Constants ───────────────────────────────────────────────────────────────────

_TRASH_SUBDIR = "Trash"
_FILES_SUBDIR = "files"
_INFO_SUBDIR = "info"
_INFO_EXT = ".trashinfo"

# ── Internal helpers ────────────────────────────────────────────────────────────


def _trash_dir() -> Path:
    """Return the XDG Trash root directory.

    Uses ``$XDG_DATA_HOME/Trash`` (default ``~/.local/share/Trash``).
    """
    xdg_data = os.environ.get("XDG_DATA_HOME", "")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    return base / _TRASH_SUBDIR


def _files_dir() -> Path:
    """Return the Trash files directory, creating it if needed."""
    d = _trash_dir() / _FILES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _info_dir() -> Path:
    """Return the Trash info directory, creating it if needed."""
    d = _trash_dir() / _INFO_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _unique_trash_name(path: Path) -> str:
    """Generate a unique filename for the trash, handling collisions.

    If a file with the same base name already exists in the trash,
    appends a counter: ``"file.txt"``, ``"file.txt (1)"``, etc.
    """
    files_dir = _files_dir()
    base = path.name
    candidate = base
    counter = 0
    while (files_dir / candidate).exists():
        counter += 1
        stem = path.stem
        suffix = path.suffix
        candidate = f"{stem} ({counter}){suffix}"
    return candidate


def _make_trashinfo(path: Path) -> str:
    """Create a ``.trashinfo`` file content for *path*.

    Args:
        path: Original (absolute) path of the file being trashed.

    Returns:
        A string conforming to the `XDG Trash Info`_ format.

    .. _XDG Trash Info:
       https://specifications.freedesktop.org/trash-spec/trashspec-latest.html#trashinfo
    """
    # URL-encode the path as required by the spec
    encoded = quote(str(path.resolve()), safe="/")
    deletion_date = time.strftime("%Y-%m-%dT%H:%M:%S")
    return (
        "[Trash Info]\n"
        f"Path={encoded}\n"
        f"DeletionDate={deletion_date}\n"
    )


def _is_a_related(original_path: str) -> bool:
    """Check if *original_path* is under an A standard directory."""
    try:
        p = Path(original_path).resolve()
    except Exception:
        return False
    a_dirs = [data_dir(), config_dir(), state_dir()]
    for ad in a_dirs:
        try:
            p.relative_to(ad)
            return True
        except ValueError:
            continue
    return False


# ── Public API ──────────────────────────────────────────────────────────────────


def move_to_trash(path: Path) -> Path:
    """Move *path* (file or directory) to the XDG Trash.

    Creates a corresponding ``.trashinfo`` metadata file in the Trash
    info directory.  Handles name collisions by appending a counter.

    Args:
        path: File or directory to trash (must exist).

    Returns:
        Path to the created ``.trashinfo`` metadata file.

    Raises:
        FileNotFoundError: If *path* does not exist.
        OSError: If the file cannot be moved or the info file cannot
            be written.
    """
    if not path.exists():
        raise FileNotFoundError(f"Cannot trash non-existent path: {path}")

    # Resolve to an absolute path for reliable info storage
    path = path.resolve()

    # Prepare trash locations
    trash_name = _unique_trash_name(path)
    target = _files_dir() / trash_name
    info_target = _info_dir() / f"{trash_name}{_INFO_EXT}"

    # Move the file/dir
    shutil.move(str(path), str(target))

    # Write .trashinfo metadata
    info_content = _make_trashinfo(path)
    info_target.write_text(info_content, encoding="utf-8")

    return info_target


def list_trash(*, only_a_related: bool = True) -> list[dict[str, Any]]:
    """List items currently in the XDG Trash.

    Args:
        only_a_related: If ``True`` (default), only return items whose
            original path is under an A standard directory (``data_dir``,
            ``config_dir``, or ``state_dir``).

    Returns:
        A list of dicts, each with:

        - ``original_path`` (:class:`Path`) — The original absolute path
          of the trashed item.
        - ``trash_path`` (:class:`Path`) — Current path in the Trash
          ``files/`` directory.
        - ``info_path`` (:class:`Path`) — Path to the ``.trashinfo``
          metadata file.
        - ``deleted_at`` (:class:`str`) — ISO timestamp of deletion.
    """
    info_dir = _info_dir()
    if not info_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []

    for info_file in sorted(info_dir.iterdir()):
        if info_file.suffix != _INFO_EXT:
            continue

        try:
            content = info_file.read_text(encoding="utf-8")
            original_path, deleted_at = _parse_trashinfo(content)
        except Exception:
            continue  # skip corrupt info files

        if only_a_related and not _is_a_related(original_path):
            continue

        # Derive trash file path
        trash_name = info_file.stem  # without .trashinfo
        trash_file = _files_dir() / trash_name

        items.append({
            "original_path": Path(original_path),
            "trash_path": trash_file if trash_file.exists() else None,
            "info_path": info_file,
            "deleted_at": deleted_at,
        })

    return items


def _parse_trashinfo(content: str) -> tuple[str, str]:
    """Parse a ``.trashinfo`` file content.

    Returns:
        ``(original_path, deletion_date)`` as strings.

    Raises:
        ValueError: If the file content is malformed.
    """
    from urllib.parse import unquote

    path = ""
    date = ""

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Path="):
            encoded = line[5:]
            path = unquote(encoded)
        elif line.startswith("DeletionDate="):
            date = line[13:]

    if not path:
        raise ValueError("Missing Path in trashinfo")

    return path, date


def empty_trash() -> int:
    """Permanently delete all items from the XDG Trash.

    Removes both ``files/`` and ``info/`` contents (but not the
    directories themselves).

    Returns:
        Number of file+info pairs deleted.
    """
    files_dir = _files_dir()
    info_dir = _info_dir()

    # Gather all info files
    info_files = list(info_dir.glob(f"*{_INFO_EXT}")) if info_dir.is_dir() else []

    count = 0
    for info_file in info_files:
        trash_name = info_file.stem
        trash_file = files_dir / trash_name

        # Delete the actual file (if it exists)
        try:
            if trash_file.exists():
                if trash_file.is_dir():
                    shutil.rmtree(trash_file)
                else:
                    trash_file.unlink()
        except OSError:
            pass

        # Delete the info file
        try:
            info_file.unlink()
            count += 1
        except OSError:
            pass

    # Also clean up orphaned files without info
    if files_dir.is_dir():
        for f in files_dir.iterdir():
            info_candidate = info_dir / f"{f.name}{_INFO_EXT}"
            if not info_candidate.exists():
                try:
                    if f.is_dir():
                        shutil.rmtree(f)
                    else:
                        f.unlink()
                except OSError:
                    pass

    return count


__all__ = [
    "move_to_trash",
    "list_trash",
    "empty_trash",
]
