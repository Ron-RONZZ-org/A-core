"""REPL loop for A-modules using stdlib ``cmd.Cmd``.

Usage::

    from A.core.plugin_loader import get_plugin_app
    from A.utils.repl import ModuleREPL

    app = get_plugin_app("tempo")
    ModuleREPL(module_name="tempo", module_app=app).cmdloop()
"""

from __future__ import annotations

import cmd
import os
import shlex
import sys
import importlib
from pathlib import Path

from A.core.paths import state_dir
from A.utils.output import info, success, error, console

HISTORY_LENGTH = 1000


class ModuleREPL(cmd.Cmd):
    """Interactive REPL for a single A-module's Typer app.

    Attributes:
        module_name: Name of the module (shown in prompt).
        module_app: The ``typer.Typer`` instance to dispatch commands to.
        prompt: The REPL prompt string (``{module_name}> ``).
    """

    intro = (
        "REPL-mode. Type help or ? for commands, exit to quit.\n"
        "  !<cmd>  run a shell command"
    )

    def __init__(
        self,
        module_name: str,
        module_app,
        module_path: str | None = None,
        module_attr: str = "app",
    ) -> None:
        """Initialise the REPL.

        Args:
            module_name: Short display name (e.g. ``"tempo"``).
            module_app: The ``typer.Typer`` instance to dispatch to.
            module_path: Fully qualified module path of the app (e.g.
                ``"A_tempo.cli"``). If ``None``, falls back to
                ``module_app.__module__`` (which points to ``typer.main``
                and will break ``refresh``).
            module_attr: Attribute name on the module that holds the app
                (e.g. ``"app"``, ``"retposto"``). Default ``"app"``.
        """
        super().__init__()
        self.module_name = module_name
        self.module_app = module_app
        self._module_path = module_path or module_app.__module__
        self._module_attr = module_attr
        self.prompt = f"{module_name}> "
        self._hist_path: Path | None = None
        self._load_history()

    # ── History ────────────────────────────────────────────────────────────

    def _load_history(self) -> None:
        """Load command history from ``state_dir/repl/<module>.history``."""
        try:
            import readline  # noqa: F401
        except ImportError:
            return

        import readline as rl

        hist_dir = state_dir() / "repl"
        hist_dir.mkdir(parents=True, exist_ok=True)
        self._hist_path = hist_dir / f"{self.module_name}.history"
        try:
            rl.read_history_file(str(self._hist_path))
        except (FileNotFoundError, OSError):
            pass
        rl.set_history_length(HISTORY_LENGTH)

    def _save_history(self) -> None:
        """Persist command history to disk."""
        if self._hist_path is None:
            return
        try:
            import readline as rl

            rl.write_history_file(str(self._hist_path))
        except (ImportError, OSError):
            pass

    # ── Lifecycle hooks ────────────────────────────────────────────────────

    def preloop(self) -> None:
        info(self.intro)

    def postloop(self) -> None:
        self._save_history()

    # ── Command dispatch ───────────────────────────────────────────────────

    def onecmd(self, line: str) -> bool:
        """Intercept ``!``-prefixed lines before dispatch."""
        if line.startswith("!"):
            self.do_shell(line[1:])
            return False
        return super().onecmd(line)

    def default(self, line: str) -> None:
        """Pass an unrecognized line as arguments to the module's Typer app.

        Example: typing ``resumu --limo 5`` in the REPL invokes
        ``module_app(args=["resumu", "--limo", "5"])``.
        """
        try:
            args = shlex.split(line)
            if not args:
                return
            self.module_app(args=args)
        except SystemExit:
            pass  # Typer/Click uses SystemExit for --help, errors, etc.
        except Exception as e:
            error(str(e))

    def emptyline(self) -> None:
        """Do nothing on empty line (don't repeat last command)."""
        pass

    # ── Built-in REPL commands ─────────────────────────────────────────────

    def do_exit(self, _arg: str) -> bool:
        """Exit the REPL."""
        return True

    do_quit = do_exit

    def do_help(self, _arg: str) -> None:
        """Show the module's help (same as ``--help``)."""
        self.default("--help")

    def do_refresh(self, _arg: str) -> None:
        """Hot-reload source code without exiting the REPL.

        Reloads all A-* modules in dependency order (core first, then plugins).
        Sub-modules (e.g. A_xxx.data) are reloaded before their parent packages.
        """
        mod_name = self._module_path
        base_pkg = mod_name.split(".")[0]

        # Collect ALL A-* modules currently loaded
        a_modules = {name: mod for name, mod in sys.modules.items()
                     if mod is not None and name.startswith("A_")
                     and hasattr(mod, "__file__") and mod.__file__ is not None}

        # Sort: by package name (deps first: A-core < A-encik < A-agento),
        # then by module depth descending (sub-modules before parents)
        pkg_order = {"A_core": 0, "A_encik": 1, "A_lien": 2, "A_organizi": 3,
                     "A_vorto": 4, "A_tempo": 5, "A_sistemo": 6, "A_medio": 7,
                     "A_sekurkopio": 8}
        def sort_key(name):
            pkg = name.split(".")[0]
            depth = name.count(".")
            return (pkg_order.get(pkg, 99), -depth, name)

        sorted_modules = sorted(a_modules.keys(), key=sort_key)
        info(f"Refreshing {len(sorted_modules)} modules...")

        for name in sorted_modules:
            try:
                importlib.reload(sys.modules[name])
            except Exception as e:
                error(f"  {name}: {e}")

        # Re-import the main entry module and rebuild the app
        # importlib.import_module already returns the deepest module —
        # no need to traverse submodule hierarchy manually.
        try:
            fresh = importlib.import_module(mod_name)
            new_app = getattr(fresh, self._module_attr)
            self.module_app = new_app
            success("Reloaded. All A-* modules refreshed.")
        except Exception as e:
            error(f"Failed to reload main app: {e}")

    def do_shell(self, arg: str) -> None:
        """Run a shell command. Usage: ``!<command>`` or ``shell <command>``."""
        if arg:
            os.system(arg)

    # ── Ctrl+C / Ctrl+D ────────────────────────────────────────────────────

    def cmdloop(self, intro: str | None = None) -> None:
        """Override to handle Ctrl+C (stay in REPL) and Ctrl+D (exit)."""
        while True:
            try:
                super().cmdloop(intro="")
                break
            except KeyboardInterrupt:
                console.print()
                continue

    def do_EOF(self, _arg: str) -> bool:
        """Ctrl+D — exit the REPL."""
        return True


__all__ = [
    "ModuleREPL",
]
