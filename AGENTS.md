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
├── cli.py           # Main entry, plugin discovery, modulo sub-app
├── core/           # Zero dependencies
│   ├── types.py
│   ├── paths.py
│   ├── i18n.py
│   ├── config.py
│   ├── exceptions.py
│   └── registry.py  # Module manifest fetch, cache, search
├── data/           # Depends on core
│   └── base.py
├── utils/         # Depends on nothing
│   ├── output.py
│   ├── subprocess.py
│   ├── editor.py
│   └── interactive.py  # Generic selection utility
├── modules.json    # Module registry manifest (hosted on GitHub)
└── tests/
    ├── test_registry.py
    ├── test_interactive.py
    └── test_cli.py
```

**Dependency rule:** CLI → Service → Data → Core. No reverse dependencies.

---

## Language and Naming Conventions

- **CLI command names in Esperanto.** See [CLI Command Standard](#cli-command-standard) below.
- **Python source code uses English `snake_case`.**
- **Help text MUST use `tr_multi()` for i18n.**
  - Use: `help=tr_multi("Maksimumaj rezultoj", "Max results", "Résultats max")`
  - NEVER use: `help="Max results"` (English only)
  - Rule: Always provide Esperanto as first argument, English second, French third
- **User-facing output: calm, minimal.**
  No bold, no highlights, no animations by default.

### i18n Quick Reference

| Situation | Solution |
|-----------|----------|
| CLI option help text | `tr_multi("eo", "en", "fr")` |
| Static UI strings (button labels) | `tr("key")` from dict |
| Dynamic/runtime strings | `tr_multi(eo, en, fr)` inline |
| Docstrings (internal) | English (not user-facing) |

### CLI Command Standard

All A-modules **must** follow this standard for CLI commands. Consistent naming reduces user confusion and enables cross-module tooling.

#### Standard Commands

| Command | Purpose | Required? | Notes |
|---------|---------|-----------|-------|
| `-h` / `--help` / `--helpo` | Help | **Required** | Configured via `context_settings={"help_option_names": ["-h", "--help", "--helpo"]}`. Do NOT add a bare `helpi` command. |
| `ls` | List items | **Required** for data modules | Alias `list` → `ls` with deprecation where `list` exists. |
| `vidi` | View single item detail | **Required** for data modules | Universal "show entry" command. |
| `aldoni` | Add/create item | **Required** for CRUD modules | |
| `modifi` | Update/modify item | **Required** for CRUD modules | |
| `forigi` | Delete item(s) | **Required** for CRUD modules | Accept multiple positional args for bulk delete. |
| `serci` | Search items | **Required** for data modules | Use ASCII `c` (NOT `serĉi` with diacritic). `serchi` may be kept as deprecated alias. |
| `importi` | Import data | Recommended | |
| `eksporti` | Export data | Recommended | |
| `rubujo` | Trash operations (as subcommand group) | For modules with soft-delete | See "Trash Commands" below. |
| `malfari` | Undo last operation | Optional | Only if module supports undo (A-core `UndoManager`). |

#### Trash Commands (subcommand group style)

Trash operations **must** be grouped under the `rubujo` subcommand, NOT as top-level commands:

| Command | Purpose |
|---------|---------|
| `rubujo ls` | List trashed items |
| `rubujo restaŭrigi` | Restore item from trash (accept `restauxrigi` as alias for keyboard portability) |
| `rubujo malplenigi` | Empty trash (delete older than N days) |
| `rubujo forigi` | Permanently delete specific item from trash |

Implementation pattern (Typer):
```python
trash_app = typer.Typer()
app.add_typer(trash_app, name="rubujo", help=tr_multi(...))
```

#### Naming Rules

1. **Esperanto names** — all command names in Esperanto
2. **ASCII only** — avoid diacritics (`ĉ`, `ĝ`, `ĥ`, `ĵ`, `ŝ`, `ŭ`) in command names. Use plain ASCII equivalents:
   - `serci` not `serĉi`
   - `restauxrigi` (x-convention) or `restaŭrigi` (if ŭ is acceptable in the locale)
3. **Do NOT use bare `help`/`helpi` commands** — Typer's `--helpo` flag is sufficient
4. **Domain-specific commands** (e.g., `konekti`, `restarti`, `generi`) are allowed but should be minimized
5. **Hidden aliases** — deprecated commands should be registered with `@app.command(hidden=True)` or `deprecated=True`

#### Migration Path

Modules migrating from non-standard names:
- Keep old names as hidden/deprecated aliases for one release cycle
- Example: `@app.command("list", hidden=True)` alongside `@app.command("ls")`

---

## Code Standards

1. **No bare `print()`** — use `A.utils.output` functions
2. **Type hints on all public functions**
3. **Errors to stderr** — use `error()` from utils
4. **No custom TUI code** — integrate existing tools
5. **WAL mode** for SQLite
6. **Test coverage required** for all modules

## Package Manager: `uv` is Required

All A-ecosystem development **must** use `uv` as the package manager.

| Operation | Command |
|-----------|---------|
| Install dependencies | `uv pip install <pkg>` |
| Install project in dev mode | `uv pip install -e .` |
| Run tests | `uv run pytest tests/` |
| Install CLI tools | `uv tool install <tool>` |
| Add dev dependency | `uv add --dev <pkg>` |

**Exceptions:**
- `pip` in README install instructions is acceptable for end users who may not have `uv`
- Readthedocs platform build may require `pip` (platform constraint)
- Runtime `install-on-confirmation` code may fall back to `pip` if `uv` is unavailable (see Optional Dependency Policy below)

## Optional Dependency Policy

When a command requires an optional dependency that is not installed:

1. **Ask user**: "The 'X' library is required. Install it now?"
2. **Default to yes**: `typer.confirm(..., default=True)`
3. **Install on confirmation**: Use venv-aware fallback chain:
   - First try: `uv pip` (uv-managed venvs preserve isolation)
   - Second try: `pip` in PATH
   - Third try: `python3 -m pip`
   - Last resort: `sys.executable -m pip` (may break isolation)
4. **Exit gracefully** if user declines or install fails

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
| `RegistryError` | `AError` | Module registry fetch/parse errors |

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

### Keyring (`A.core.keyring`)

| Function | Returns | Description |
|----------|---------|-------------|
| `get_password(service, key)` | `str \| None` | Retrieve password from system keyring |
| `set_password(service, key, password)` | `bool` | Store password in system keyring |
| `delete_password(service, key)` | `bool` | Remove password from system keyring |

**Service pattern:** Use ``"app_name/identifier"`` as service name, ``"password"`` as key.

```python
from A.core.keyring import get_password, set_password, delete_password

