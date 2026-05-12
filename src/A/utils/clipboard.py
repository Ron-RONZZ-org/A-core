"""Clipboard integration for A.

Priority: native command -> pyperclip (optional) -> failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from A.utils.subprocess import has_command, run, SubprocessResult


def _get_native_command() -> list[str] | None:
    """Detect best available native clipboard command for the current platform."""
    if sys.platform == "darwin":
        # macOS
        if has_command("pbcopy"):
            return ["pbcopy"]
    elif sys.platform == "win32":
        # Windows - prefer PowerShell, fall back to clip
        if has_command("powershell"):
            return ["powershell", "-Command", "Set-Clipboard"]
        elif has_command("clip"):
            return ["clip"]
    else:
        # Linux - try Wayland first, then X11 tools
        if has_command("wl-copy"):
            return ["wl-copy"]
        if has_command("xclip"):
            return ["xclip", "-selection", "clipboard"]
        if has_command("xsel"):
            return ["xsel", "--clipboard", "--input"]
    return None


def _pyperclip_available() -> bool:
    """Check if pyperclip is installed (runtime detection)."""
    try:
        import pyperclip  # noqa: F401
        return True
    except ImportError:
        return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard.

    Tries native command first (platform-specific), falls back to pyperclip
    if available. Returns False if no clipboard method is available.

    Args:
        text: Text content to copy to clipboard.

    Returns:
        True if copied successfully, False otherwise.

    Examples:
        >>> if copy_to_clipboard("Hello world"):
        ...     print("Copied!")
    """
    cmd = _get_native_command()
    if cmd is not None:
        # Short timeout: if clipboard command hangs (e.g. no X display),
        # fail fast rather than blocking for the default 30s.
        result = run(*cmd, input=text, timeout=2.0)
        if result.success:
            return True

    # Fallback to pyperclip if available
    if _pyperclip_available():
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    return False


def copy_file(path: str | Path) -> bool:
    """Copy a text file's content to clipboard.

    Reads the file as UTF-8 text and copies its content to clipboard.
    Binary files or files with encoding errors return False.

    Args:
        path: Path to the file to copy.

    Returns:
        True if content was copied successfully, False if file read or
        clipboard operation failed.

    Examples:
        >>> if copy_file("/path/to/notes.txt"):
        ...     print("File content copied!")
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        return copy_to_clipboard(text)
    except (OSError, UnicodeDecodeError):
        return False


def _get_clipboard_command() -> list[str] | None:
    """Get the native clipboard command list for current platform (internal)."""
    return _get_native_command()


__all__ = [
    "copy_to_clipboard",
    "copy_file",
    "_get_native_command",
    "_pyperclip_available",
]