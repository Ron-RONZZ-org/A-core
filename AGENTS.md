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
| `create(data)` | Create with auto uuid/timestamp |
| `update(uuid, data)` | Update with timestamp |
| `delete(uuid, soft)` | Delete (soft/permanent) |
| `restore(uuid)` | Restore from trash |
| `empty_trash(days)` | Cleanup trash |
| `push_undo(op, data)` | Undo stack |
| `load_undo_stack()` | Load undo stack |

```python
# Example
from A.core.service import CRUDService
from A.data import SQLiteDB

db = SQLiteDB("vorto")
words = CRUDService(db, "vorto")

words.create({"teksto": "hello"})
words.list()
words.delete(uuid, soft=True)
words.restore(uuid)
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