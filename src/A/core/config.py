"""Configuration loader for A."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
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
    settings: dict[str, Any] = field(default_factory=dict)  # legacy flat [A.settings]
    module_settings: dict[str, dict[str, Any]] = field(default_factory=dict)  # new [module] sections


def _cfg_path() -> Path:
    return config_dir() / "config.toml"


def load_config() -> Config:
    """Load configuration from config.toml."""
    config_path = _cfg_path()

    if not config_path.exists():
        return Config()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"failed to load config: {e}") from e

    # Support both top-level format (legacy) and [A] section
    root = data.get("A", data)

    config = Config(
        language=root.get("language", "eo"),
        verbose=root.get("verbose", False),
        plugins=root.get("plugins", []),
        aliases=root.get("aliases", {}),
        settings=dict(root.get("settings", {})),
    )

    # Read top-level [module] sections (everything not starting with uppercase)
    for section, values in data.items():
        if section == "A":
            continue
        if isinstance(values, dict):
            config.module_settings[section] = dict(values)

    return config


def save_config(config: Config) -> None:
    """Save configuration to config.toml (incremental tomlkit update).

    Preserves comments and unknown sections via tomlkit parse-modify-write.

    Args:
        config: The configuration to persist.
    """
    import tomlkit
    from tomlkit import dumps

    config_path = _cfg_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Parse existing file to preserve comments and unknown sections
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        doc = tomlkit.parse(raw)
    else:
        doc = tomlkit.document()

    # ── [A] section (top-level fields) ──────────────────────────────────
    if "A" not in doc:
        doc["A"] = tomlkit.table()
    a_tbl = doc["A"]

    a_tbl["language"] = config.language

    if config.verbose:
        a_tbl["verbose"] = True
    elif "verbose" in a_tbl:
        del a_tbl["verbose"]

    if config.plugins:
        arr = tomlkit.array()
        for p in config.plugins:
            arr.append(p)
        a_tbl["plugins"] = arr
    elif "plugins" in a_tbl:
        del a_tbl["plugins"]

    if config.aliases:
        alias_tbl = tomlkit.table()
        for k, v in config.aliases.items():
            alias_tbl[k] = v
        a_tbl["aliases"] = alias_tbl
    elif "aliases" in a_tbl:
        del a_tbl["aliases"]

    # Legacy flat [A.settings] (keys not belonging to any module)
    if config.settings:
        settings_tbl = tomlkit.table()
        for k, v in config.settings.items():
            settings_tbl[k] = v
        a_tbl["settings"] = settings_tbl
    elif "settings" in a_tbl:
        del a_tbl["settings"]

    # ── Per-module [module] sections ────────────────────────────────────
    for module, module_cfg in config.module_settings.items():
        _write_module_section(doc, module, module_cfg)

    # ── Clean up migrated keys from legacy [A.settings] ─────────────────
    old_settings = a_tbl.get("settings")
    if old_settings is not None:
        keys_to_clean = set()
        for module in config.module_settings:
            prefix = f"{module}."
            for k in list(old_settings.keys()):
                if isinstance(k, str) and k.startswith(prefix):
                    keys_to_clean.add(k)
        for k in keys_to_clean:
            del old_settings[k]

    output = dumps(doc)
    # Inject commented-default sections for newly-registered modules
    output = _inject_missing_sections(output)

    config_path.write_text(output, encoding="utf-8")


def _write_module_section(doc: Any, module: str, settings: dict[str, Any]) -> None:
    """Update or create a ``[module]`` section, preserving comments.

    Removes any keys that exist in the file but not in *settings*
    (full replacement of the section's values).
    """
    import tomlkit

    if module in doc:
        tbl = doc[module]
    else:
        tbl = tomlkit.table()
        doc[module] = tbl

    # Remove keys no longer present in settings
    for k in list(tbl.keys()):
        if k not in settings:
            del tbl[k]

    for k, v in settings.items():
        if v is None:
            if k in tbl:
                del tbl[k]
        else:
            tbl[k] = v


# ── User profile helpers (legacy flat API) ─────────────────────────────────


def get_setting(key: str, default: Any = None) -> Any:
    """Get a user setting (legacy flat ``[A.settings]``)."""
    config = load_config()
    return config.settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set a user setting (legacy flat ``[A.settings]``)."""
    config = load_config()
    config.settings[key] = value
    save_config(config)


def load_profile() -> dict:
    """Load full user profile (legacy)."""
    config = load_config()
    return {
        "language": config.language,
        "settings": config.settings,
    }


def save_profile(data: dict) -> None:
    """Save full user profile (legacy)."""
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
# Centralised module settings — new [module] section convention
# ══════════════════════════════════════════════════════════════════════════════


_SENTINEL = object()


def get_module_setting(module: str, key: str, default: Any = None) -> Any:
    """Read a module setting from the central config.

    Tries ``config[module][key]`` first (new top-level section convention).
    Falls back to ``config["A"]["settings"][f"{module}.{key}"]`` (legacy
    dot-notation under ``[A.settings]``).

    Args:
        module: Module name (e.g. ``"filmeto"``, ``"uzanto"``).
        key: Setting key (e.g. ``"default_output"``).
        default: Fallback value if the key is not set.

    Returns:
        The stored value, or *default*.
    """
    config = load_config()
    # New format: top-level [module] section
    module_cfg = config.module_settings.get(module)
    if module_cfg is not None and key in module_cfg:
        return module_cfg[key]
    # Legacy fallback: dot-notation under [A.settings]
    full_key = f"{module}.{key}"
    return config.settings.get(full_key, default)


def set_module_setting(module: str, key: str, value: Any) -> None:
    """Write a module setting to the central config.

    Persists to the top-level ``[module]`` section and cleans up any legacy
    ``[A.settings]`` entry with the same ``module.key`` name.

    Args:
        module: Module name.
        key: Setting key.
        value: Value to store (must be TOML-serialisable).
    """
    config = load_config()
    # New format: top-level [module] section
    config.module_settings.setdefault(module, {})[key] = value
    # Clean up legacy dot-notation key
    config.settings.pop(f"{module}.{key}", None)
    save_config(config)


# ══════════════════════════════════════════════════════════════════════════════
# Module config defaults — commented-out template for user discovery
# ══════════════════════════════════════════════════════════════════════════════


_DEFAULT_MODULE_CONFIGS: dict[str, dict[str, Any]] = {}


def get_module_defaults(module: str) -> dict[str, tuple[Any, str]] | None:
    """Return the registered defaults for *module*, or ``None`` if unknown."""
    return _DEFAULT_MODULE_CONFIGS.get(module)


def register_module_defaults(module: str, defaults: dict[str, tuple[Any, str]]) -> None:
    """Register module config defaults so they appear in the config file.

    Called at module import time.  *defaults* maps key → (default_value, help_text).

    The actual file write is deferred to :func:`save_config` which calls
    :func:`_flush_pending_defaults` before saving. This avoids file I/O at
    import time (safe for tests).
    """
    _DEFAULT_MODULE_CONFIGS[module] = dict(defaults)


def _flush_pending_defaults(doc: Any) -> None:
    """Append commented ``[module]`` sections for newly-registered modules.

    Operates on the *parsed* tomlkit document so comments are preserved.
    Only writes if the module's section does not yet exist.
    """
    from tomlkit import table as _toml_table

    for module, defaults in _DEFAULT_MODULE_CONFIGS.items():
        if module in doc:
            continue  # Already has a section
        # Build a commented table by appending text after the doc is dumped
        # — handled at the string level below
        setattr(doc, f"_pending_{module}", defaults)


def _discover_plugin_defaults() -> None:
    """Import config modules of all installed A-plugins to trigger registration.

    Each A-module's ``config.py`` calls :func:`register_module_defaults` at
    import time.  This function discovers all ``A.commands`` entry points and
    imports their ``<package>.config`` submodule so those registration calls
    happen even before the user runs any module-specific command.

    Safe to call repeatedly — Python caches imported modules.
    """
    import importlib
    import importlib.metadata as _imeta

    try:
        eps = _imeta.entry_points(group="A.commands")
    except TypeError:
        eps = _imeta.entry_points().get("A.commands", [])

    for ep in eps:
        # ep.value looks like "A_medio.cli:app" — derive package name
        package = ep.value.split(".")[0]
        try:
            importlib.import_module(f"{package}.config")
        except ImportError:
            pass  # Module doesn't have a config.py — that's fine


def _inject_missing_sections(raw: str) -> str:
    """Append commented ``[module]`` sections that are not yet in *raw*.

    First discovers all installed plugin config modules (so their defaults
    are registered), then appends any missing sections.

    This is a pure-string operation, done once during ``save_config``
    before the tomlkit document is dumped.
    """
    _discover_plugin_defaults()
    if not _DEFAULT_MODULE_CONFIGS:
        return raw

    # Parse to check what's already present
    try:
        data = tomllib.loads(raw) if raw else {}
    except Exception:
        return raw  # Malformed — don't touch

    lines: list[str] = []
    for module, defaults in _DEFAULT_MODULE_CONFIGS.items():
        if module in data:
            continue
        lines.append("")
        lines.append(f"[{module}]")
        for key, (default, help_text) in defaults.items():
            if help_text:
                lines.append(f"# {help_text}")
            lines.append(f"# {key} = {_toml_literal(default)}")

    if not lines:
        return raw

    return raw.rstrip() + "\n" + "\n".join(lines) + "\n"


def _toml_literal(value: Any) -> str:
    """Render a Python value as a TOML literal for commented defaults."""
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        if not value:
            return '""'
        return f'"{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_toml_literal(v) for v in value)
        return f"[{items}]"
    return str(value)


# ══════════════════════════════════════════════════════════════════════════════
# ConfigSchema — per-module declarative config (issue #60, legacy)
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
