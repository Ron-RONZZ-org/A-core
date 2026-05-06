"""A CLI main entry point."""

from typing import Callable

import typer
from rich.table import Table
from rich.panel import Panel

from A import tr, tr_multi
from A.core.paths import ensure_dirs
from A.core.migration import get_status, migrate_all, MigrationStatus
from A.core.registry import fetch_registry, get_module_info, get_installed_modules, search_registry
from A.core.markdown_parser import render_markdown
from A.core.plugin_loader import (
    _PLUGIN_ENTRY_POINTS,
    discover_plugin_names,
    LazyPluginGroup,
)
from A.utils import info, success, error, warning, console
from A.utils.interactive import select_candidate


# ── Main App ─────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="A",
    cls=LazyPluginGroup,
    help=tr("A - minimuma CLI kadro"),
    no_args_is_help=True,
    pretty_exceptions_short=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
) -> None:
    """A - minimuma CLI kadro."""
    pass


@app.command("list")
def list_cmd() -> None:
    """Listigi instalitajn modulojn (malrekomendita)."""
    warning(tr_multi(
        "`A list` estas malrekomendita. Uzu `A modulo ls --instalita` anstataŭe.",
        "`A list` is deprecated. Use `A modulo ls --instalita` instead.",
        "`A list` est d\u00e9pr\u00e9ci\u00e9. Utilisez `A modulo ls --instalita`.",
    ))
    modulo_ls(instalita=True)


# ── Migration helpers ─────────────────────────────────────────────────────────

_DISCOVERED_MIGRATIONS: dict[str, Callable[[], None]] = {}


def _discover_migrations() -> dict[str, Callable[[], None]]:
    """Discover migrations from A-modules via entry points (cached).

    Looks for entry points in the "A.migrations" group.
    Each entry point should be a callable that registers the migration.
    """
    global _DISCOVERED_MIGRATIONS

    if _DISCOVERED_MIGRATIONS:
        return _DISCOVERED_MIGRATIONS

    migrations: dict[str, Callable[[], None]] = {}
    try:
        eps = importlib.metadata.entry_points(group="A.migrations")
    except TypeError:
        eps = importlib.metadata.entry_points().get("A.migrations", [])

    for ep in eps:
        try:
            migrator = ep.load()
            if callable(migrator):
                migrations[ep.name] = migrator
            else:
                warning(f"invalid migration {ep.name}: not callable")
        except Exception as e:
            warning(f"failed to load migration {ep.name}: {e}")

    _DISCOVERED_MIGRATIONS = migrations
    return migrations


def _register_migrations() -> None:
    """Register all available migrations."""
    for module, migrator in _discover_migrations().items():
        try:
            migrator()
        except Exception as e:
            warning(f"failed to register migration for {module}: {e}")


# ── Migration Sub-App ───────────────────────────────────────────────────────

