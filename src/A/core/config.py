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


# ══════════════════════════════════════════════════════════════════════════════
# ConfigSchema — per-module declarative config (issue #60)
# ══════════════════════════════════════════════════════════════════════════════


class ConfigSchema:
    """Per-module configuration: CLI options + TOML persistence + interactive prompts.

    Derives all three access methods from a single declarative schema.
    TOML path: ``~/.config/A/<module>/config.toml``

    Usage::

        schema = ConfigSchema("A-modulo", {
            "provider": {"type": "str", "default": "ollama", "help": "LLM provider"},
            "timeout":  {"type": "int",  "default": 30,      "help": "Request timeout"},
        })

        # CLI integration:
        @app.command()
        def cmd(
            provider: str = schema.option("provider"),
            timeout: int = schema.option("timeout"),
        ):
            cfg = schema.load({"provider": provider, "timeout": timeout})

        # Interactive setup:
        answers = schema.interactive_prompt()
        schema.save(answers)
    """

    def __init__(self, module: str, fields: dict[str, dict[str, Any]]) -> None:
        """Initialize schema.

        Args:
            module: Module name (used as TOML subdirectory).
            fields: Dict mapping field name → config dict.
                    Each config dict requires ``default`` and may include
                    ``type`` (str/int/float/bool, default ``"str"``) and ``help``.
        """
        self.module = module
        self._fields: dict[str, dict[str, Any]] = {}
        for key, cfg in fields.items():
            self._fields[key] = {
                "type": cfg.get("type", "str"),
                "default": cfg["default"],
                "help": cfg.get("help", ""),
            }

    @property
    def _path(self) -> Path:
        return config_dir() / self.module / "config.toml"

    def default(self, key: str) -> Any:
        """Get the hardcoded default value for a field.

        Raises:
            KeyError: If field does not exist.
        """
        return self._fields[key]["default"]

    def option(self, key: str) -> Any:
        """Return a ``typer.Option`` for use in CLI function signatures.

        The returned Option carries the field's default, ``--<snake-case>``
        flag name, and help text. Bool fields get ``--flag/--no-flag``.

        Example::

            @app.command()
            def cmd(provider: str = schema.option("provider")): ...

        Raises:
            KeyError: If field does not exist.
        """
        import typer as _typer

        field = self._fields[key]
        flag = f"--{key.replace('_', '-')}"

        if field["type"] == "bool":
            return _typer.Option(field["default"], flag, f"--no-{flag.lstrip('--')}", help=field["help"])

        return _typer.Option(field["default"], flag, help=field["help"])

    def load(self, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Load config from TOML, apply CLI overrides.

        Priority: CLI > TOML > hardcoded default.

        Args:
            cli_overrides: Dict of CLI-provided values (only non-default values override).

        Returns:
            Dict with all schema fields populated.
        """
        # Start with hardcoded defaults
        result: dict[str, Any] = {k: f["default"] for k, f in self._fields.items()}

        # Override from TOML
        path = self._path
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            for key in self._fields:
                if key in data:
                    result[key] = data[key]

        # Override from CLI (values differing from hardcoded default)
        if cli_overrides:
            for key in self._fields:
                val = cli_overrides.get(key)
                if val is not None and val != self._fields[key]["default"]:
                    result[key] = val

        return result

    def save(self, data: dict[str, Any]) -> None:
        """Persist config to TOML file. Only writes known schema fields.

        Args:
            data: Dict of field values to persist.
        """
        path = self._path
        path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [f"# {self.module} configuration"]
        for key, field in self._fields.items():
            if key not in data:
                continue
            val = data[key]
            if val is None:
                continue
            if val == field["default"]:
                continue  # Skip defaults to keep TOML minimal
            if isinstance(val, bool):
                lines.append(f"{key} = {'true' if val else 'false'}")
            elif isinstance(val, str):
                # Escape quotes and backslashes
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            else:
                lines.append(f"{key} = {val}")

        path.write_text("\n".join(lines) + "\n")

    def interactive_prompt(self) -> dict[str, Any]:
        """Prompt user interactively for all fields.

        Returns dict of user answers. Fields with existing TOML values
        pre-fill prompts with those values as defaults.
        """
        import typer as _typer

        existing = self.load()
        answers: dict[str, Any] = {}

        for key, field in self._fields.items():
            current = existing.get(key, field["default"])
            ftype = field["type"]
            help_text = field.get("help", "")

            if ftype == "bool":
                val = _typer.confirm(
                    f"{help_text or key}",
                    default=bool(current),
                )
            elif ftype == "int":
                val = _typer.prompt(
                    f"{help_text or key}",
                    default=int(current) if current is not None else field["default"],
                    type=int,
                )
            elif ftype == "float":
                val = _typer.prompt(
                    f"{help_text or key}",
                    default=float(current) if current is not None else field["default"],
                    type=float,
                )
            else:
                val = _typer.prompt(
                    f"{help_text or key}",
                    default=str(current) if current is not None else field["default"],
                )

            answers[key] = val

        return answers