# Store
set_password("A-lien/abc-123", "password", "sekret123")

# Retrieve
pw = get_password("A-lien/abc-123", "password")

# Delete
delete_password("A-lien/abc-123", "password")
```

**Graceful fallback:** All functions return ``None``/``False`` when the ``keyring`` library is not installed. Handle this in application code:

```python
from A.core.keyring import get_password

if pw := get_password("myapp/db", "password"):
    # use the password
else:
    # keyring unavailable — prompt user or use alternative
```

Install the optional dependency with:

```bash
pip install A-core[keyring]
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

### Markdown (`A.core.markdown_parser`)

| Function | Description |
|----------|-------------|
| `render_markdown(text: str, escape: bool = True) -> str` | Render markdown to HTML |
| `get_parser() -> mistune.Markdown` | Get configured parser |

**Syntax highlighting:** Uses Pygments for code blocks:

```python
from A.core.markdown_parser import render_markdown

# Basic rendering
html = render_markdown("# Hello\n\nWorld")

# With syntax highlighting (escape=False for trusted content)
md = "```python\nx = 1\n```"
html = render_markdown(md, escape=False)
```

### Markdown HTML Preview (`A.core.markdown_html_view`)

| Function | Description |
|----------|-------------|
| `preview_markdown(text, use_cache, open_browser, title) -> Path` | Render and open in browser |
| `preview_html(html, open_browser, title) -> Path` | Open HTML directly |
| `KATEX_HTML() -> str` | Get KaTeX HTML snippet (inline local or CDN) |
| `ensure_katex() -> bool` | Pre-download KaTeX assets for offline use |
| `clear_cache() -> int` | Clear cached HTML files and KaTeX downloads |
| `get_cache_dir() -> Path` | Get cache directory |

