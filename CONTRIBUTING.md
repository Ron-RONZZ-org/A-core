# Contributing to A

Thank you for considering contributing to A!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Install development dependencies:

```bash
poetry install
```

## Development

```bash
# Run tests
poetry run pytest tests/

# Run type checking
poetry run ruff check src/

# Format code
poetry run ruff format src/
```

## Adding a Plugin

See the documentation for plugin development:
- [English](./docs/en/index.md)
- [Esperanto](./eo/index.md)
- [Français](./fr/index.md)

### Reference Plugins

Seven working plugins you can study:

1. **[A-tempo](https://github.com/Ron-RONZZ-org/A-tempo/)** — Time/clock, simplest plugin
2. **[A-sistemo](https://github.com/Ron-RONZZ-org/A-sistemo/)** — System management (wifi, usb, disko, bluetooth)
3. **[A-vorto](https://github.com/Ron-RONZZ-org/A-vorto/)** — Wordbook with SQLite
4. **[A-encik](https://github.com/Ron-RONZZ-org/A-encik/)** — Knowledge management with Wikidata
5. **[A-organizi](https://github.com/Ron-RONZZ-org/A-organizi/)** — Calendar, todo, journal
6. **[A-lien](https://github.com/Ron-RONZZ-org/A-lien/)** — Email and contacts
7. **[A-medio](https://github.com/Ron-RONZZ-org/A-medio/)** — Video, photo, audio

## Code Style

- Follow PEP 8
- Use `ruff` for formatting
- Type hints required on public functions
- Docstrings required on public functions

## Testing

All new code must include tests. Run the full test suite:

```bash
poetry run pytest tests/ -v
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring

## Submitting

1. Create a branch
2. Make your changes
3. Add tests
4. Push and create a pull request

---

## Kontribuo al A

Dankon pro konsideri kontribui al A!

## Komenco

1. Forĵu la deponejon
2. Klonu vian forkon
3. Instalu dependencojn:

```bash
poetry install
```

## Evoligado

```bash
# Ruli testojn
poetry run pytest tests/

# Ruli tipkontrolon
poetry run ruff check src/
```

## Aldoni Kromprogramon

Vidu dokumentadon supre.

## Coda Stilo

- Sekvu PEP 8
- Uzu `ruff` por formatado
- Tipo indikoj bezonataj
- Docstrings bezonataj

## Testado

Ĉiu nova kodo devas inkluzivi testojn.

## Sendado

Kreu pull request-on.