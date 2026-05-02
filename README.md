# A-core

## Context

This module uses [A-workspace](https://github.com/Ron-RONZZ-org/A-workspace) as a **git submodule**:


```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/Ron-RONZZ-org/A-core.git
# Or if already cloned:
git submodule update --init --recursive
```

**DO NOT edit workspace/ directly** - see [A-workspace](https://github.com/Ron-RONZZ-org/A-workspace) for master context.


A - minimuma CLI kadro / A - minimal CLI framework

Esperanto-native CLI framework with plugin support.

## Features

- Esperanto as primary language (eo, en, fr)
- Plugin discovery via entry points
- SQLite data layer with WAL mode
- Full-text search via SQLite FTS5
- Text normalization (French ligatures, accents)
- Fuzzy search with rapidfuzz (optional)
- Undo system for operations tracking (add/modify/delete)
- Import/export with AES-256 encryption (optional)
- Minimal, calm output
- Shared utilities (i18n, output, subprocess)

## Install

```bash
pip install A-core
```

## Architecture

A is a plugin-based framework. **A-core** provides the foundation:

```
A-core (this package)
├── core/       # Zero dependencies (types, paths, i18n, config, service)
├── data/      # SQLite base classes, FTS5 search
└── utils/     # Output, subprocess, editor, text normalization
```

**Plugin dependencies on A-core:**
- `A` package imports (i18n, output, subprocess, search)
- Entry point registration
- Shared SQLite utilities with WAL mode
- FTS5 full-text search (optional)

## Search & Normalization

A-core provides built-in full-text search via SQLite FTS5:

```python
from A.core.service import CRUDService
from A.data.search import FTSConfig
from A.utils.normalize import fold_search_text

# Configure FTS5
config = FTSConfig(
    table="words",
    fts_columns=["text"],
    normalize={"text": fold_search_text},
)

# Create service with search
service = CRUDService(db, "words", fts_config=config)
service.search_fts("query")              # Full-text search
service.search_fuzzy("heelo", 0.8)        # Fuzzy matching (rapidfuzz)
service.search_advanced("query", fuzzy=True)  # Combined search
```

**Text normalization** handles French ligatures:
- `œ` → `oe`, `Œ` → `OE`
- `æ` → `ae`, `Æ` → `AE`
- Accent stripping via NFKD

**Install with fuzzy search:**
```bash
pip install A-core[search]  # Adds rapidfuzz for fast fuzzy matching
```

## Undo System

A-core provides a built-in undo system for tracking operations:

```python
from A.core.service import CRUDService
from A.data import SQLiteDB

# Enable undo with configurable stack size (default: 10)
service = CRUDService(db, "words", undo_size=10)

# Operations are automatically tracked
service.create({"teksto": "hello"})  # Tracks add
service.update(uuid, {"teksto": "world"})  # Tracks modify
service.delete(uuid, soft=True)  # Tracks delete

# Undo last operation
result = service.undo()
# Returns: {"operation_type": "delete", "table": "words", "record_uuid": "...", ...}
```

**Features:**
- O(1) undo operations via `collections.deque(maxlen=N)`
- Configurable stack size (default 10, set to 0 to disable)
- Automatic tracking of create/update/delete operations
- Timestamps for each operation
- Optional DB persistence for crash recovery

## Import/Export

A-core provides import/export with optional AES-256 encryption:

```python
from A.core import export_json, import_json, encrypt, decrypt

# Export to JSON
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
export_json(data, Path("export.json"))

# Encrypted export
export_json(data, Path("export.enc"), encryption_password="secret")

# Import
records = import_json(Path("export.json"))

# Auto-detect format and decrypt
records = import_json(Path("export.enc"), decryption_password="secret")
```

**Encryption:**
- AES-256-GCM (authenticated encryption)
- PBKDF2-HMAC-SHA256 key derivation (600k iterations)
- Random salt + nonce per encryption

**Streaming:** For large datasets, use generators:

```python
from A.core.export import export_json_stream

def record_generator():
    for i in range(100000):
        yield {"id": i, "data": f"item-{i}"}

export_json_stream(record_generator(), Path("large.json"))
```

**Install with encryption:**
```bash
pip install A-core  # Includes cryptography
```

## Usage

```bash
A list          # List plugins
A help         # Show help
```

## Plugins

Install plugins with pip:

```bash
pip install A[tempo]        # Time/clock plugin
pip install A-sistemo       # System management
```

### Available Plugins

| Plugin | Description |
|--------|-------------|
| [A-tempo](https://github.com/Ron-RONZZ-org/A-tempo/) | Time and clock |
| [A-sistemo](https://github.com/Ron-RONZZ-org/A-sistemo/) | System management (wifi, usb, disko, bluetooth) |
| [A-vorto](https://github.com/Ron-RONZZ-org/A-vorto/) | Wordbook / vocabulary |
| [A-encik](https://github.com/Ron-RONZZ-org/A-encik/) | Knowledge management |
| [A-organizi](https://github.com/Ron-RONZZ-org/A-organizi/) | Calendar, todo, journal |
| [A-lien](https://github.com/Ron-RONZZ-org/A-lien/) | Email and contacts |
| [A-medio](https://github.com/Ron-RONZZ-org/A-medio/) | Video, photo, audio |

## Shell Integrations

Some features are better handled as shell aliases rather than plugins:

### kp (clipboard)

Instead of a plugin, use your terminal's clipboard tools directly:

| OS | Command |
|---|---------|
| Linux (xclip) | `xclip -selection clipboard` |
| Linux (xsel) | `xsel --clipboard --input` |
| macOS | `pbcopy` |
| Windows | `clip` |

**Add to shell config:**

```bash
# ~/.bashrc or ~/.zshrc
alias kp='xclip -selection clipboard'  # Linux
# or
alias kp='xsel --clipboard --input'     # Linux alternative
alias kp='pbcopy'                     # macOS
alias kp='clip'                       # Windows
```

**Usage:**

```bash
A sistemo info | kp    # Copy output to clipboard
```

This avoids a 60-line wrapper for a single shell command.

## Developing Plugins

See the documentation for plugin development:
- [English](./docs/en/index.md)
- [Esperanto](./docs/eo/index.md)
- [Français](./docs/fr/index.md)

## Background

A was born from personal need. See [0-WHY-AUTISH.md](./0-WHY-AUTISH.md) for the full story.