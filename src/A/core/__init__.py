"""A-core - minimal CLI framework core."""

from A.core.types import CommandResult, PluginInfo, Config
from A.core.paths import data_dir, config_dir, cache_dir, state_dir, ensure_dirs
from A.core.i18n import tr, set_language, available_languages, get_current_language
from A.core.exceptions import AError, ConfigError, PluginError, DataError, CommandError
from A.core.config import load_config, save_config, Config, get_setting, set_setting, load_profile, save_profile, export_profile, import_profile
from A.core.crypto import encrypt, decrypt, encrypt_str, decrypt_str
from A.core.keyring import get_password, set_password, delete_password
from A.core.export import export_json, export_toml, export_json_stream, export_toml_stream
from A.core.import_ import import_json, import_toml, import_auto, import_stream
from A.core.markdown_parser import render_markdown
from A.core.markdown_html_view import preview_markdown, preview_html, clear_cache
from A.core.ai import get_provider, save_api_key, get_api_key
from A.core.providers import LLMProvider, ToolCall, LLMResponse
from A.core.migration import get_status, migrate_all, register_migration, MigrationResult, MigrationStatus
from A.core.network import format_connection_error

# Lazy import: http.py may not exist on older installations.
try:
    from A.core.http import fetch_text as _fetch_text
    fetch_text = _fetch_text
except ImportError:
    fetch_text = None  # type: ignore[assignment]

__all__ = [
    # Types
    "CommandResult",
    "PluginInfo",
    "Config",
    # Paths
    "data_dir",
    "config_dir",
    "cache_dir",
    "state_dir",
    "ensure_dirs",
    # i18n
    "tr",
    "set_language",
    "available_languages",
    "get_current_language",
    # Exceptions
    "AError",
    "ConfigError",
    "PluginError",
    "DataError",
    "CommandError",
    # Config
    "load_config",
    "save_config",
    "get_setting",
    "set_setting",
    "load_profile",
    "save_profile",
    "export_profile",
    "import_profile",
    # Crypto
    "encrypt",
    "decrypt",
    "encrypt_str",
    "decrypt_str",
    # Keyring
    "get_password",
    "set_password",
    "delete_password",
    # Export
    "export_json",
    "export_toml",
    "export_json_stream",
    "export_toml_stream",
    # Import
    "import_json",
    "import_toml",
    "import_auto",
    "import_stream",
    # Markdown
    "render_markdown",
    "preview_markdown",
    "preview_html",
    "clear_cache",
    # AI / LLM providers
    "get_provider",
    "save_api_key",
    "get_api_key",
    "LLMProvider",
    # Migration
    "get_status",
    "migrate_all",
    "register_migration",
    "MigrationResult",
    "MigrationStatus",
    # Network
    "format_connection_error",
]

if fetch_text is not None:
    __all__.append("fetch_text")
