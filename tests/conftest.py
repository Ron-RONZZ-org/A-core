"""A-core test configuration — prevents tests from writing to real filesystem."""

import pytest
from A.core.testing import patch_paths


@pytest.fixture(autouse=True)
def isolate_core(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Redirect all A-core path functions to a temporary directory.

    Without this, tests like ``test_paths`` would create real
    ``~/.local/share/A/``, ``~/.config/A/``, etc. on the developer's
    machine.
    """
    patch_paths(monkeypatch, tmp_path)
