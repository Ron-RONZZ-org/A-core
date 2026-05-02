"""Core types for A."""

from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result from a command execution."""
    success: bool
    message: str = ""
    data: dict = None