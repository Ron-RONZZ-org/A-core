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
"""

from pathlib import Path
from typing import Any

import pytest


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
