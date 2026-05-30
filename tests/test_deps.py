"""Tests for A.utils.deps — dependency auto-install utilities."""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Any
from unittest.mock import patch

import pytest

# Fake module name that doesn't exist
_FAKE_MODULE = "_test_fake_dep_do_not_install_"
_real_import_module = importlib.import_module


class TestGetPipCommand:
    """get_pip_command() must try uv > pip > pip3 > python3 -m pip > sys.executable -m pip."""

    def test_uv_available(self) -> None:
        """When uv is in PATH, return ['uv', 'pip']."""
        with patch("shutil.which", side_effect=lambda x: "/usr/bin/uv" if x == "uv" else None):
            from A.utils.deps import get_pip_command
            assert get_pip_command() == ["/usr/bin/uv", "pip"]

    def test_pip_available_when_uv_missing(self) -> None:
        """Fallback to pip when uv is not available."""
        def _which(cmd: str) -> str | None:
            return "/usr/bin/pip" if cmd in {"pip", "pip3"} else None
        with patch("shutil.which", side_effect=_which):
            from A.utils.deps import get_pip_command
            result = get_pip_command()
            assert result == ["/usr/bin/pip"] or result == ["/usr/bin/pip3"]

    def test_python3_m_as_pip(self) -> None:
        """Fallback to python3 -m pip when no pip binary found."""
        def _which(cmd: str) -> str | None:
            return "/usr/bin/python3" if cmd == "python3" else None
        with patch("shutil.which", side_effect=_which):
            from A.utils.deps import get_pip_command
            assert get_pip_command() == ["/usr/bin/python3", "-m", "pip"]

    def test_sys_executable_last_resort(self) -> None:
        """Last resort: sys.executable -m pip."""
        with patch("shutil.which", return_value=None):
            from A.utils.deps import get_pip_command
            assert get_pip_command() == [sys.executable, "-m", "pip"]


class TestEnsureDependency:
    """ensure_dependency() covers fast-path, user prompt, install, and error handling."""

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_already_installed(self, _mock_isatty: Any) -> None:
        """When module is already importable, return immediately (fast path)."""
        from A.utils.deps import ensure_dependency
        ensure_dependency("json")  # should not raise

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_auto_install_declined(self, _mock_isatty: Any) -> None:
        """When user declines the prompt, raise ImportError."""
        from A.utils.deps import ensure_dependency
        with (
            patch.object(importlib, "import_module", side_effect=self._fail_for_fake),
            patch("typer.confirm", return_value=False),
        ):
            with pytest.raises(ImportError, match="not installed"):
                ensure_dependency(_FAKE_MODULE)

    @staticmethod
    def _fail_for_fake(name: str) -> object:
        """Import helper: raise ImportError only for _FAKE_MODULE."""
        if name == _FAKE_MODULE:
            msg = f"module {name} not found"
            raise ImportError(msg)
        return _real_import_module(name)

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_install_success(self, _mock_isatty: Any) -> None:
        """After successful install, re-import and return."""
        from A.utils.deps import ensure_dependency

        fake_call_count: list[int] = [0]

        def _import(name: str) -> object:
            if name == _FAKE_MODULE:
                fake_call_count[0] += 1
                if fake_call_count[0] > 1:
                    return object()
                msg = f"module {name} not found"
                raise ImportError(msg)
            return _real_import_module(name)

        with (
            patch.object(importlib, "import_module", side_effect=_import),
            patch("typer.confirm", return_value=True),
            # Mock get_pip_command to return a predictable command
            patch("A.utils.deps.get_pip_command", return_value=["echo"]),
            # Patch subprocess.run at the A.utils.deps level to avoid circular import issues
            patch("A.utils.deps.subprocess.run") as mock_run,
            patch("A.utils.deps.importlib.invalidate_caches") as mock_inval,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "install", "fakepkg"],
                returncode=0, stdout="Success", stderr="",
            )
            ensure_dependency(_FAKE_MODULE, "fakepkg")
            mock_run.assert_called_once()
            mock_inval.assert_called_once()
            # Verify it was called with the right package name
            call_args = mock_run.call_args[0][0]
            assert "fakepkg" in call_args

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_install_failure_shows_stderr(self, _mock_isatty: Any) -> None:
        """When install fails, raise ImportError and surface stderr."""
        from A.utils.deps import ensure_dependency
        with (
            patch.object(importlib, "import_module", side_effect=self._fail_for_fake),
            patch("typer.confirm", return_value=True),
            patch("A.utils.deps.get_pip_command", return_value=["echo"]),
            patch("A.utils.deps.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "install", _FAKE_MODULE],
                returncode=1, stdout="", stderr="ERROR: Permission denied",
            )
            with pytest.raises(ImportError, match="Permission denied"):
                ensure_dependency(_FAKE_MODULE)

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_install_timeout(self, _mock_isatty: Any) -> None:
        """When subprocess.run raises TimeoutExpired, raise ImportError."""
        from A.utils.deps import ensure_dependency
        with (
            patch.object(importlib, "import_module", side_effect=self._fail_for_fake),
            patch("typer.confirm", return_value=True),
            patch("A.utils.deps.get_pip_command", return_value=["echo"]),
            patch("A.utils.deps.subprocess.run", side_effect=subprocess.TimeoutExpired(
                cmd=["echo", "install", "bigpkg"], timeout=30,
            )),
        ):
            with pytest.raises(ImportError, match="timed out"):
                ensure_dependency(_FAKE_MODULE, "bigpkg", timeout=30)

    @patch("A.utils.deps.sys.stdin.isatty", return_value=True)
    def test_custom_package_name(self, _mock_isatty: Any) -> None:
        """When package != module (e.g. yt-dlp vs yt_dlp), use package for install."""
        from A.utils.deps import ensure_dependency

        fake_call_count: list[int] = [0]

        def _import(name: str) -> object:
            if name == _FAKE_MODULE:
                fake_call_count[0] += 1
                if fake_call_count[0] > 1:
                    return object()
                msg = f"module {name} not found"
                raise ImportError(msg)
            return _real_import_module(name)

        with (
            patch.object(importlib, "import_module", side_effect=_import),
            patch("typer.confirm", return_value=True),
            patch("A.utils.deps.get_pip_command", return_value=["uv", "pip"]),
            patch("A.utils.deps.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["uv", "pip", "install", "yt-dlp"],
                returncode=0, stdout="", stderr="",
            )
            ensure_dependency(_FAKE_MODULE, "yt-dlp")
            install_args = mock_run.call_args[0][0]
            assert "yt-dlp" in install_args

    def test_auto_install_false_no_tty(self) -> None:
        """When auto_install=False and import fails, raise immediately."""
        from A.utils.deps import ensure_dependency
        with (
            patch.object(importlib, "import_module", side_effect=self._fail_for_fake),
            patch("A.utils.deps.sys.stdin.isatty", return_value=False),
        ):
            with pytest.raises(ImportError):
                ensure_dependency(_FAKE_MODULE, auto_install=False)
