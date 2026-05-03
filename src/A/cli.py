"""A CLI main entry point."""

import importlib.metadata
from typing import Callable

import typer

from A import tr, tr_multi
from A.core.paths import ensure_dirs
from A.core.migration import get_status, migrate_all, migrate_keyring_passwords, MigrationStatus
from A.utils import info, success, error, warning


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
    """Listigi agorditajn komandojn."""
    names = sorted(_PLUGIN_ENTRY_POINTS.keys())

    if not names:
        info("Neniuj kromprogramoj instalitaj. Instalu per: pip install A[tempo]")
        return

    success(f"Agordeblaj komandoj ({len(names)}):")
    for name in names:
        info(f"  {name}")


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


@app.command("migri-keyring")
def migri_keyring_cmd() -> None:
    """Migradu pasvortojn de autish al A."""
    imported = _ensure_keyring()
    if not imported:
        raise typer.Exit(1)
    
    migrated = migrate_keyring_passwords()
    if migrated > 0:
        success(f"{migrated} pasvortoj migrantitaj")
    else:
        info("Neniuj pasvortoj por migradi")


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


def main():
    """Main entry point."""
    ensure_dirs()

    # Populate plugin entry points (names only — no module loading)
    _PLUGIN_ENTRY_POINTS.update(_discover_plugin_names())

    # Run — plugins loaded lazily on first use
    app()


if __name__ == "__main__":
    main()
