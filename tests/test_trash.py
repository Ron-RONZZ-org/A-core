"""Tests for A.core.trash — move_to_trash, list_trash, empty_trash.

The ``conftest.py`` fixture ``isolate_core`` redirects ``data_dir()`` and
other A paths to ``tmp_path``, but the XDG Trash location uses
``$XDG_DATA_HOME`` or ``~/.local/share/Trash``, which is **not** redirected.
To avoid polluting the real trash, tests that call ``move_to_trash``
must either:

- Mock ``_trash_dir()`` to point under ``tmp_path``
- Or assert that the real trash is left unchanged.

We use monkeypatching to redirect the trash location.
"""

from pathlib import Path

import pytest


@pytest.fixture
def trash_dir(tmp_path: Path) -> Path:
    """Redirect the XDG Trash directory under tmp_path for isolation."""
    d = tmp_path / "Trash"
    d.mkdir(parents=True, exist_ok=True)

    # We monkey-patch the internal _trash_dir function so it returns
    # our test location.  The other helpers (_files_dir, _info_dir)
    # call _trash_dir(), so they are automatically redirected.
    import A.core.trash as trash_mod

    original = trash_mod._trash_dir

    def patched() -> Path:
        return d

    trash_mod._trash_dir = patched

    yield d

    # Restore original
    trash_mod._trash_dir = original


# ── move_to_trash ───────────────────────────────────────────────────────────────


def test_move_to_trash_moves_file(trash_dir: Path, tmp_path: Path) -> None:
    """move_to_trash() moves a file to the Trash files directory."""
    from A.core.trash import move_to_trash

    src = tmp_path / "test.txt"
    src.write_text("hello")

    info_path = move_to_trash(src)

    assert not src.exists()  # original is gone
    assert info_path.suffix == ".trashinfo"

    # File should be in Trash/files/
    files_dir = trash_dir / "files"
    assert (files_dir / "test.txt").exists()
    assert (files_dir / "test.txt").read_text() == "hello"


def test_move_to_trash_moves_directory(trash_dir: Path, tmp_path: Path) -> None:
    """move_to_trash() moves a directory recursively."""
    from A.core.trash import move_to_trash

    src = tmp_path / "mydir"
    src.mkdir(parents=True)
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")

    info_path = move_to_trash(src)

    assert not src.exists()
    info_dir = trash_dir / "info"
    files_dir = trash_dir / "files"
    assert (info_dir / "mydir.trashinfo").exists()
    assert (files_dir / "mydir").is_dir()
    assert (files_dir / "mydir" / "a.txt").read_text() == "a"


def test_move_to_trash_creates_trashinfo(trash_dir: Path, tmp_path: Path) -> None:
    """move_to_trash() creates a .trashinfo with Path and DeletionDate."""
    from A.core.trash import move_to_trash

    src = tmp_path / "info_test.txt"
    src.write_text("data")

    info_path = move_to_trash(src)
    content = info_path.read_text(encoding="utf-8")

    assert "[Trash Info]" in content
    assert "Path=" in content
    assert "DeletionDate=" in content
    # Path should resolve to the absolute original path
    from urllib.parse import unquote
    for line in content.splitlines():
        if line.startswith("Path="):
            restored = unquote(line[5:])
            assert restored == str(src.resolve())
            break


def test_move_to_trash_raises_on_nonexistent(trash_dir: Path) -> None:
    """move_to_trash() raises FileNotFoundError for missing path."""
    from A.core.trash import move_to_trash

    with pytest.raises(FileNotFoundError, match="non-existent"):
        move_to_trash(Path("/nonexistent/path"))


def test_move_to_trash_handles_collision(trash_dir: Path, tmp_path: Path) -> None:
    """move_to_trash() appends a counter when the same filename is trashed twice."""
    from A.core.trash import move_to_trash

    src = tmp_path / "dup.txt"

    # First trash: create file, trash it
    src.write_text("first")
    info1 = move_to_trash(src)
    assert info1.name == "dup.txt.trashinfo"

    # Re-create file with same name, trash again
    src.write_text("second")
    info2 = move_to_trash(src)
    assert info2.name == "dup (1).txt.trashinfo"

    files_dir = trash_dir / "files"
    assert (files_dir / "dup.txt").read_text() == "first"
    assert (files_dir / "dup (1).txt").read_text() == "second"


# ── list_trash ──────────────────────────────────────────────────────────────────


def test_list_trash_empty(trash_dir: Path) -> None:
    """list_trash() returns empty list when trash is empty."""
    from A.core.trash import list_trash

    assert list_trash() == []


def test_list_trash_finds_items(trash_dir: Path, tmp_path: Path) -> None:
    """list_trash() returns trashed items."""
    from A.core.trash import move_to_trash, list_trash

    # Create file under data_dir() so it's A-related
    from A.core.paths import data_dir
    a_file = data_dir() / "test.txt"
    a_file.parent.mkdir(parents=True, exist_ok=True)
    a_file.write_text("hello")

    move_to_trash(a_file)
    items = list_trash()

    assert len(items) == 1
    assert items[0]["original_path"] == a_file.resolve()
    assert items[0]["trash_path"] is not None
    assert items[0]["trash_path"].name == "test.txt"
    assert items[0]["deleted_at"] != ""


def test_list_trash_filters_non_a(trash_dir: Path, tmp_path: Path) -> None:
    """list_trash(only_a_related=True) skips items outside A dirs."""
    from A.core.trash import move_to_trash, list_trash

    # Create file outside A dirs (under tmp_path directly)
    src = tmp_path / "non_a_file.txt"
    src.write_text("not A related")
    move_to_trash(src)

    items = list_trash(only_a_related=True)
    assert len(items) == 0

    items_all = list_trash(only_a_related=False)
    assert len(items_all) >= 1


# ── empty_trash ─────────────────────────────────────────────────────────────────


def test_empty_trash_removes_items(trash_dir: Path, tmp_path: Path) -> None:
    """empty_trash() deletes all items from the trash."""
    from A.core.trash import move_to_trash, empty_trash, list_trash

    from A.core.paths import data_dir
    a_file = data_dir() / "to_empty.txt"
    a_file.parent.mkdir(parents=True, exist_ok=True)
    a_file.write_text("delete me")

    move_to_trash(a_file)
    assert len(list_trash()) == 1

    count = empty_trash()
    assert count >= 1
    assert len(list_trash()) == 0


def test_empty_trash_multiple(trash_dir: Path, tmp_path: Path) -> None:
    """empty_trash() removes multiple items."""
    from A.core.trash import move_to_trash, empty_trash, list_trash
    from A.core.paths import data_dir

    for name in ("a.txt", "b.txt", "c.txt"):
        f = data_dir() / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(name)
        move_to_trash(f)

    assert len(list_trash()) == 3

    count = empty_trash()
    assert count == 3
    assert len(list_trash()) == 0


def test_empty_trash_idempotent(trash_dir: Path) -> None:
    """empty_trash() is safe to call on an already empty trash."""
    from A.core.trash import empty_trash

    count = empty_trash()
    assert count == 0

    count = empty_trash()
    assert count == 0