```python
from A.core.markdown_html_view import preview_markdown, preview_html, KATEX_HTML, ensure_katex

# Render markdown and open in browser
path = preview_markdown("# Notes\n\nContent here", open_browser=True)

# Or open raw HTML
path = preview_html("<h1>Custom</h1>", open_browser=True)

# Get KaTeX snippet for embedding in custom HTML
katex_snippet = KATEX_HTML()  # callable, not a constant
```

**Features:**
- File-based caching (lazy render)
- Opens in default browser via `webbrowser.open()`
- Cache in `~/.cache/A/markdown/`
- Offline KaTeX: assets downloaded on first use, inlined into HTML
- Falls back to CDN if download fails
- Also caches in `~/.cache/A/katex/`
- Cache cleared via `clear_cache()`

### Links (`A.core.links`)

Bidirectional links for cross-module references. Stores links as adjacency list with O(1) lookups.

| Class/Function | Returns | Description |
|---------------|---------|-------------|
| `Link` | dataclass | Represents a directed link |
| `LinksDB` | class | Database for managing links |
| `get_links_db() -> LinksDB` | LinksDB | Get singleton instance |
| `add_link(source_type, source_id, target_type, target_id) -> Link` | Link | Add bidirectional link |
| `remove_link(...) -> bool` | bool | Remove a link |
| `get_outgoing(source_type, source_id) -> list[Link]` | list | Get outgoing links |
| `get_incoming(target_type, target_id) -> list[Link]` | list | Get incoming links (backlinks) |
| `get_links(entry_type, entry_id) -> dict` | dict | Get both outgoing and incoming |
| `link_exists(...) -> bool` | bool | Check if link exists |
| `remove_all_for_entry(...) -> int` | int | Remove all links for an entry |
| `get_linked_entries(...) -> dict` | dict | Get all linked entry IDs grouped by type |

**Schema:** Links stored in dedicated table with indexes on source and target.

```python
from A.core.links import add_link, get_outgoing, get_incoming

# Add link from vorto entry to encik entry
add_link("vorto", "uuid-123", "encik", "uuid-456")

# Get outgoing links from vorto entry
outgoing = get_outgoing("vorto", "uuid-123")

# Get incoming links (backlinks) to encik entry
incoming = get_incoming("encik", "uuid-456")
```

### References (`A.core.references`)

Parse and resolve vt#uuid and ec#uuid references in text. Supports markdown links and plain references.

| Class/Function | Returns | Description |
|---------------|---------|-------------|
| `Ref` | dataclass | Parsed reference |
| `ResolvedRef` | dataclass | Reference with resolved entry data |
| `parse_refs(text: str) -> list[Ref]` | list | Extract all references from text |
| `resolve(ref_type, uuid) -> ResolvedRef` | ResolvedRef | Resolve reference to entry data |
| `get_ref_display(ref_type, uuid, show_uuid) -> str` | str | Human-readable display string |
| `clear_ref_cache() -> None` | — | Clear resolution cache |
| `is_valid_ref(ref: str) -> bool` | bool | Check if string is valid reference |
| `normalize_ref(ref: str) -> str` | str | Normalize to canonical form |

**Reference formats:**
- Markdown: `[label](vt#uuid)` or `[label](ec#uuid)`
- Plain: `vt#uuid` or `ec#uuid`

**Runtime detection:** Resolves references using A-vorto or A-encik if available. Gracefully degrades if modules not installed.

```python
from A.core.references import parse_refs, resolve, get_ref_display

# Parse references from text
text = "See [this word](vt#12345678) and ec#abcdef01"
refs = parse_refs(text)
# Returns: [Ref(ref_type='vt', uuid='12345678', label='this word', is_markdown=True), ...]

# Resolve to entry data
resolved = resolve("vt", "12345678")
# Returns: ResolvedRef with exists=True if found

# Get display string
display = get_ref_display("vt", "12345678", show_uuid=True)
# Returns: "word (vt#1234567)"
```

