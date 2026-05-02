"""Configuration loader for A."""

import tomllib
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from A.core.paths import config_dir
from A.core.exceptions import ConfigError


@dataclass
class Config:
    """User configuration."""
    language: str = "eo"
    verbose: bool = False
    plugins: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


def load_config() -> Config:
    """Load configuration from config.toml."""
    config_path = config_dir() / "config.toml"
    
    if not config_path.exists():
        return Config()
    
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"failed to load config: {e}") from e
    
    return Config(
        language=data.get("language", "eo"),
        verbose=data.get("verbose", False),
        plugins=data.get("plugins", []),
        aliases=data.get("aliases", {}),
        settings=data.get("settings", {}),
    )


def save_config(config: Config) -> None:
    """Save configuration to config.toml."""
    config_path = config_dir() / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # TOML doesn't support dataclass, manual write
    lines = ["[A]", f"language = \"{config.language}\""]
    if config.verbose:
        lines.append("verbose = true")
    if config.plugins:
        lines.append(f"plugins = {config.plugins}")
    if config.aliases:
        lines.append("[A.aliases]")
        for k, v in config.aliases.items():
            lines.append(f'{k} = "{v}"')
    
    config_path.write_text("\n".join(lines) + "\n")


# User profile methods
def get_setting(key: str, default: Any = None) -> Any:
    """Get a user setting."""
    config = load_config()
    return config.settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set a user setting."""
    config = load_config()
    config.settings[key] = value
    save_config(config)


def load_profile() -> dict:
    """Load full user profile."""
    config = load_config()
    return {
        "language": config.language,
        "settings": config.settings,
    }


def save_profile(data: dict) -> None:
    """Save full user profile."""
    config = load_config()
    if "language" in data:
        config.language = data["language"]
    if "settings" in data:
        config.settings.update(data["settings"])
    save_config(config)


def export_profile(path: Path) -> None:
    """Export profile to JSON file."""
    profile = load_profile()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def import_profile(path: Path) -> None:
    """Import profile from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    save_profile(data)