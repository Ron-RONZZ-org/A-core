"""XDG path resolution with optional ``A_DIR`` environment variable override.

When the ``A_DIR`` environment variable is set, all four path functions
return paths under ``$A_DIR / {data,config,cache,state}`` instead of
their default XDG locations.

Example::

    export A_DIR=/tmp/my-project
    python -c "from A.core.paths import data_dir; print(data_dir())"
    # => /tmp/my-project/data
"""

import os
from pathlib import Path

_A_DIR_ENV = "A_DIR"


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
    """Ensure all A directories exist (respects ``A_DIR`` override)."""
    for d in [data_dir(), config_dir(), cache_dir(), state_dir()]:
        d.mkdir(parents=True, exist_ok=True)
