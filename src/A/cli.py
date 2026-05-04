"""A CLI main entry point."""

import importlib.metadata
from typing import Callable

import typer
from rich.table import Table
from rich.panel import Panel

from A import tr, tr_multi
from A.core.paths import ensure_dirs
from A.core.migration import get_status, migrate_all, MigrationStatus
from A.core.registry import fetch_registry, get_module_info, get_installed_modules, search_registry
from A.core.markdown_parser import render_markdown
from A.utils import info, success, error, warning, console
from A.utils.interactive import select_candidate


# ── Lazy Plugin Loading ──────────────────────────────────────────────────────
# Entry points discovered by name only — plugins are loaded on first command use.
# This means `A retposto ls` won't trigger loading A-sistemo (or other plugins).

_PLUGIN_ENTRY_POINTS: dict[str, importlib.metadata.EntryPoint] = {}


def _discover_plugin_names() -> dict[str, importlib.metadata.EntryPoint]:
    """Discover plugin entry points without loading them.

    Returns: dict mapping plugin name → EntryPoint
    """
    try:
        eps = importlib.metadata.entry_points(group="A.commands")
    except TypeError:
        # Python < 3.10
        eps = importlib.metadata.entry_points().get("A.commands", [])
    return {ep.name: ep for ep in eps}


def _load_plugin(name: str) -> typer.main.TyperGroup | None:
    """Load a plugin by name, returning a Click/Typer command or None on failure."""
    ep = _PLUGIN_ENTRY_POINTS.get(name)
    if ep is None:
        return None
    try:
        real = ep.load()
        if not isinstance(real, typer.Typer):
            error(f"invalid plugin {name}: not a Typer app")
            return None
        return typer.main.get_command(real)
    except Exception as e:
        error(f"failed to load {name}: {e}")
        return None


class LazyPluginGroup(typer.main.TyperGroup):
    """Click Group that lazy-loads A plugins on first invocation.

    Plugins are not imported at startup — only when the user runs a command
    that belongs to that plugin. Failed loads are silently dropped from the
    command list.
    """

    def get_command(
        self, ctx: typer.Context, cmd_name: str
    ) -> typer.main.TyperGroup | None:
        # Already loaded (built-in command or previously cached)?
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd

        # First access — load from entry point
        if cmd_name in _PLUGIN_ENTRY_POINTS:
            click_cmd = _load_plugin(cmd_name)
            if click_cmd is not None:
                self.add_command(click_cmd, name=cmd_name)
                return click_cmd
            # Load failed — remove so we don't try again
            _PLUGIN_ENTRY_POINTS.pop(cmd_name, None)

        return None

    def list_commands(self, ctx: typer.Context) -> list[str]:
        cmds = list(super().list_commands(ctx))
        for name in _PLUGIN_ENTRY_POINTS:
            if name not in cmds:
                cmds.append(name)
        return [c for c in cmds if not c.startswith("_")]


# ── Main App ─────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="A",
    cls=LazyPluginGroup,
    help=tr("A - minimuma CLI kadro"),
    no_args_is_help=True,
    pretty_exceptions_short=True,
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    h: bool = typer.Option(None, "-h", "--help", help="Montri helpon", is_eager=True),
) -> None:
    """A - minimuma CLI kadro."""
    if h is not None:
        typer.echo(ctx.get_help())


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
    """Register all discovered migrations by calling their registration functions."""
    for module, migrator in _discover_migrations().items():
        try:
            migrator()
        except Exception as e:
            warning(f"failed to register migration for {module}: {e}")


@app.command("migri")
def migri_cmd(
    status: bool = typer.Option(
        False,
        "--status",
        "-s",
        help=tr("Montri staton de cxiuj migradoj"),
    ),
    list_cmd: bool = typer.Option(
        False,
        "--list",
        "-l",
        help=tr("Listigi cxiujn disponeblajn migradojn"),
    ),
) -> None:
    """Montri migr-adolon aŭ migradan staton."""
    _register_migrations()

    if status or list_cmd:
        show_migration_status()
        return

    results = migrate_all()

    if not results:
        info("Neniuj migrationoj haveblas.")
        return

    success("Rezultoj de migr-adolo:")
    for module, result in results.items():
        if result.skipped:
            info(f"  {module}: saltita ({result.skipped_reason})")
        elif result.errors:
            detail_msg = f" {result.detail}" if result.detail else ""
            error(f"  {module}: {result.migrated_rows}/{result.source_rows}{detail_msg} eraroj: {len(result.errors)}")
        else:
            detail_msg = f" {result.detail}" if result.detail else ""
            success(f"  {module}: {result.migrated_rows}/{result.source_rows}{detail_msg} ✓")


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
    """Find the best available pip command, respecting venv isolation.
    
    Returns:
        list: pip command arguments ready for subprocess
    """
    import shutil, os
    
    # 1. Try uv pip first (uv-managed venvs preserve isolation)
    uv_cmd = shutil.which("uv")
    if uv_cmd:
        return [uv_cmd, "pip"]
    
    # 2. Try pip in PATH
    pip_cmd = shutil.which("pip") or shutil.which("pip3")
    if pip_cmd:
        return [pip_cmd]
    
    # 3. Try python3 -m pip
    python3 = shutil.which("python3")
    if python3:
        return [python3, "-m", "pip"]
    
    # 4. Last resort: sys.executable (may break isolation in broken venvs)
    import sys
    return [sys.executable, "-m", "pip"]


def _ensure_keyring() -> bool:
    """Ensure the keyring library is available, offering to install if not.
    
    Returns:
        True if keyring is available, False if user declined.
    """
    import importlib
    try:
        importlib.import_module("keyring")
        return True
    except ImportError:
        import typer
        from A import tr_multi
        
        answer = typer.confirm(
            tr_multi(
                "Bezonas 'keyring' bibliotekon. Ĉu instali ĝin nun?",
                "The 'keyring' library is required. Install it now?",
                "La bibliothèque 'keyring' est nécessaire. Installer maintenant ?",
            ),
            default=True,
        )
        if not answer:
            return False
        
        try:
            import subprocess
            pip_cmd = _get_pip_command()
            # Suppress pip output unless it fails
            subprocess.check_call(
                pip_cmd + ["install", "keyring"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Re-import after install
            importlib.import_module("keyring")
            return True
        except Exception as e:
            error(f"Instalo malsukoresis: {e}")
            return False
        
        try:
            import subprocess, sys
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "keyring"]
            )
            # Re-import after install
            importlib.import_module("keyring")
            return True
        except Exception as e:
            error(f"Instalo malsukcesis: {e}")
            return False


# ── Modulo sub-app ────────────────────────────────────────────────────────────

modulo_app = typer.Typer(
    name="modulo",
    help=tr_multi(
        "Moduloj — administrado de A-moduloj",
        "Modules — A module management",
        "Modules — gestion des modules A",
    ),
    no_args_is_help=True,
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


def main():
    """Main entry point."""
    ensure_dirs()

    # Populate plugin entry points (names only — no module loading)
    _PLUGIN_ENTRY_POINTS.update(_discover_plugin_names())

    # Run — plugins loaded lazily on first use
    app()


if __name__ == "__main__":
    main()
