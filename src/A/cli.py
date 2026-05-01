"""A CLI main entry point."""

import sys
import importlib.metadata
from pathlib import Path
from functools import lru_cache

import typer

from A import tr
from A.core.paths import ensure_dirs
from A.utils import info, success, error
from A.core.exceptions import AError


# Cache for discovered plugins
_DISCOVERED_PLUGINS: dict[str, typer.Typer] = {}


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


app = typer.Typer(
    name="A",
    help=tr("A - minimuma CLI kadro"),
    no_args_is_help=True,
)


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


@app.command("help")
def help_cmd() -> None:
    """Montri ĉi tiun helpon."""
    # Ensure plugins are registered first
    for name, cmd_app in _discover_plugins().items():
        app.add_typer(cmd_app, name=name)
    typer.echo(app.get_help())


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