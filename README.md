# A-core

A - minimuma CLI kadro / A - minimal CLI framework

Esperanto-native CLI framework with plugin support.

## Features

- Esperanto as primary language (eo, en, fr)
- Plugin discovery via entry points
- SQLite data layer with WAL mode
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
├── core/       # Zero dependencies (types, paths, i18n, config)
├── data/      # SQLite base classes
└── utils/     # Output, subprocess, editor helpers
```

**Plugin dependencies on A-core:**
- `A` package imports (i18n, output, subprocess)
- Entry point registration
- Shared SQLite utilities with WAL mode

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
| [A-sistemo](https://github.com/Ron-RONZZ-org/A-sistemo/) | System management |

## Developing Plugins

See the documentation for plugin development:
- [English](./docs/en/index.md)
- [Esperanto](./docs/eo/index.md)
- [Français](./docs/fr/index.md)

## Background

A was born from personal need. See [0-WHY-AUTISH.md](./0-WHY-AUTISH.md) for the full story.