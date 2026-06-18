"""Base exceptions for A."""

from __future__ import annotations

from typing import Any


class AError(Exception):
    """Base exception for A."""
    
    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message)
        self.message = message
        self.details = kwargs


class ConfigError(AError):
    """Configuration-related errors."""
    pass


class PluginError(AError):
    """Plugin loading errors."""
    pass


class DataError(AError):
    """Database errors."""
    pass


class CommandError(AError):
    """Command execution errors."""
    pass


class RegistryError(AError):
    """Module registry fetch/parse errors."""
    pass


class ProtectedPathError(AError):
    """Raised when attempting to delete/modify a protected A directory.

    A directory is *protected* when it (or an ancestor) contains a
    ``.a-protected`` marker file.  See :func:`A.core.paths.protect_directory`.
    """

    def __init__(self, path: "str | Path", operation: str = "delete"):
        from pathlib import Path

        self.path = Path(path)
        self.operation = operation
        super().__init__(
            f"Cannot {operation} protected path: {path}. "
            f"Remove the '.a-protected' marker file first "
            f"if you are sure."
        )


class PathTraversalError(AError):
    """Raised when a file path escapes all allowed base directories.

    Used by :func:`A.core.file_security.resolve_safe_path` when a
    resolved path does not fall within any of the configured allowlist
    base directories.
    """

    def __init__(self, path: str, allowed_bases: "list[str]" | None = None):
        self.path = path
        self.allowed_bases = allowed_bases or []
        bases_str = ", ".join(self.allowed_bases) if self.allowed_bases else "(none)"
        super().__init__(
            f"Path traversal detected: '{path}' is not under any allowed "
            f"base directory ({bases_str})."
        )