migri_app = typer.Typer(
    name="migri",
    help=tr("Administri migradojn de autish al A-moduloj"),
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@migri_app.callback(invoke_without_command=True)
def migri_callback(ctx: typer.Context) -> None:
    """Run all pending migrations (default, no subcommand)."""
    # Only run if no subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    _register_migrations()
    results = migrate_all()

    if not results:
        info("Neniuj migrationoj haveblas.")
        return

    success("Rezultoj de migrado:")
    for module, result in results.items():
        if result.skipped:
            info(f"  {module}: saltita ({result.skipped_reason})")
        elif result.errors:
            error(f"  {module}: {result.migrated_rows}/{result.source_rows} — eraroj: {len(result.errors)}")
        else:
            success(f"  {module}: {result.migrated_rows}/{result.source_rows} migritaj")


@migri_app.command("ls")
def migri_ls() -> None:
    """List available migrations."""
    _register_migrations()
    show_migration_status()


@migri_app.command("statuso")
def migri_statuso() -> None:
    """Show migration status."""
    _register_migrations()
    show_migration_status()


# Register migri as subcommand
app.add_typer(migri_app, name="migri")


def show_migration_status() -> None:
    """Show migration status for all modules."""
    discovered = _discover_migrations()

    if not discovered:
        info("Neniuj migr-moduloj trovite.")
        info("Instalu A-modulojn kun migr-ad funkcioj.")
        return

    success(f"Migrada stato ({len(discovered)} moduloj):")

    status_map = get_status()

    for module in sorted(discovered.keys()):
        if module in status_map:
            st: MigrationStatus = status_map[module]
            if st.migrated:
                info(f"  {module}: migrantita ({st.migrated_rows} vicoj)")
            elif st.available:
                info(f"  {module}: havebla ({st.source_rows} vicoj por migrantadi)")
            else:
                info(f"  {module}: nehavebla")
    else:
        info(f"  {module}: neiniciatita")


def _get_pip_command():
    """Find the best available pip command."""
    from A.utils.deps import get_pip_command
    return get_pip_command()


def _ensure_keyring() -> bool:
    """Ensure the keyring library is available, offering to install if not.
    
    Returns:
        True if keyring is available, False if user declined.
    """
    from A.utils.deps import ensure_dependency
    try:
        ensure_dependency("keyring")
        return True
    except ImportError:
        return False


# ── Modulo sub-app ────────────────────────────────────────────────────────────

modulo_app = typer.Typer(
    name="modulo",
    help=tr_multi(
        "Moduloj — administered de A-moduloj",
        "Modules — A module management",
        "Modules — gestion des modules A",
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


def _get_first_line(text: str, max_chars: int = 60) -> str:
    """Extract the first meaningful line from a markdown description."""
    line = ""
    for part in text.split("\n"):
        stripped = part.strip()
        if stripped and not stripped.startswith("#"):
            line = stripped
            break
    if len(line) > max_chars:
        line = line[: max_chars - 1] + "\u2026"
    return line


@modulo_app.command("ls")
def modulo_ls(
    instalita: bool = typer.Option(
        False,
        "--instalita",
        help=tr_multi(
            "Montri nur instalitajn modulojn",
            "Show only installed modules",
            "Afficher uniquement les modules install\u00e9s",
        ),
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help=tr_multi(
            "Refre\u015digi la manifeston de la reto",
            "Refresh the registry from network",
            "Actualiser le registre depuis le r\u00e9seau",
        ),
    ),
) -> None:
    """Listigi modulojn el la registra manifest."""
    if instalita:
        modules = get_installed_modules()
        if not modules:
            info(tr_multi(
                "Neniuj moduloj instalitaj.",
                "No modules installed.",
                "Aucun module install\u00e9.",
            ))
            return

        table = Table(show_header=True, header_style="dim", box=None)
        table.add_column("#", style="dim", width=3)
        table.add_column(tr_multi("Nomo", "Name", "Nom"), style="bold")
        table.add_column(tr_multi("Pip-paketo", "Pip package", "Paquet pip"), style="dim")

        for i, m in enumerate(modules, 1):
            table.add_row(str(i), m.get("display_name", m["name"]), m.get("pip", ""))
        console.print(table)
        return

    # Full list: available + installed
    data = fetch_registry(refresh=refresh)
    if data is None:
        error(tr_multi(
            "Ne eblas atingi la modul-registron. Kontrolu vian retkonekton.",
            "Cannot reach the module registry. Check your internet connection.",
            "Impossible d'atteindre le registre. V\u00e9rifiez votre connexion.",
        ))
        raise typer.Exit(1)

    installed_names = {m["name"] for m in get_installed_modules()}
    all_modules = sorted(data.get("modules", []), key=lambda m: m.get("name", ""))

    table = Table(show_header=True, header_style="dim", box=None)
    table.add_column("#", style="dim", width=3)
    table.add_column(tr_multi("Nomo", "Name", "Nom"), style="bold")
    table.add_column(
        tr_multi("Priskribo", "Description", "Description"), style="dim"
    )
    table.add_column(
        tr_multi("Stato", "Status", "\u00c9tat"), style="dim", width=12
    )

    for i, m in enumerate(all_modules, 1):
        name = m.get("name", "")
        display = m.get("display_name", name)
        desc = _get_first_line(m.get("description", ""))
        status = ""
        if name in installed_names:
            status = tr_multi("\u2713 instalita", "\u2713 installed", "\u2713 install\u00e9")
        table.add_row(str(i), display, desc, status)

    console.print(table)


@modulo_app.command("serci")
def modulo_serci(
    keyword: str = typer.Argument(
        ...,
        help=tr_multi(
            "\u015closilvorto por ser\u0109i modulojn",
            "Keyword to search modules",
            "Mot-cl\u00e9 pour rechercher des modules",
        ),
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help=tr_multi(
            "Refre\u015digi la manifeston de la reto",
            "Refresh the registry from network",
            "Actualiser le registre depuis le r\u00e9seau",
        ),
    ),
) -> None:
    """Ser\u0109i modulojn la\u016d nomo a\u016d priskribo."""
    # Force refresh before searching
    if refresh:
        fetch_registry(refresh=True)

    results = search_registry(keyword)

    if not results:
        info(tr_multi(
            f"Neniuj rezultoj por '{keyword}'.",
            f"No results for '{keyword}'.",
            f"Aucun r\u00e9sultat pour '{keyword}'.",
        ))
        return

    if len(results) == 1:
        _show_module_info(results[0])
        return

    # Multiple results — use interactive selection
    result = select_candidate(
        results,
        columns=[
            {
                "header": tr_multi("Nomo", "Name", "Nom"),
                "style": "bold",
            },
            {
                "header": tr_multi("Priskribo", "Description", "Description"),
                "style": "dim",
            },
        ],
        row_formatter=lambda m, i: [
            m.get("display_name", m.get("name", "")),
            _get_first_line(m.get("description", ""), 50),
        ],
    )
    if result is not None:
        _show_module_info(result[1])


def _show_module_info(module: dict) -> None:
    """Display a single module's information panel."""
    name = module.get("display_name", module.get("name", ""))
    pip = module.get("pip", "")
    desc = module.get("description", "")

    # Check install status
    installed_names = {m["name"] for m in get_installed_modules()}
    is_installed = module.get("name", "") in installed_names

    status_text = (
        tr_multi("\u2713 instalita", "\u2713 installed", "\u2713 install\u00e9")
        if is_installed
        else tr_multi("havebla", "available", "disponible")
    )

    # Render description as HTML for panel body
    body = render_markdown(desc)

    panel = Panel(
        body,
        title=f"[bold]{name}[/bold]",
        subtitle=f"[dim]pip install {pip}[/dim]",
    )
    console.print(panel)
    console.print(f"[dim]Stato: {status_text}[/dim]")


@modulo_app.command("info")
def modulo_info(
    name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nomo de la moduloj",
            "Module name",
            "Nom du module",
        ),
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help=tr_multi(
            "Refre\u015digi la manifeston de la reto",
            "Refresh the registry from network",
            "Actualiser le registre depuis le r\u00e9seau",
        ),
    ),
) -> None:
    """Vidi detalajn informojn pri modulo."""
    if refresh:
        fetch_registry(refresh=True)

    module = get_module_info(name)
    if module is None:
        error(tr_multi(
            f"Modulo '{name}' ne trovita en la registraro.",
            f"Module '{name}' not found in the registry.",
            f"Module '{name}' introuvable dans le registre.",
        ))
        # Show available names
        data = fetch_registry()
        if data:
            names = ", ".join(m.get("name", "") for m in data.get("modules", []))
            info(tr_multi(
                f"Disponeblaj moduloj: {names}",
                f"Available modules: {names}",
                f"Modules disponibles : {names}",
            ))
        raise typer.Exit(1)

    _show_module_info(module)


app.add_typer(modulo_app, name="modulo")


@app.command("repl")
def repl(
    ctx: typer.Context,
    module_name: str = typer.Argument(
        ...,
        help=tr_multi(
            "Nomo de la modulo por eniri REPL-re\u011dimon",
            "Module name to enter REPL mode",
            "Nom du module pour entrer en mode REPL",
        ),
    ),
) -> None:
    """Eniri interagan REPL-re\u011dimon por A-modulo.

    In the REPL, type subcommands directly without the 'A <module>' prefix.
    Use 'exit' or Ctrl+D to quit, '!' for shell commands.
    """
    from A.core.plugin_loader import _PLUGIN_ENTRY_POINTS, get_plugin_app
    from A.utils.repl import ModuleREPL

    if module_name not in _PLUGIN_ENTRY_POINTS:
        error(tr_multi(
            f"Modulo '{module_name}' ne estas instalita a\u016d trovita.",
            f"Module '{module_name}' is not installed or not found.",
            f"Module '{module_name}' n'est pas install\u00e9 ou introuvable.",
        ))
        raise typer.Exit(1)

    app = get_plugin_app(module_name)
    if app is None:
        error(tr_multi(
            f"Ne eblas \u015dargi modulon '{module_name}'.",
            f"Cannot load module '{module_name}'.",
            f"Impossible de charger le module '{module_name}'.",
        ))
        raise typer.Exit(1)

    # Derive the module path and attribute name from the entry point
    # (not app.__module__, which points to typer.main — the Typer class
    # module). Entry point value format: "module:attr" e.g. "A_lien.cli:retposto"
    ep = _PLUGIN_ENTRY_POINTS[module_name]
    mod_path = ep.value.split(":", 1)[0]
    mod_attr = ep.value.split(":", 1)[1] if ":" in ep.value else "app"

    ModuleREPL(
        module_name=module_name,
        module_app=app,
        module_path=mod_path,
        module_attr=mod_attr,
    ).cmdloop()


def main():
    """Main entry point."""
    ensure_dirs()

    # Populate plugin entry points (names only — no module loading)
    _PLUGIN_ENTRY_POINTS.update(discover_plugin_names())

    # Run — plugins loaded lazily on first use
    app()


if __name__ == "__main__":
    main()
