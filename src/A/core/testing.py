"""Testing utilities for A-modules: isolate filesystem, keyring, singletons.

Usage in a module's ``tests/conftest.py``:

.. code-block:: python

    import pytest
    from A.core.testing import patch_paths, patch_keyring

    @pytest.fixture(autouse=True)
    def isolate_module(monkeypatch, tmp_path):
        patch_paths(monkeypatch, tmp_path)
        patch_keyring(monkeypatch)
        # Module-specific singleton resets go here...

For subprocess / CLI smoke tests, use :func:`simulate`:

.. code-block:: python

    import os
    import subprocess
    from A.core.testing import simulate

    env = os.environ.copy()
    with simulate(tmp_path, env=env):
        subprocess.run(["A", "modulo", "ls"], env=env, check=True)
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from A.core.paths import data_dir


def patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect all A-core path functions to *tmp_path* subdirectories.

    Sets the ``A_DIR`` environment variable so that every path function
    returns a subdirectory under *tmp_path*:

    ============= ==================
    Function      Under ``A_DIR``
    ============= ==================
    ``data_dir``  ``tmp_path / "data"``
    ``config_dir`` ``tmp_path / "config"``
    ``cache_dir`` ``tmp_path / "cache"``
    ``state_dir`` ``tmp_path / "state"``
    ============= ==================

    Subdirectories are **not** pre-created (matches the lazy contract of
    :func:`A.core.paths.ensure_dirs`).
    """
    monkeypatch.setenv("A_DIR", str(tmp_path))


def patch_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock ``A.core.ai`` keyring functions to prevent real keyring writes.

    Both ``save_api_key`` and ``get_api_key`` are replaced with no-op /
    mock implementations so that tests never touch the system keyring.
    """
    monkeypatch.setattr("A.core.ai.save_api_key", lambda _key, **kw: True)
    monkeypatch.setattr("A.core.ai.get_api_key", lambda **kw: "mock-key")


@contextmanager
def simulate(tmp_path: Path, env: dict[str, str] | None = None) -> Iterator[Path]:
    """Context manager that isolates A paths under *tmp_path*.

    Sets the ``A_DIR`` environment variable (or updates *env* if provided)
    and verifies that :func:`~A.core.paths.data_dir` resolves under
    *tmp_path*.

    Usage (in-process, with :func:`patch_paths` semantics)::

        def test_foo(tmp_path):
            with simulate(tmp_path):
                # data_dir() returns tmp_path / "data"
                ...

    Usage (subprocess testing)::

        env = os.environ.copy()
        with simulate(tmp_path, env=env):
            subprocess.run(["A", "modulo", "ls"], env=env, check=True)

    Yields:
        *tmp_path* for convenience.

    Raises:
        RuntimeError: If ``A_DIR`` isolation did not take effect
            (i.e. ``data_dir()`` still returns the real user directory).
    """
    _orig: str | None = os.environ.get("A_DIR")
    _target = str(tmp_path)

    os.environ["A_DIR"] = _target
    if env is not None:
        env["A_DIR"] = _target

    # Safety guard: verify isolation took effect
    resolved = data_dir()
    try:
        resolved.relative_to(tmp_path)
    except ValueError:
        raise RuntimeError(
            f"simulate() failed: data_dir() = {resolved} is not under "
            f"tmp_path = {tmp_path}. A_DIR='{_target}' did not redirect "
            f"paths away from the real user directory."
        ) from None

    try:
        yield tmp_path
    finally:
        if _orig is not None:
            os.environ["A_DIR"] = _orig
        else:
            os.environ.pop("A_DIR", None)
