"""Tests for A.core.paths — A_DIR env var override & default XDG resolution."""

import os
from pathlib import Path

import pytest

from A.core.paths import (
    _A_DIR_ENV,
    _base,
    cache_dir,
    config_dir,
    data_dir,
    ensure_dirs,
    state_dir,
)

# ── _base helper ────────────────────────────────────────────────────────────


def test_base_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """_base() returns None when A_DIR is not set."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)
    assert _base() is None


def test_base_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """_base() returns None when A_DIR is empty string."""
    monkeypatch.setenv(_A_DIR_ENV, "")
    assert _base() is None


def test_base_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """_base() returns None when A_DIR is whitespace-only."""
    monkeypatch.setenv(_A_DIR_ENV, "   ")
    assert _base() is None


def test_base_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """_base() returns resolved Path for a valid A_DIR."""
    monkeypatch.setenv(_A_DIR_ENV, "/tmp/a-core-test")
    result = _base()
    assert isinstance(result, Path)
    assert result == Path("/tmp/a-core-test").resolve()


def test_base_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    """_base() resolves relative paths to absolute."""
    monkeypatch.setenv(_A_DIR_ENV, ".")
    result = _base()
    assert result.is_absolute()
    assert result == Path.cwd().resolve()


# ── Default (XDG) paths ────────────────────────────────────────────────────


def test_default_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """data_dir() returns XDG default when A_DIR is unset."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)
    assert data_dir() == Path.home() / ".local" / "share" / "A"


def test_default_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """config_dir() returns XDG default when A_DIR is unset."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)
    assert config_dir() == Path.home() / ".config" / "A"


def test_default_cache_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """cache_dir() returns XDG default when A_DIR is unset."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)
    assert cache_dir() == Path.home() / ".cache" / "A"


def test_default_state_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """state_dir() returns XDG default when A_DIR is unset."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)
    assert state_dir() == Path.home() / ".local" / "state" / "A"


# ── A_DIR override ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path_func, subdir",
    [
        (data_dir, "data"),
        (config_dir, "config"),
        (cache_dir, "cache"),
        (state_dir, "state"),
    ],
)
def test_override(
    monkeypatch: pytest.MonkeyPatch,
    path_func: callable,
    subdir: str,
) -> None:
    """Each path function returns ``A_DIR / <subdir>`` when A_DIR is set."""
    monkeypatch.setenv(_A_DIR_ENV, "/tmp/a-override")
    expected = Path("/tmp/a-override").resolve() / subdir
    assert path_func() == expected


# ── Empty string treated as unset ──────────────────────────────────────────


def test_empty_string_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty A_DIR falls back to XDG default."""
    monkeypatch.setenv(_A_DIR_ENV, "")
    assert data_dir() == Path.home() / ".local" / "share" / "A"
    assert config_dir() == Path.home() / ".config" / "A"
    assert cache_dir() == Path.home() / ".cache" / "A"
    assert state_dir() == Path.home() / ".local" / "state" / "A"


# ── Lazy evaluation ────────────────────────────────────────────────────────


def test_lazy_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing A_DIR between calls changes the returned path."""
    monkeypatch.setenv(_A_DIR_ENV, "/tmp/first")
    assert data_dir() == Path("/tmp/first/data").resolve()

    monkeypatch.setenv(_A_DIR_ENV, "/tmp/second")
    assert data_dir() == Path("/tmp/second/data").resolve()


# ── ensure_dirs ─────────────────────────────────────────────────────────────


def test_ensure_dirs_respects_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ensure_dirs() creates directories under the A_DIR override."""
    monkeypatch.setenv(_A_DIR_ENV, str(tmp_path))
    ensure_dirs()
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "config").is_dir()
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "state").is_dir()


def test_ensure_dirs_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ensure_dirs() creates XDG directories when A_DIR is unset."""
    monkeypatch.delenv(_A_DIR_ENV, raising=False)

    # Monkey-patch home to avoid polluting real ~
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    ensure_dirs()
    assert (fake_home / ".local" / "share" / "A").is_dir()
    assert (fake_home / ".config" / "A").is_dir()
    assert (fake_home / ".cache" / "A").is_dir()
    assert (fake_home / ".local" / "state" / "A").is_dir()


# ── patch_paths integration ─────────────────────────────────────────────────


def test_patch_paths_isolates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """patch_paths() redirects all paths under tmp_path."""
    from A.core.testing import patch_paths

    patch_paths(monkeypatch, tmp_path)
    assert data_dir() == tmp_path / "data"
    assert config_dir() == tmp_path / "config"
    assert cache_dir() == tmp_path / "cache"
    assert state_dir() == tmp_path / "state"
