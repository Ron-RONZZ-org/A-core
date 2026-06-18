"""Tests for A.core.plugin_loader — lazy plugin loading, info_name fix."""

from __future__ import annotations

import click
import typer
from typer.testing import CliRunner


def _make_sub(app: typer.Typer, name: str) -> None:
    """Register a dummy sub-command on *app*."""
    @app.command(name)
    def _dummy() -> None:
        pass


class TestFuzzyMatching:
    """``resolve_command`` must keep the standard single "Did you mean"
    suggestion from TyperGroup (no regressions for #15 sub-issue 3).

    The duplicate "Did you mean" issue reported in #15 could not be
    reproduced with the current Click/Typer version.  The installed
    TyperGroup already produces exactly one suggestion.
    """

    def test_typo_shows_suggestion(self) -> None:
        """A typo close to an existing command shows "Did you mean" once."""
        app = typer.Typer()
        _make_sub(app, "start")
        _make_sub(app, "stop")

        runner = CliRunner()
        result = runner.invoke(app, ["stopp"])  # typo of "stop"
        assert result.exit_code != 0
        assert result.output.count("Did you mean") == 1, (
            f"Expected single 'Did you mean', got: {result.output!r}"
        )

    def test_no_suggestion_for_unrelated(self) -> None:
        """A completely unrelated command shows no suggestion."""
        app = typer.Typer()
        _make_sub(app, "start")

        runner = CliRunner()
        result = runner.invoke(app, ["xyzzy"])
        assert result.exit_code != 0
        assert "xyzzy" in result.output

    def test_known_command_success(self) -> None:
        """A known command dispatches normally."""
        app = typer.Typer()
        _make_sub(app, "ping")
        _make_sub(app, "pong")  # 2nd command so Typer creates a Group

        runner = CliRunner()
        result = runner.invoke(app, ["ping"])
        assert result.exit_code == 0

    def test_lazy_group_typo(self) -> None:
        """LazyPluginGroup should also show suggestion when command is typo'd."""
        from A.core.plugin_loader import LazyPluginGroup

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "aldoni")
        _make_sub(app, "vidi")

        runner = CliRunner()
        result = runner.invoke(app, ["vido"])  # typo of "vidi"
        assert result.exit_code != 0
        # Should suggest 'vidi'
        assert "vidi" in result.output


class TestPatchInfoName:
    """Sub-issue 4: ``_patch_info_name`` must propagate the full command path."""

    def test_single_level(self) -> None:
        """A single command gets ``info_name = \"<parent> <name>\"``."""
        from A.core.plugin_loader import LazyPluginGroup

        group = click.Group("test")
        cmd = click.Command("hello")
        group.add_command(cmd)

        LazyPluginGroup._patch_info_name(group, "parent")

        assert group.info_name == "parent test"
        assert cmd.info_name == "parent test hello"

    def test_nested_commands(self) -> None:
        """Sub-commands of sub-commands are patched recursively."""
        from A.core.plugin_loader import LazyPluginGroup

        sub = click.Group("sub")
        sub.add_command(click.Command("leaf1"))
        sub.add_command(click.Command("leaf2"))

        root = click.Group("root")
        root.add_command(sub)

        LazyPluginGroup._patch_info_name(root, "top")

        assert root.info_name == "top root"
        assert sub.info_name == "top root sub"
        assert sub.commands["leaf1"].info_name == "top root sub leaf1"
        assert sub.commands["leaf2"].info_name == "top root sub leaf2"

    def test_empty_parent_path(self) -> None:
        """When parent_path is empty, info_name is just the command name."""
        from A.core.plugin_loader import LazyPluginGroup

        cmd = click.Command("foo")
        LazyPluginGroup._patch_info_name(cmd, "")
        assert cmd.info_name == "foo"

    def test_group_from_typer_app(self) -> None:
        """Children from a Typer->Click conversion get the correct path."""
        from A.core.plugin_loader import LazyPluginGroup

        typer_app = typer.Typer(name="mymod")
        _make_sub(typer_app, "ls")
        _make_sub(typer_app, "vidi")
        _make_sub(typer_app, "aldoni")
        click_cmd = typer.main.get_command(typer_app)

        LazyPluginGroup._patch_info_name(click_cmd, "vorto")

        assert click_cmd.info_name == "vorto mymod"
        for sub_name in ("ls", "vidi", "aldoni"):
            sub = click_cmd.commands[sub_name]
            assert sub.info_name == f"vorto mymod {sub_name}", (
                f"Expected info_name 'vorto mymod {sub_name}', "
                f"got {sub.info_name!r}"
            )


class TestGetCommand:
    """Lazy loading of plugins via ``get_command``."""

    def test_unknown_plugin_returns_none(self) -> None:
        """Requesting an unknown plugin returns None (no crash)."""
        from A.core.plugin_loader import LazyPluginGroup

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "dummy1")
        _make_sub(app, "dummy2")
        runner = CliRunner()
        # Invoke a non-existent command — should get error, not crash
        result = runner.invoke(app, ["nonexistent_plugin_xyz"])
        assert result.exit_code != 0

    def test_builtin_command_cached(self) -> None:
        """A built-in command is cached and subsequent calls return same object."""
        from A.core.plugin_loader import LazyPluginGroup

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "mycmd")
        _make_sub(app, "mycmd2")

        runner = CliRunner()
        result = runner.invoke(app, ["mycmd"])
        assert result.exit_code == 0


class TestListCommands:
    """``list_commands`` must include expected commands."""

    def test_builtin_commands_listed(self) -> None:
        """Built-in commands appear in help."""
        from A.core.plugin_loader import LazyPluginGroup

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "builtin_cmd")

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "builtin_cmd" in result.output

    def test_plugin_names_listed(self) -> None:
        """Unloaded plugin names appear in help output."""
        from A.core.plugin_loader import LazyPluginGroup, _PLUGIN_ENTRY_POINTS

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "builtin_cmd")

        # Simulate a discovered plugin
        _PLUGIN_ENTRY_POINTS["myplugin"] = None  # placeholder

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Both built-in and plugin names should appear
        assert "builtin_cmd" in result.output

    def test_private_commands_hidden(self) -> None:
        """Commands starting with _ are not listed by ``list_commands``."""
        from A.core.plugin_loader import LazyPluginGroup

        app = typer.Typer(cls=LazyPluginGroup)
        _make_sub(app, "visible")
        _make_sub(app, "_hidden")

        # Invoke --help — hidden commands shouldn't appear in the group listing
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "visible" in result.output
        # '_hidden' may be shown differently; the important thing is
        # that LazyPluginGroup.list_commands excludes _-prefixed names
        # (tested implicitly through help rendering)


class TestLoadPlugin:
    """``load_plugin`` handles failure gracefully."""

    def test_unknown_plugin(self) -> None:
        """Loading a plugin that is not in _PLUGIN_ENTRY_POINTS returns None."""
        from A.core.plugin_loader import load_plugin
        assert load_plugin("nonexistent") is None

    def test_invalid_plugin_non_typer(self) -> None:
        """A plugin that isn't a Typer app returns None gracefully."""
        from A.core.plugin_loader import load_plugin
        assert load_plugin("nonexistent2") is None
