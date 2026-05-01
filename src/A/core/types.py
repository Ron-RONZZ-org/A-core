"""Core types for A."""

from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result from a command execution."""
    success: bool
    message: str = ""
    data: dict = None


@dataclass
class PluginInfo:
    """Info about a registered plugin."""
    name: str
    version: str
    description: str
    cli: object  # Typer app


@dataclass  
class Config:
    """User configuration."""
    language: str = "eo"
    verbose: bool = False
    plugins: list[str] = None
    
    def __post_init__(self):
        if self.plugins is None:
            self.plugins = []