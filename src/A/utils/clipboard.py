"""Clipboard integration for A.

Priority: native command -> pyperclip (optional) -> failure.
"""

from __future__ import annotations

import os
import subprocess
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


def _describe_env() -> str:
    """Build a diagnostic string describing the clipboard environment.

    Only called on failure, so its cost is irrelevant.
    """
    parts = [f"platform={sys.platform}"]
    if sys.platform == "linux":
        parts.append(f"DISPLAY={os.environ.get('DISPLAY', '<unset>')}")
        parts.append(f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '<unset>')}")
        for tool in ("wl-copy", "xclip", "xsel"):
            parts.append(f"{tool}={has_command(tool)}")
    elif sys.platform == "darwin":
        parts.append(f"pbcopy={has_command('pbcopy')}")
    elif sys.platform == "win32":
        parts.append(f"powershell={has_command('powershell')}")
        parts.append(f"clip={has_command('clip')}")
    return ", ".join(parts)


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to system clipboard.

    Tries native command first (platform-specific), falls back to pyperclip
    if available.

    Args:
        text: Text content to copy to clipboard.

    Returns:
        A tuple ``(success, reason)`` where:
        - ``success`` is ``True`` if copied successfully.
        - ``reason`` is an empty string on success, or a diagnostic
          message explaining why the operation failed.

    Examples:
        >>> ok, reason = copy_to_clipboard("Hello world")
        >>> if not ok:
        ...     print(f"Clipboard error: {reason}")
    """
    # ── Try native command first ──────────────────────────────────────
    native_what: str | None = None  # set on failure for diagnostics
    cmd = _get_native_command()
    if cmd is not None:
        # Use Popen with a gentle timeout: clipboard tools like xclip
        # write data to the clipboard immediately upon reading stdin
        # but may then block/hang on X/display initialization.
        # A hard timeout + kill loses the clipboard data that was
        # already written, causing false-negative warnings.
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _, stderr_text = proc.communicate(input=text, timeout=5.0)
        except subprocess.TimeoutExpired:
            # Data was already written to clipboard — don't kill,
            # just detach. Return success with a diagnostic note.
            try:
                proc.stdout.close()
                proc.stderr.close()
                proc.stdin.close()
            except OSError:
                pass
            return True, f"clipboard tool {cmd[0]} timed out (data was written)"
        if proc.returncode == 0:
            return True, ""

        detail = f"Command {cmd} failed (rc={proc.returncode})"
        if stderr_text:
            stderr_clean = stderr_text.strip()[:200]
            detail += f": {stderr_clean}"
        native_what = detail
    else:
        native_what = None  # no native command available

    # ── Fallback to pyperclip ────────────────────────────────────────
    if _pyperclip_available():
        try:
            import pyperclip
            pyperclip.copy(text)
            return True, ""
        except Exception as exc:
            reasons = []
            if native_what:
                reasons.append(native_what)
            reasons.append(f"pyperclip failed: {exc}")
            return False, "; ".join(reasons)

    # ── Nothing worked ───────────────────────────────────────────────
    env_info = _describe_env()
    if native_what:
        return False, f"{native_what} ({env_info})"
    return False, f"No clipboard tool found ({env_info})"


def copy_file(path: str | Path) -> tuple[bool, str]:
    """Copy a text file's content to clipboard.

    Reads the file as UTF-8 text and copies its content to clipboard.
    Binary files or files with encoding errors return a descriptive reason.

    Args:
        path: Path to the file to copy.

    Returns:
        A tuple ``(success, reason)`` — see ``copy_to_clipboard``.

    Examples:
        >>> ok, reason = copy_file("/path/to/notes.txt")
        >>> if not ok:
        ...     print(f"Clipboard error: {reason}")
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        return copy_to_clipboard(text)
    except OSError as exc:
        return False, f"File read error: {exc}"
    except UnicodeDecodeError as exc:
        return False, f"File encoding error: {exc}"


def _get_clipboard_command() -> list[str] | None:
    """Get the native clipboard command list for current platform (internal)."""
    return _get_native_command()


__all__ = [
    "copy_to_clipboard",
    "copy_file",
    "_get_native_command",
    "_pyperclip_available",
]