"""Core types for A."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CommandResult:
    """Result from a command execution."""
    success: bool
    message: str = ""
    data: dict = None


@dataclass
class PluginInfo:
    """Plugin information."""
    name: str
    version: str = ""
    description: str = ""
    commands: dict[str, Any] = None


@dataclass
class Config:
    """User configuration."""
    language: str = "eo"
    verbose: bool = False
    plugins: list = None
    aliases: dict = None
    settings: dict = None
    
    def __post_init__(self):
        if self.plugins is None:
            self.plugins = []
        if self.aliases is None:
            self.aliases = {}
        if self.settings is None:
            self.settings = {}