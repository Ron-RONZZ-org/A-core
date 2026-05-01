"""Configuration loader for A."""

import tomllib
from pathlib import Path
from dataclasses import dataclass, field

from A.core.paths import config_dir
from A.core.exceptions import ConfigError


@dataclass
class Config:
    """User configuration."""
    language: str = "eo"
    verbose: bool = False
    plugins: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)


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