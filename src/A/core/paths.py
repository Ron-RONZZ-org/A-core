"""XDG path resolution."""

from pathlib import Path
from functools import lru_cache


@lru_cache
def data_dir() -> Path:
    """Return data directory (~/.local/share/A)."""
    return Path.home() / ".local" / "share" / "A"


@lru_cache
def config_dir() -> Path:
    """Return config directory (~/.config/A)."""
    return Path.home() / ".config" / "A"


@lru_cache
def cache_dir() -> Path:
    """Return cache directory (~/.cache/A)."""
    return Path.home() / ".cache" / "A"


@lru_cache
def state_dir() -> Path:
    """Return state directory (~/.local/state/A)."""
    return Path.home() / ".local" / "state" / "A"


def ensure_dirs() -> None:
    """Ensure all A directories exist."""
    for d in [data_dir(), config_dir(), cache_dir(), state_dir()]:
        d.mkdir(parents=True, exist_ok=True)