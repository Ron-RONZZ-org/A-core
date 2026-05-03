"""Base exceptions for A."""

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