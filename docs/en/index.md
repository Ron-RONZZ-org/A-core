# A Documentation

Welcome to A — minimuma CLI kadro / minimal CLI framework

## Quick Start

### Installation

```bash
pip install A-core
```

Or from source:

```bash
git clone https://github.com/Ron-RONZZ-org/A-core.git
cd A-core
poetry install
```

### Basic Usage

```bash
A --help          # Show help
A list            # List installed plugins
A help            # Show help
```

### Installing Plugins

```bash
pip install A-tempo      # Time plugin
pip install A-sistemo     # System plugin
pip install A-mail       # Email plugin (when available)
```

Or all plugins:

```bash
pip install A-core[all]
```

---

## Architecture

A has four layers with strict dependency direction:

```
┌─────────────────────────────────────────────┐
│ CLI Layer (commands)                      │
│ Typer commands, argument parsing        │
├─────────────────────────────────────────────┤
│ Service Layer                      │
│ Business logic                   │
├─────────────────────────────────────────────┤
│ Data Layer                     │
│ SQLite repos                   │
├─────────────────────────────────────────────┤
│ Core Layer                    │
│ Config, paths, i18n, types     │
└─────────────────────────────────────────────┘
```

**Rule:** CLI → Service → Data → Core. No reverse dependencies.

---

## Developing Plugins

### Basic Plugin Structure

```python
# A_tempo/src/A_tempo/cli.py
import typer
from A import data_dir, ensure_dirs

app = typer.Typer(name="tempo", help="Time management")

@app.command()
def now():
    """Show current time."""
    from datetime import datetime
    from A.utils import success
    
    ensure_dirs()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success(now)

__all__ = ["app"]
```

### Plugin Registration

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."A.commands"]
tempo = "A_tempo.cli:app"
```

### Data Layer

Use `A.data.SQLiteDB`:

```python
from A.data import SQLiteDB
from A.core.paths import data_dir

class TempoDB(SQLiteDB):
    def __init__(self):
        super().__init__("tempo", {
            "events": """
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
        })
```

---

## Configuration

A looks for config at `~/.config/A/config.toml`:

```toml
[A]
language = "eo"        # Default: Esperanto
verbose = false

[A.aliases]
t = "tempo"
```

---

## Language Support

A supports three languages:

| Code | Language |
|------|----------|
| `eo` | Esperanto (default) |
| `en` | English |
| `fr` | Français |

Change language:

```python
from A.core.i18n import set_language
set_language("en")
```

---

## API Reference

### Core

```python
from A import tr, ensure_dirs
from A.core import data_dir, config_dir, load_config
```

### Data

```python
from A.data import SQLiteDB
```

### Utils

```python
from A.utils import success, error, info, run, edit_text
```

---

## Migration from Autish

A supports migration from autish (legacy) to A-* modules:

```bash
A migri           # Run all pending migrations
A migri-keyring   # Migrate passwords from legacy keyring
```

**What gets migrated:**

| Legacy DB | Target Module | Data |
|----------|------------|------|
| retposto.db | A-lien | contacts |
| vorto.db | A-vorto | words |
| encik.db | A-encik | knowledge entries |
| kalendaro.db | A-organizi | calendar events |
| tasklibro.db | A-organizi | tasks + journal |

**Features:**
- Idempotent — safe to run multiple times
- State tracking in `~/.local/share/A/migration_state.json`
- JSON field conversions (legacy flat → A-* JSON arrays)
- Keyring migration: `autish-retposto-{uuid}` → `A-lien/{uuid}`

| Aspect | autish | A |
|--------|--------|-----|
| Structure | Monolithic | Layered |
| Plugins | None | Entry points |
| Language | Mixed | Esperanto-first |
| TUI | Custom | Integrated tools |
| Config | No formal loader | TOML |

A is a rewrite of [autish](https://github.com/Ron-RONZZ-org/autish/). See above for migration support.

---

## Contributing

Please see CONTRIBUTING.md in the repository root.

---

## License

GPL-3.0-only