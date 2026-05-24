"""Tests for A.core.backup_targets."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from A.core.backup_targets import (
    BackupTarget,
    clear_cache,
    get_backup_targets,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Reset module-level cache before each test."""
    clear_cache()


def _make_fake_db(tmp_path: Path, *parts: str) -> Path:
    """Create a dummy .db file under data_dir (which is tmp_path/data/), return path."""
    from A.core.paths import data_dir

    p = data_dir().joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    return p


def _data(tmp_path: Path) -> Path:
    """Return the effective data_dir path."""
    from A.core.paths import data_dir

    return data_dir()


# ── BackupTarget dataclass ─────────────────────────────────────────────────────


class TestBackupTarget:
    def test_minimal(self) -> None:
        t = BackupTarget(path=Path("/a/b.db"))
        assert t.path == Path("/a/b.db")
        assert t.category == "data"
        assert t.module == ""
        assert t.label == ""

    def test_full(self) -> None:
        t = BackupTarget(
            path=Path("/x/y.db"),
            category="config",
            module="sistemo",
            label="Sistemo database",
        )
        assert t.path == Path("/x/y.db")
        assert t.category == "config"
        assert t.module == "sistemo"

    def test_frozen(self) -> None:
        t = BackupTarget(path=Path("/a.db"))
        with pytest.raises(AttributeError):
            t.path = Path("/b.db")  # type: ignore[misc]

    def test_hashable(self) -> None:
        t1 = BackupTarget(path=Path("/a.db"))
        t2 = BackupTarget(path=Path("/a.db"))
        assert hash(t1) == hash(t2)


# ── get_backup_targets: basic cases ────────────────────────────────────────────


class TestGetBackupTargets:
    def test_empty_no_data_dir(self, tmp_path: Path) -> None:
        """No data_dir -> empty list."""
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        assert targets == []

    def test_scan_finds_db_files(self, tmp_path: Path) -> None:
        """Scan discovers .db files in data_dir."""
        d = _data(tmp_path)
        _make_fake_db(tmp_path, "vorto.db")
        _make_fake_db(tmp_path, "encik.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        paths = {t.path for t in targets}
        assert d / "vorto.db" in paths
        assert d / "encik.db" in paths

    def test_scan_subdirectory(self, tmp_path: Path) -> None:
        """Scan finds .db files in subdirectories."""
        d = _data(tmp_path)
        _make_fake_db(tmp_path, "medio", "medio.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        assert any(t.path == d / "medio" / "medio.db" for t in targets)

    def test_scan_only_finds_db(self, tmp_path: Path) -> None:
        """Scan ignores non-.db files."""
        d = _data(tmp_path)
        _make_fake_db(tmp_path, "notes.txt")
        _make_fake_db(tmp_path, "vorto.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        assert any(t.path == d / "vorto.db" for t in targets)
        assert not any(t.path == d / "notes.txt" for t in targets)

    def test_scan_skip_if_disabled(self, tmp_path: Path) -> None:
        """include_data_dir_scan=False skips the scan."""
        _make_fake_db(tmp_path, "vorto.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert targets == []

    def test_cache_same_result(self, tmp_path: Path) -> None:
        """Calling get_backup_targets twice returns cached result."""
        _make_fake_db(tmp_path, "vorto.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            first = get_backup_targets()
            second = get_backup_targets()
        assert first is second  # same list object (cached)

    def test_clear_cache(self, tmp_path: Path) -> None:
        """clear_cache forces re-discovery on next call."""
        _make_fake_db(tmp_path, "vorto.db")
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            first = get_backup_targets()
        clear_cache()
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            second = get_backup_targets()
        assert first is not second  # different list object


# ── Entry-point discovery ──────────────────────────────────────────────────────


class _FakeEntryPoint:
    """Minimal EntryPoint-like object for testing."""

    def __init__(self, name: str, factory: Any) -> None:
        self.name = name
        self._factory = factory

    def load(self) -> Any:
        return self._factory


class TestEntryPoints:
    def test_entry_point_targets_included(self, tmp_path: Path) -> None:
        """Entry point targets appear in results."""

        def fake_factory() -> list[BackupTarget]:
            return [
                BackupTarget(
                    path=Path("/custom/mydb.db"),
                    category="config",
                    module="myplugin",
                    label="My database",
                ),
            ]

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[_FakeEntryPoint("myplugin", fake_factory)],
        ):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert len(targets) == 1
        assert targets[0].path == Path("/custom/mydb.db")
        assert targets[0].category == "config"
        assert targets[0].module == "myplugin"

    def test_entry_point_error_isolation(self, tmp_path: Path) -> None:
        """A failing entry point factory does not block others."""

        def broken() -> list[BackupTarget]:
            raise RuntimeError("boom")

        def working() -> list[BackupTarget]:
            return [BackupTarget(path=Path("/good.db"))]

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[
                _FakeEntryPoint("broken", broken),
                _FakeEntryPoint("working", working),
            ],
        ):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert len(targets) == 1
        assert targets[0].path == Path("/good.db")

    def test_entry_point_wins_over_scan(self, tmp_path: Path) -> None:
        """When entry point matches a scanned module, entry point takes priority."""

        def vorto_factory() -> list[BackupTarget]:
            return [
                BackupTarget(
                    path=Path("/explicit/vorto.db"),
                    category="data",
                    module="vorto",
                    label="Vorto database",
                ),
            ]

        _make_fake_db(tmp_path, "vorto.db")  # scan would find this too

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[_FakeEntryPoint("vorto", vorto_factory)],
        ):
            targets = get_backup_targets(include_data_dir_scan=True)
        # The entry point path should be present
        assert any(t.path == Path("/explicit/vorto.db") for t in targets)
        # The scanned path should NOT be present (claimed by entry point)
        d = _data(tmp_path)
        assert not any(t.path == d / "vorto.db" for t in targets)

    def test_non_callable_entry_point_skipped(self) -> None:
        """Entry points that load to non-callables are skipped."""

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[_FakeEntryPoint("bad", "not_callable")],
        ):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert targets == []


# ── Edge cases ─────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_data_dir_not_exists(self) -> None:
        """When data_dir does not exist, scan returns empty."""
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        assert targets == []

    def test_multiple_targets_per_module(self, tmp_path: Path) -> None:
        """A single module can register multiple backup targets."""

        def multi_factory() -> list[BackupTarget]:
            return [
                BackupTarget(path=Path("/a/db1.db"), module="multi", label="DB 1"),
                BackupTarget(path=Path("/a/db2.db"), module="multi", label="DB 2"),
            ]

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[_FakeEntryPoint("multi", multi_factory)],
        ):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert len(targets) == 2

    def test_empty_factory(self) -> None:
        """A module can return an empty list (e.g. stateless module)."""

        def empty_factory() -> list[BackupTarget]:
            return []

        with patch.object(
            importlib.metadata,
            "entry_points",
            return_value=[_FakeEntryPoint("tempo", empty_factory)],
        ):
            targets = get_backup_targets(include_data_dir_scan=False)
        assert targets == []

    def test_scan_derives_module_name_correctly(self, tmp_path: Path) -> None:
        """Scan-derived module name uses stem for flat files, top dir for nested."""
        _make_fake_db(tmp_path, "vorto.db")  # → module "vorto"
        _make_fake_db(tmp_path, "medio", "medio.db")  # → module "medio"
        with patch.object(importlib.metadata, "entry_points", return_value=[]):
            targets = get_backup_targets()
        names = {t.module for t in targets}
        assert "vorto" in names
        assert "medio" in names
