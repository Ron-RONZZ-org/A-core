# AGENTS.md — Root Project Rules for A-core
This file extends [A-workspace](./workspace/AGENTS.md).

This is the canonical, repo-wide instruction file for AI agents working on **A-core**.

## Relationship to autish

**A is a derivative of [autish](https://github.com/Ron-RONZZ-org/autish/)** — a ground-up rewrite with better architecture. When in doubt:

1. Consult [autish](https://github.com/Ron-RONZZ-org/autish/) for reference patterns
2. Read autish source code for implementation examples
3. Learn from autish mistakes — do better

## Hierarchical Context Model

Agents **must** follow this rule:

> When working inside a directory, load the nearest `AGENTS.md` file and merge it with the root `AGENTS.md`.  
> Local rules override global rules.

Context resolution order (highest priority first):
1. `AGENTS-[module].md` in module-specific directories
2. `AGENTS.md` in current working directory (if present)
3. Root `AGENTS.md` — global rules

---

## Project Overview

**A** (A-core) is a minimal, modular CLI framework designed for neurodiverse users. It provides:

- Clean layer architecture (CLI → Service → Data → Core)
- Plugin-based system via Python entry points
- Esperanto-native UI with multilingual support (eo/en/fr)
- Minimal, calm output (no spinners, no animations)
- SQLite data layer with WAL mode

**Key principles:**
1. Don't build what exists — integrate existing tools
2. No custom TUIs — use `$EDITOR`, `fzf`, pipe to existing CLI tools
3. Layered architecture — strict dependency direction
4. Esperanto-first — but graceful English fallback

---

## Architecture

```
src/A/
├── cli.py           # Main entry, plugin discovery
├── core/           # Zero dependencies
│   ├── types.py
│   ├── paths.py
│   ├── i18n.py
│   ├── config.py
│   └── exceptions.py
├── data/           # Depends on core
│   └── base.py
└── utils/         # Depends on nothing
    ├── output.py
    ├── subprocess.py
    └── editor.py
```

**Dependency rule:** CLI → Service → Data → Core. No reverse dependencies.

---

## Language and Naming Conventions

- **CLI command names in Esperanto.**
  Examples: `tempo`, `list`, `help`.
- **Python source code uses English `snake_case`.**
- **Help text in Esperanto by default.**
  Fall back to English, then French.
- **User-facing output: calm, minimal.**
  No bold, no highlights, no animations by default.

---

## Code Standards

1. **No bare `print()`** — use `A.utils.output` functions
2. **Type hints on all public functions**
3. **Errors to stderr** — use `error()` from utils
4. **No custom TUI code** — integrate existing tools
5. **WAL mode** for SQLite
6. **Test coverage required** for all modules

---

## Documentation Standards (IMPORTANT)

This project **must** have better documentation than autish:

1. **Every public function needs a docstring** with:
   - What it does
   - Args and return type
   - Example usage

2. **README.md must have:**
   - Installation instructions
   - Quick start guide
   - Plugin development guide
   - Example plugin

3. **Contributing guide** explaining:
   - How to add a plugin
   - How to run tests
   - Code style

4. **API documentation** (for developers):
   - Layer responsibilities
   - Plugin contract
   - Migration guide from autish

**Unlike autish, documentation is a first-class concern.**

---

## Plugin System

Plugins register via Python entry points:

```toml
[project.entry-points."A.commands"]
tempo = "A_tempo.cli:app"
sistemo = "A_sistemo.cli:app"
```

A plugin **must** export a `typer.Typer` instance as `app`.

---

## Example Plugins

Reference implementations for plugin developers:

| Plugin | Repository | Description |
|--------|------------|-------------|
| A-tempo | [A-tempo](https://github.com/Ron-RONZZ-org/A-tempo/) | Time/clock - simplest plugin |
| A-sistemo | [A-sistemo](https://github.com/Ron-RONZZ-org/A-sistemo/) | System management |
| A-vorto | [A-vorto](https://github.com/Ron-RONZZ-org/A-vorto/) | Wordbook - SQLite CRUD |
| A-encik | [A-encik](https://github.com/Ron-RONZZ-org/A-encik/) | Knowledge + Wikidata |
| A-organizi | [A-organizi](https://github.com/Ron-RONZZ-org/A-organizi/) | Calendar+todo+journal |
| A-lien | [A-lien](https://github.com/Ron-RONZZ-org/A-lien/) | Email+contacts |
| A-medio | [A-medio](https://github.com/Ron-RONZZ-org/A-medio/) | Video+photo+audio |

**Use these as reference** when building new plugins.

---

## Testing

```bash
poetry run pytest tests/
```

All new code must include tests.

---

## What to Avoid

- Don't use `click` — use Typer
- Don't add GUI/TUI widgets
- Don't hardcode paths — use `A.core.paths`
- Don't skip documentation
- Don't reinvent — integrate existing tools

---

## Shell Integrations

Some features are better handled as shell aliases rather than plugins. See issue [#3](https://github.com/Ron-RONZZ-org/A-core/issues/3) for rationale.

**kp (clipboard):** Use `xclip`, `xsel`, `pbcopy` directly instead of creating a 60-line wrapper plugin.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:`, `fix:`, `docs:`, `test:`, `refactor:`

---

## API Reference

This section documents all public APIs in A-core. Plugins import from `A.core`.

### Core Module (`from A.core import ...`)

```python
from A.core import (
    # Types
    CommandResult, PluginInfo, Config,
    # Paths
    data_dir, config_dir, cache_dir, state_dir, ensure_dirs,
    # i18n
    tr, set_language, available_languages, get_current_language,
    # Exceptions
    AError, ConfigError, PluginError, DataError, CommandError,
    # Config
    load_config, save_config, get_setting, set_setting,
    load_profile, save_profile, export_profile, import_profile,
)
```

### Types (`A.core.types`)

| Class | Description | Fields |
|-------|-------------|--------|
| `CommandResult` | Result from command execution | `success: bool`, `message: str`, `data: dict` |
| `PluginInfo` | Registered plugin info | `name: str`, `version: str`, `description: str`, `cli: object` |
| `Config` | User configuration | `language: str`, `verbose: bool`, `plugins: list`, `aliases: dict`, `settings: dict` |

### Paths (`A.core.paths`)

| Function | Returns | Description |
|----------|---------|-------------|
| `data_dir() -> Path` | `~/.local/share/A` | User data directory |
| `config_dir() -> Path` | `~/.config/A` | User config directory |
| `cache_dir() -> Path` | `~/.cache/A` | User cache directory |
| `state_dir() -> Path` | `~/.local/state/A` | User state directory |
$1

**`ensure_dirs` usage:**
```python
from A.core.paths import ensure_dirs, data_dir

# Create all A directories (data, config, cache, state)
ensure_dirs()

# Create a specific directory (e.g., plugin data dir)
my_data_dir = data_dir() / "my_plugin"
ensure_dirs(my_data_dir)
```

### i18n (`A.core.i18n`)

| Function | Returns | Description |
|----------|---------|-------------|
| `tr(key: str, lang: str = None) -> str` | Translated string | Translate key (falls back to English) |
| `tr_multi(eo: str, en: str = None, fr: str = None) -> str` | Translated string | Inline translation for current language |
| `set_language(lang: str) -> None` | — | Set current language |
| `available_languages() -> list[str]` | `["eo", "en", "fr"]` | Get supported languages |
| `get_current_language() -> str` | Language code | Get current language |

Supported languages: `eo` (Esperanto), `en` (English), `fr` (French)

**Usage:**
```python
from A import tr, tr_multi

# Dictionary lookup (existing behavior)
help_text = tr("help")  # Returns "Helpo" in eo, "Help" in en

# Inline translation (new - for plugin help text)
app = typer.Typer(
    help=tr_multi(
        "Encik — persona sci-mastruma mikroapo.",           # eo
        "Encik — personal knowledge management microapp.",   # en
        "Encik — microapplication de gestion de connaissances." # fr
    )
)
```

### Exceptions (`A.core.exceptions`)

| Exception | Base | Description |
|-----------|-----|-------------|
| `AError` | `Exception` | Base exception |
| `ConfigError` | `AError` | Configuration errors |
| `PluginError` | `AError` | Plugin loading errors |
| `DataError` | `AError` | Database errors |
| `CommandError` | `AError` | Command execution errors |

### Config (`A.core.config`)

| Function | Returns | Description |
|----------|---------|-------------|
| `load_config() -> Config` | Config object | Load from `~/.config/A/config.toml` |
| `save_config(config: Config) -> None` | — | Save to config.toml |
| `get_setting(key: str, default: Any = None) -> Any` | Setting value | Get user setting |
| `set_setting(key: str, value: Any) -> None` | — | Set user setting |
| `load_profile() -> dict` | Profile dict | Load full profile |
| `save_profile(data: dict) -> None` | — | Save full profile |
| `export_profile(path: Path) -> None` | — | Export to JSON file |
| `import_profile(path: Path) -> None` | — | Import from JSON file |

### Data Layer (`A.data`)

```python
from A.data import SQLiteDB
from pathlib import Path

# Basic usage with name (creates ~/.local/share/A/mydb.db)
db = SQLiteDB("mydb")
db.execute("SELECT * FROM table")        # -> list[dict]
db.execute_one("SELECT * FROM table")   # -> dict | None
db.transaction()                          # context manager

# With full Path (for plugins that define custom paths)
db = SQLiteDB(Path.home() / ".local" / "share" / "A" / "encik.db")

# With schema (tables created automatically if not exist)
schema = {
    "words": "CREATE TABLE words (id INTEGER PRIMARY KEY, text TEXT)"
}
db = SQLiteDB("vorto", schema)
```

**SQLiteDB Constructor:**
- `name_or_path: str | Path` - Database name (e.g., "tempo") or full Path
- `schema: dict[str, str]` - Optional dict of table_name → CREATE TABLE SQL

**Methods:**
- `execute(sql, params) -> list[dict]` - Execute SQL, return all rows
- `execute_one(sql, params) -> dict | None` - Execute SQL, return first row
- `execute_many(sql, params_list) -> None` - Execute SQL with multiple param sets
- `transaction()` - Context manager for auto-commit transactions

**Features:**
- WAL mode enabled by default
- Foreign keys enabled
- Returns rows as dicts (sqlite3.Row factory)
- Schema applied idempotently (only creates tables that don't exist)

### Service Layer (`A.core.service`)

| Class/Function | Description |
|---------------|-------------|
| `CRUDService` | CRUD with soft-delete, undo |
| `create_service(name, table)` | Factory function |

### CRUDService Methods

| Method | Description |
|-------|-------------|
| `list(order_by, desc, limit)` | List entries |
| `get(uuid)` | Get by UUID |
| `get_by_field(field, value)` | Get by field |
| `search(field, query)` | Search |
| `create(data)` | Create with auto uuid/timestamp + undo tracking |
| `update(uuid, data)` | Update with timestamp + undo tracking |
| `delete(uuid, soft)` | Delete (soft/permanent) + undo tracking |
| `restore(uuid)` | Restore from trash |
| `empty_trash(days)` | Cleanup trash |
| `undo()` | Undo last operation (returns operation details or None) |
| `clear_undo_stack()` | Clear undo stack |

```python
# Example with undo
from A.core.service import CRUDService
from A.data import SQLiteDB

db = SQLiteDB("vorto")
words = CRUDService(db, "vorto", undo_size=10)  # Enable undo with max 10 operations

words.create({"teksto": "hello"})
words.list()
result = words.undo()  # Returns {"operation_type": "add", "record_uuid": "...", ...}
words.delete(uuid, soft=True)
words.restore(uuid)
```

### Undo System (`A.core.undo`)

| Class/Function | Description |
|---------------|-------------|
| `UndoManager` | In-memory undo stack with configurable size |
| `UndoOperation` | Dataclass representing a trackable operation |
| `create_undo_operation()` | Convenience factory function |

**UndoOperation fields:**
- `operation_type: Literal["add", "modify", "delete"]`
- `table: str`
- `record_uuid: str`
- `old_data: dict | None` — previous state (for modify/delete)
- `new_data: dict | None` — new state (for add/modify)
- `timestamp: datetime`

**UndoManager features:**
- O(1) push/undo operations via `collections.deque(maxlen=N)`
- Optional database persistence for crash recovery
- Integrates with CRUDService automatically

```python
# Standalone usage
from A.core.undo import UndoManager, create_undo_operation

manager = UndoManager(max_size=10)
manager.push(create_undo_operation(
    operation_type="add",
    table="vorto",
    record_uuid="abc-123",
    new_data={"teksto": "hello"},
))
op = manager.undo()  # Returns UndoOperation or None
```

### Crypto (`A.core.crypto`)

| Function | Returns | Description |
|----------|---------|-------------|
| `encrypt(plaintext: bytes, password: str, salt: bytes = None) -> bytes` | Encrypted data | AES-256-GCM encryption |
| `decrypt(encrypted_data: bytes, password: str) -> bytes` | Original plaintext | Decrypt AES-256-GCM |
| `encrypt_str(plaintext: str, password: str) -> bytes` | Encrypted bytes | Encrypt string |
| `decrypt_str(encrypted_data: bytes, password: str) -> str` | Original string | Decrypt to string |
| `is_encrypted(data: bytes) -> bool` | True if encrypted | Check encryption |
| `derive_key(password: str, salt: bytes) -> bytes` | 256-bit key | PBKDF2 key derivation |
| `generate_salt() -> bytes` | 16-byte salt | Random salt |
| `generate_nonce() -> bytes` | 12-byte nonce | Random nonce |
| `encrypt_file(input_path: str, output_path: str, password: str) -> None` | — | Encrypt file |
| `decrypt_file(input_path: str, output_path: str, password: str) -> None` | — | Decrypt file |

**Encryption uses:**
- AES-256-GCM (authenticated encryption)
- PBKDF2-HMAC-SHA256 with 600,000 iterations
- Random salt (16 bytes) + nonce (12 bytes) per encryption

```python
from A.core.crypto import encrypt, decrypt, encrypt_str, decrypt_str

# Encrypt string (convenience)
encrypted = encrypt_str("secret data", "password")
decrypted = decrypt_str(encrypted, "password")

# Encrypt bytes
plaintext = b"binary data"
encrypted = encrypt(plaintext, "password")
decrypted = decrypt(encrypted, "password")
```

### Export (`A.core.export`)

| Function | Description |
|----------|-------------|
| `export_json(data: list[dict], output_path: Path, encryption_password: str = None)` | Export to JSON |
| `export_toml(data: dict, output_path: Path, encryption_password: str = None)` | Export to TOML |
| `export_json_stream(generator, output_path: Path, encryption_password: str = None)` | Stream JSON export |
| `export_toml_stream(generator, output_dir: Path, encryption_password: str = None)` | Stream to TOML files |
| `is_encrypted_file(path: Path) -> bool` | Check if file encrypted |
| `detect_format(path: Path) -> str` | Detect format (json/toml/encrypted) |

**Export format:**
- JSON: Full export all records as array
- TOML: Single record export
- Streaming: Generator pattern for large datasets

```python
from A.core.export import export_json, export_json_stream, export_toml
from pathlib import Path

# Full export
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
export_json(data, Path("export.json"))

# Encrypted export
export_json(data, Path("export.enc"), encryption_password="my-password")

# Streaming export
def record_generator():
    for i in range(10000):
        yield {"id": i, "value": f"item-{i}"}

export_json_stream(record_generator(), Path("large.json"))
```

### Import (`A.core.import_`)

| Function | Description |
|----------|-------------|
| `import_json(path: Path, decryption_password: str = None) -> list[dict]` | Import JSON |
| `import_toml(path: Path, decryption_password: str = None) -> dict` | Import TOML |
| `import_auto(path: Path, decryption_password: str = None) -> list[dict] | dict` | Auto-detect format |
| `import_stream(path: Path, decryption_password: str = None) -> Generator[dict]` | Stream import |

```python
from A.core.import_ import import_json, import_auto, import_stream

# Import JSON
records = import_json(Path("export.json"))

# Import encrypted
records = import_json(Path("export.enc"), decryption_password="my-password")

# Auto-detect format
data = import_auto(Path("data.json"))  # or .toml, or encrypted

# Streaming import
for record in import_stream(Path("data.json")):
    process(record)
```

### Plugin Contract

Plugins must register via entry points:

```toml
[project.entry-points."A.commands"]
myplugin = "A_myplugin.cli:app"
```

Requirements:
- Export `app: typer.Typer` from `A_myplugin.cli`
- Use `A.core.i18n.tr()` for all user-facing strings
- Use `A.core.exceptions` for errors
- Use XDG paths from `A.core.paths`

### Example Plugin Structure

```
A_myplugin/
├── src/
│   └── A_myplugin/
│       ├── __init__.py
��       ├── cli.py          # exports: app
│       ├── service.py     # Business logic
│       └── data.py        # SQLite operations
├── tests/
├── pyproject.toml         # Entry point registration
└── AGENTS.md
```