### Migration (`A.core.migration`)

Migration from autish (legacy) to A-* modules. Tracks state for idempotent runs.

| Class/Function | Returns | Description |
|----------------|---------|-------------|
| `MigrationResult` | dataclass | Result from a single migration |
| `MigrationStatus` | dataclass | Overall migration status for a module |
| `get_status() -> dict` | dict | Get status for all modules |
| `migrate_all(dry_run=False) -> dict` | dict | Run all pending migrations |
| `register_migration(...)` | — | Register a module migration |
| `migrate_keyring_passwords(...) -> int` | int | Migrate keyring passwords |

**CLI commands:**
```bash
A migri              # Run all pending migrations
A migri --status     # Show migration status for all modules
A migri --list       # List available migrations (alias for --status)
A migri-keyring      # Migrate keyring passwords
```

**Programmatic usage:**
```python
from A.core.migration import get_status, migrate_all, MigrationResult

# Check status
status = get_status()
for module, st in status.items():
    if st.available and not st.migrated:
        print(f"{module}: {st.source_rows} rows to migrate")

# Run migrations
results = migrate_all()
for module, result in results.items():
    print(f"{module}: {result.migrated_rows}/{result.source_rows} migrated")
```

**Migration state:** Stored in `~/.local/share/A/migration_state.json`

### Module Registry (`A.core.registry`)

Discovers available A-modules via a curated manifest (`modules.json`) hosted on GitHub.
Fetches and caches the manifest for offline use.

| Function | Returns | Description |
|----------|---------|-------------|
| `fetch_registry(*, refresh=False) -> dict \| None` | Manifest dict | Fetch manifest (cache-first), returns None if unreachable |
| `search_registry(query: str) -> list[dict]` | Matching modules | Case-insensitive search by name/description |
| `get_module_info(name: str) -> dict \| None` | Module entry | Get single module by name (case-insensitive) |
| `get_installed_modules() -> list[dict]` | Installed modules | Discover via `A.commands` entry points |

**Config options:**
- `module_registry_url` (config key) — custom registry URL
- `A_MODULE_REGISTRY_URL` (env var) — overrides config
- `module_cache_ttl` (config key, default 86400s) — cache TTL

**Example:**
```python
from A import fetch_registry, search_registry

# Fetch all modules
data = fetch_registry()
for m in data["modules"]:
    print(m["name"], m["display_name"])

# Search
results = search_registry("kalendaro")
for m in results:
    print(m["name"], m["description"][:60])
```

### Interactive Selection (`A.utils.interactive`)

Generic "show numbered table → prompt for selection" pattern extracted from A-encik.
Reusable across all A-modules.

| Function | Returns | Description |
|----------|---------|-------------|
| `select_candidate(candidates, *, columns, row_formatter, ...) -> tuple[int, T] \| None` | Selected item | Display numbered table, prompt user to select |
| `confirm_action(message, *, default=False) -> bool` | Confirmation | Yes/no prompt |

**`select_candidate` parameters:**
- `candidates: list[T]` — items to display
- `columns: list[dict]` — Rich Table column defs (`header`, `style`, `width`)
- `row_formatter: Callable[[T, int], list[str]]` — `(item, 1-based-index) → cell values`
- `prompt_text: str` — custom prompt (default: translated message)
- `default: str` — default input (default: `""` = skip)

**Example:**
```python
from A.utils.interactive import select_candidate

result = select_candidate(
    modules,
    columns=[
        {"header": "Nomo", "style": "bold"},
        {"header": "Priskribo", "style": "dim"},
    ],
    row_formatter=lambda m, i: [m["name"], m["description"][:50]],
)
if result is not None:
    idx, module = result
    print(f"Selected: {module['name']}")
```

### CLI Modulo Commands

```bash
A modulo ls                # List all available modules (installed marked)
A modulo ls --instalita   # List only installed modules
A modulo serci <keyword>  # Search modules by name/description
A modulo info <name>      # Show module details with install instructions
```

The old `A list` is deprecated and delegates to `A modulo ls --instalita`.

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

## Branch Convention

All A-* repos use `main` as the primary branch. Use `main` for all development.