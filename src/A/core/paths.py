"""XDG path resolution with optional ``A_DIR`` environment variable override.

When the ``A_DIR`` environment variable is set, all four path functions
return paths under ``$A_DIR / {data,config,cache,state}`` instead of
their default XDG locations.

Example::

    export A_DIR=/tmp/my-project
    python -c "from A.core.paths import data_dir; print(data_dir())"
    # => /tmp/my-project/data

Sentinel protection
-------------------

The functions :func:`protect_directory`, :func:`is_protected`,
:func:`safe_rmtree`, and :func:`safe_unlink` implement a lightweight
deletion guard based on a ``.a-protected`` marker file.

When a directory is *protected*, Python-level deletion via
:func:`safe_rmtree` or :func:`safe_unlink` raises
:class:`A.core.exceptions.ProtectedPathError` unless ``force=True``
is passed.

.. note::
   This guard **only** catches Python-level calls.  It does **not**
   prevent ``rm -rf`` in a shell.  The :class:`BackupManager
   <A.core.backup>` module provides filesystem-level recovery.
"""

import os
import shutil
from pathlib import Path

_A_DIR_ENV = "A_DIR"
_SENTINEL_NAME = ".a-protected"


def _base() -> Path | None:
    """Return the base directory from ``A_DIR`` env var, or ``None``.

    Reads the ``A_DIR`` environment variable on every call (lazy
    evaluation).  Returns ``None`` when the variable is unset, empty,
    or whitespace-only, preserving the default XDG resolution.
    """
    val = os.environ.get(_A_DIR_ENV, "").strip()
    if not val:
        return None
    return Path(val).resolve()


def data_dir() -> Path:
    """Return the A data directory.

    Default::

        ~/.local/share/A

    When the ``A_DIR`` environment variable is set, returns
    ``A_DIR / "data"`` instead.

    The directory is **not** created automatically — call
    :func:`ensure_dirs` or ``.mkdir(parents=True)`` explicitly.
    """
    base = _base()
    if base is not None:
        return base / "data"
    return Path.home() / ".local" / "share" / "A"


def config_dir() -> Path:
    """Return the A config directory.

    Default::

        ~/.config/A

    When the ``A_DIR`` environment variable is set, returns
    ``A_DIR / "config"`` instead.
    """
    base = _base()
    if base is not None:
        return base / "config"
    return Path.home() / ".config" / "A"


def cache_dir() -> Path:
    """Return the A cache directory.

    Default::

        ~/.cache/A

    When the ``A_DIR`` environment variable is set, returns
    ``A_DIR / "cache"`` instead.
    """
    base = _base()
    if base is not None:
        return base / "cache"
    return Path.home() / ".cache" / "A"


def state_dir() -> Path:
    """Return the A state directory.

    Default::

        ~/.local/state/A

    When the ``A_DIR`` environment variable is set, returns
    ``A_DIR / "state"`` instead.
    """
    base = _base()
    if base is not None:
        return base / "state"
    return Path.home() / ".local" / "state" / "A"


def ensure_dirs() -> None:
    """Ensure all A directories exist and are protected.

    Creates the standard A directories (data, config, cache, state)
    if they don't exist, then marks each with a ``.a-protected``
    sentinel so that :func:`safe_rmtree` and :func:`safe_unlink`
    will refuse to delete them.
    """
    for d in [data_dir(), config_dir(), cache_dir(), state_dir()]:
        d.mkdir(parents=True, exist_ok=True)
        protect_directory(d)


# ── Sentinel protection helpers ─────────────────────────────────────────────────


def protect_directory(path: Path) -> Path:
    """Create a ``.a-protected`` sentinel marker in *path*.

    The marker is an empty file.  Its presence signals that automated
    tools (AI agents, scripts) should **not** delete this directory or
    its contents.

    The directory is created if it does not exist.  Idempotent
    (safe to call multiple times).

    Args:
        path: Directory to protect.

    Returns:
        *path* for chaining.
    """
    path.mkdir(parents=True, exist_ok=True)
    sentinel = path / _SENTINEL_NAME
    sentinel.touch(exist_ok=True)
    return path


def is_protected(path: Path) -> bool:
    """Check if *path* or any ancestor is protected.

    Walks up the directory tree from *path* toward the root.
    Returns ``True`` if any directory in the ancestry contains
    a ``.a-protected`` marker file.

    This means protecting ``~/.local/share/A/`` protects **all**
    subdirectories (modules) automatically.

    Args:
        path: Directory to check.

    Returns:
        ``True`` if the path (or any parent) is protected.
    """
    for parent in [path, *path.parents]:
        if (parent / _SENTINEL_NAME).exists():
            return True
    return False


def safe_rmtree(path: Path, *, force: bool = False) -> None:
    """Remove a directory tree, refusing if protected.

    Args:
        path:  Directory to remove.
        force: If ``True``, bypass the protection check.

    Raises:
        ProtectedPathError: If *path* (or any parent) is protected
            and ``force`` is ``False``.
        FileNotFoundError: If *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not force and is_protected(path):
        from A.core.exceptions import ProtectedPathError
        raise ProtectedPathError(path, "delete")
    shutil.rmtree(path)


def safe_unlink(path: Path, *, force: bool = False) -> None:
    """Delete a file, refusing if the parent directory is protected.

    Args:
        path:  File to delete.
        force: If ``True``, bypass the protection check.

    Raises:
        ProtectedPathError: If the parent directory is protected
            and ``force`` is ``False``.
        FileNotFoundError: If *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not force and is_protected(path.parent):
        from A.core.exceptions import ProtectedPathError
        raise ProtectedPathError(path, "unlink")
    path.unlink()


def protect_all() -> None:
    """Protect all standard A directories.

    Creates and marks each standard directory (data, config, cache,
    state) with a ``.a-protected`` sentinel.  Idempotent.
    """
    for d in [data_dir(), config_dir(), cache_dir(), state_dir()]:
        protect_directory(d)



