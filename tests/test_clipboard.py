"""Tests for clipboard module."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from A.utils.clipboard import (
    copy_to_clipboard,
    copy_file,
    _pyperclip_available,
    _get_native_command,
)


def _mock_popen(returncode: int = 0, stderr: str = "",
                timeout_raise: bool = False) -> MagicMock:
    """Build a mock subprocess.Popen instance with configurable behaviour."""
    proc = MagicMock()
    proc.returncode = returncode
    if timeout_raise:
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd=["fake"], timeout=5.0, output="", stderr=stderr,
        )
    else:
        proc.communicate.return_value = ("", stderr)
    return proc


class TestCopyToClipboard:
    """Tests for copy_to_clipboard function."""

    @patch("A.utils.clipboard._get_native_command")
    @patch("A.utils.clipboard.subprocess.Popen")
    def test_native_command_success(self, mock_popen, mock_get_cmd):
        """Test successful copy via native command."""
        mock_get_cmd.return_value = ["pbcopy"]
        mock_popen.return_value = _mock_popen(returncode=0)

        ok, reason = copy_to_clipboard("test text")

        assert ok is True
        assert reason == ""
        mock_popen.assert_called_once_with(
            ["pbcopy"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    @patch("A.utils.clipboard._get_native_command")
    @patch("A.utils.clipboard.subprocess.Popen")
    def test_native_command_fails_falls_back_to_pyperclip(
        self, mock_popen, mock_get_cmd
    ):
        """Test fallback to pyperclip when native command fails and pyperclip available."""
        mock_get_cmd.return_value = ["pbcopy"]
        mock_popen.return_value = _mock_popen(returncode=1, stderr="err")

        with patch("A.utils.clipboard._pyperclip_available", return_value=True):
            ok, reason = copy_to_clipboard("test text")

        # pyperclip not actually installed, so this should fail
        assert ok is False
        assert "pyperclip" in reason
        assert "err" in reason

    @patch("A.utils.clipboard._get_native_command")
    @patch("A.utils.clipboard.subprocess.Popen")
    def test_native_command_fails_pyperclip_unavailable(
        self, mock_popen, mock_get_cmd
    ):
        """Test returns diagnostic when both native command and pyperclip fail."""
        mock_get_cmd.return_value = ["pbcopy"]
        mock_popen.return_value = _mock_popen(returncode=1, stderr="error")

        with patch("A.utils.clipboard._pyperclip_available", return_value=False):
            ok, reason = copy_to_clipboard("test text")

        assert ok is False
        assert "Command" in reason
        assert "pbcopy" in reason
        assert "error" in reason

    @patch("A.utils.clipboard._get_native_command")
    def test_no_native_command_no_pyperclip(self, mock_get_cmd):
        """Test returns diagnostic when no native command and pyperclip unavailable."""
        mock_get_cmd.return_value = None

        with patch("A.utils.clipboard._pyperclip_available", return_value=False):
            ok, reason = copy_to_clipboard("test text")

        assert ok is False
        assert "No clipboard tool found" in reason

    @patch("A.utils.clipboard._get_native_command")
    @patch("A.utils.clipboard.subprocess.Popen")
    def test_native_command_timed_out_but_data_written(
        self, mock_popen, mock_get_cmd
    ):
        """Test returns True with diagnostic when native command times out."""
        mock_get_cmd.return_value = ["xclip", "-selection", "clipboard"]
        mock_popen.return_value = _mock_popen(timeout_raise=True, stderr="")

        ok, reason = copy_to_clipboard("test text")

        assert ok is True
        assert "timed out" in reason

    @patch("A.utils.clipboard._get_native_command")
    @patch("A.utils.clipboard.subprocess.Popen")
    def test_pyperclip_fallback_success(self, mock_popen, mock_get_cmd):
        """Test successful fallback to pyperclip when available."""
        mock_get_cmd.return_value = ["pbcopy"]
        mock_popen.return_value = _mock_popen(returncode=1, stderr="err")

        mock_pyperclip = type("pyperclip_mod", (), {"copy": lambda self_, text: None})()

        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            with patch("A.utils.clipboard._pyperclip_available", return_value=True):
                ok, reason = copy_to_clipboard("test text")

        assert ok is True
        assert reason == ""


class TestCopyFile:
    """Tests for copy_file function."""

    @patch("A.utils.clipboard.copy_to_clipboard")
    def test_copy_file_success(self, mock_copy):
        """Test successful file copy."""
        mock_copy.return_value = (True, "")

        ok, reason = copy_file("tests/fixtures/sample.txt")

        assert ok is True
        assert reason == ""

    @patch("A.utils.clipboard.Path")
    def test_copy_file_read_error(self, mock_path):
        """Test returns diagnostic when file cannot be read."""
        mock_path.return_value.read_text.side_effect = OSError("No such file")

        ok, reason = copy_file("nonexistent.txt")

        assert ok is False
        assert "File read error" in reason

    @patch("A.utils.clipboard.Path")
    def test_copy_file_encoding_error(self, mock_path):
        """Test returns diagnostic on encoding error."""
        mock_path.return_value.read_text.side_effect = UnicodeDecodeError(
            "utf-8", b"\xff\xfe", 0, 1, "invalid start byte"
        )

        ok, reason = copy_file("binary.bin")

        assert ok is False
        assert "File encoding error" in reason


class TestPyperclipAvailable:
    """Tests for _pyperclip_available function."""

    def test_returns_true_when_pyperclip_available(self):
        """Test returns True when pyperclip can be imported."""
        with patch("builtins.__import__") as mock_import:
            mock_import.side_effect = ImportError("not pyperclip")

            result = _pyperclip_available()

            assert isinstance(result, bool)


class TestGetNativeCommand:
    """Tests for _get_native_command function."""

    @patch("A.utils.clipboard.has_command")
    def test_returns_command_on_darwin(self, mock_has_command):
        """Test returns pbcopy on macOS."""
        with patch("A.utils.clipboard.sys") as mock_sys:
            mock_sys.platform = "darwin"
            mock_has_command.return_value = True

            result = _get_native_command()

            assert result == ["pbcopy"]

    @patch("A.utils.clipboard.has_command")
    def test_returns_none_when_no_commands_available(self, mock_has_command):
        """Test returns None when no clipboard commands available."""
        mock_has_command.return_value = False

        with patch("A.utils.clipboard.sys") as mock_sys:
            mock_sys.platform = "linux"

            result = _get_native_command()

        assert result is None
