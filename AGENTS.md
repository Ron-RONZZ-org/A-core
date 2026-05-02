# AGENTS.md — Root Project Rules for A-core

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

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:`, `fix:`, `docs:`, `test:`, `refactor:`