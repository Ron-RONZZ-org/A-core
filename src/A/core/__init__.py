"""A-core - minimal CLI framework core."""

from A.core.types import CommandResult, PluginInfo, Config
from A.core.paths import data_dir, config_dir, cache_dir, state_dir, ensure_dirs
from A.core.i18n import tr, set_language, available_languages, get_current_language
from A.core.exceptions import AError, ConfigError, PluginError, DataError, CommandError
from A.core.config import load_config, save_config, Config, get_setting, set_setting, load_profile, save_profile, export_profile, import_profile
from A.core.crypto import encrypt, decrypt, encrypt_str, decrypt_str
from A.core.export import export_json, export_toml, export_json_stream, export_toml_stream
from A.core.import_ import import_json, import_toml, import_auto, import_stream

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
]