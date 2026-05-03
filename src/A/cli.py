"""A CLI main entry point."""

import sys
import importlib.metadata
from pathlib import Path
from functools import lru_cache
from typing import Callable

import typer

from A import tr
from A.core.paths import ensure_dirs
from A.core.migration import get_status, migrate_all, migrate_keyring_passwords, MigrationStatus
from A.utils import info, success, error, warning
from A.core.exceptions import AError


# Cache for discovered plugins
_DISCOVERED_PLUGINS: dict[str, typer.Typer] = {}

# Cache for discovered migrations
_DISCOVERED_MIGRATIONS: dict[str, Callable[[], None]] = {}


def _discover_plugins() -> dict[str, typer.Typer]:
    """Discover installed plugins via entry points (cached)."""
    global _DISCOVERED_PLUGINS
    
    if _DISCOVERED_PLUGINS:
        return _DISCOVERED_PLUGINS
    
    commands = {}
    try:
        eps = importlib.metadata.entry_points(group="A.commands")
    except TypeError:
        # Python < 3.10
        eps = importlib.metadata.entry_points().get("A.commands", [])
    
    for ep in eps:
        try:
            cmd = ep.load()
            # Validate it's a Typer app
            if isinstance(cmd, typer.Typer):
                commands[ep.name] = cmd
            else:
                error(f"invalid plugin {ep.name}: not a Typer app")
        except Exception as e:
            error(f"failed to load {ep.name}: {e}")
    
    _DISCOVERED_PLUGINS = commands
    return commands


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
        # Python < 3.10
        eps = importlib.metadata.entry_points().get("A.migrations", [])
    
    for ep in eps:
        try:
            migrator = ep.load()
            # Validate it's callable
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


app = typer.Typer(
    name="A",
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
def list_commands() -> None:
    """Listigi agorditajn komandojn."""
    plugins = _discover_plugins()
    
    if not plugins:
        info("Neniuj kromprogramoj instalitaj. Instalu per: pip install A[tempo]")
        return
    
    success(f"Agordeblaj komandoj ({len(plugins)}):")
    for name in sorted(plugins.keys()):
        info(f"  {name}")


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
    # Register all discovered migrations first
    _register_migrations()
    
    # Handle --status or --list
    if status or list_cmd:
        show_migration_status()
        return
    
    # Run all pending migrations (using A.core.migration)
    results = migrate_all()
    
    if not results:
        info("Neniuj migrationoj haveblas.")
        return
    
    success("Rezultoj de migr-adolo:")
    for module, result in results.items():
        if result.skipped:
            info(f"  {module}: saltita ({result.skipped_reason})")
        elif result.errors:
            error(f"  {module}: {result.migrated_rows}/{result.source_rows} eraroj: {len(result.errors)}")
        else:
            success(f"  {module}: {result.migrated_rows}/{result.source_rows} migrantitaj")


def show_migration_status() -> None:
    """Show migration status for all modules."""
    discovered = _discover_migrations()
    
    if not discovered:
        info("Neniuj migr-moduloj trovite.")
        info("Instalu A-modulojn kun migr-ad funkcioj.")
        return
    
    success(f"Migrada stato ({len(discovered)} moduloj):")
    
    # Get status from migration framework
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
            # Registered but no status yet
            info(f"  {module}: neiniciatita")


@app.command("migri-keyring")
def migri_keyring_cmd() -> None:
    """Migradu pasvortojn de autish al A."""
    migrated = migrate_keyring_passwords()
    if migrated > 0:
        success(f"{migrated} pasvortoj migrantitaj")
    else:
        info("Neniuj pasvortoj por migradi")


def main():
    """Main entry point."""
    # Initialize directories on first run
    ensure_dirs()
    
    # Register discovered plugins BEFORE running
    for name, cmd_app in _discover_plugins().items():
        app.add_typer(cmd_app, name=name)
    
    # Run
    app()


if __name__ == "__main__":
    main()