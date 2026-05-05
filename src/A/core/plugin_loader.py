"""Plugin loading for A-core CLI.

Handles lazy discovery and loading of A-module plugins via entry points.
Supports AI command injection from A-agento via the "A.ai_commands" group.
"""

from __future__ import annotations

import importlib.metadata

import typer

from A import error


# ── Lazy Plugin Loading ──────────────────────────────────────────────────────
# Entry points discovered by name only — plugins are loaded on first command use.

_PLUGIN_ENTRY_POINTS: dict[str, importlib.metadata.EntryPoint] = {}


def discover_plugin_names() -> dict[str, importlib.metadata.EntryPoint]:
    """Discover plugin entry points without loading them.

    Returns: dict mapping plugin name → EntryPoint
    """
    try:
        eps = importlib.metadata.entry_points(group="A.commands")
    except TypeError:
        # Python < 3.10
        eps = importlib.metadata.entry_points().get("A.commands", [])
    return {ep.name: ep for ep in eps}


def _inject_ai_commands(app: typer.Typer, module_name: str) -> None:
    """Inject AI commands into a module's Typer app from A-agento.

    Checks for entry points in the "A.ai_commands" group matching
    the module name. If found, loads the AI sub-app factory and
    injects it as a named sub-app (appears as a separate section
    in --help output).

    Args:
        app: The module's Typer app to inject into
        module_name: Module identifier (e.g. "lien", "organizi", "encik")
    """
    try:
        ai_eps = importlib.metadata.entry_points(group="A.ai_commands")
    except TypeError:
        ai_eps = importlib.metadata.entry_points().get("A.ai_commands", [])

    for ep in ai_eps:
        if ep.name != module_name:
            continue
        try:
            factory = ep.load()
            ai_app = factory() if callable(factory) else factory
            if isinstance(ai_app, typer.Typer):
                app.add_typer(ai_app, name="ai")
            return
        except Exception:
            pass  # AI commands are optional


def load_plugin(name: str) -> typer.main.TyperGroup | None:
    """Load a plugin by name, returning a Click/Typer command or None on failure.

    Also injects AI commands from A-agento if available.

    Args:
        name: Plugin name matching a "A.commands" entry point

    Returns:
        Click command group or None if loading fails
    """
    ep = _PLUGIN_ENTRY_POINTS.get(name)
    if ep is None:
        return None
    try:
        real = ep.load()
        if not isinstance(real, typer.Typer):
            error(f"invalid plugin {name}: not a Typer app")
            return None

        # Inject AI commands from A-agento if available
        _inject_ai_commands(real, name)

        return typer.main.get_command(real)
    except Exception as e:
        error(f"failed to load {name}: {e}")
        return None


def get_plugin_app(name: str) -> typer.Typer | None:
    """Load a plugin and return the raw ``typer.Typer`` app (not Click-wrapped).

    Unlike ``load_plugin()`` which returns a Click command for CLI dispatch,
    this returns the raw Typer app suitable for programmatic invocation via
    ``app(args=[...])`` (e.g. in the REPL).

    Injects AI commands from A-agento if available.
    """
    ep = _PLUGIN_ENTRY_POINTS.get(name)
    if ep is None:
        return None
    try:
        app = ep.load()
        if not isinstance(app, typer.Typer):
            error(f"Invalid plugin {name}: not a Typer app")
            return None
        _inject_ai_commands(app, name)
        return app
    except Exception as e:
        error(f"Failed to load {name}: {e}")
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
            click_cmd = load_plugin(cmd_name)
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


__all__ = [
    "_PLUGIN_ENTRY_POINTS",
    "discover_plugin_names",
    "load_plugin",
    "LazyPluginGroup",
]
