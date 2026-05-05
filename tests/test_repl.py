"""Tests for A REPL module (``A.utils.repl.ModuleREPL``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from A.utils.repl import ModuleREPL


@pytest.fixture
def mock_app() -> MagicMock:
    return MagicMock()


class TestModuleREPL:
    """Tests for the ModuleREPL class (pure function behaviour)."""

    def test_init(self, mock_app: MagicMock) -> None:
        """Prompt reflects module name."""
        repl = ModuleREPL("tempo", mock_app)
        assert repl.prompt == "tempo> "
        assert repl.module_name == "tempo"

    def test_default_passes_args(self, mock_app: MagicMock) -> None:
        """default() splits the line and calls app(args=...)."""
        repl = ModuleREPL("tempo", mock_app)
        repl.default("resumu --limo 5")
        mock_app.assert_called_once_with(args=["resumu", "--limo", "5"])

    def test_default_handles_system_exit(self, mock_app: MagicMock) -> None:
        """SystemExit from Typer is caught and does not propagate."""
        mock_app.side_effect = SystemExit(0)
        repl = ModuleREPL("tempo", mock_app)
        repl.default("--help")  # Should not raise

    def test_default_empty_args(self, mock_app: MagicMock) -> None:
        """Empty or whitespace-only args are skipped."""
        repl = ModuleREPL("tempo", mock_app)
        repl.default("   ")
        mock_app.assert_not_called()

    def test_exit_returns_true(self, mock_app: MagicMock) -> None:
        """do_exit returns True to signal cmdloop exit."""
        repl = ModuleREPL("tempo", mock_app)
        assert repl.do_exit("") is True

    def test_quit_is_alias(self, mock_app: MagicMock) -> None:
        """do_quit exits the same way as do_exit."""
        repl = ModuleREPL("tempo", mock_app)
        assert repl.do_quit("") is True
        assert repl.do_exit("") is True

    def test_help_shows_module_help(self, mock_app: MagicMock) -> None:
        """do_help passes --help to the module app."""
        repl = ModuleREPL("tempo", mock_app)
        repl.do_help("")
        mock_app.assert_called_once_with(args=["--help"])

    def test_shell_command(self, mock_app: MagicMock) -> None:
        """do_shell runs the command via os.system."""
        with patch("os.system") as mock_os:
            repl = ModuleREPL("tempo", mock_app)
            repl.do_shell("echo hello")
            mock_os.assert_called_once_with("echo hello")

    def test_shell_empty_arg(self, mock_app: MagicMock) -> None:
        """do_shell with empty arg is a no-op."""
        with patch("os.system") as mock_os:
            repl = ModuleREPL("tempo", mock_app)
            repl.do_shell("")
            mock_os.assert_not_called()

    def test_onecmd_shell_escape(self, mock_app: MagicMock) -> None:
        """! prefix triggers do_shell."""
        with patch.object(ModuleREPL, "do_shell") as mock_shell:
            repl = ModuleREPL("tempo", mock_app)
            repl.onecmd("!echo hi")
            mock_shell.assert_called_once_with("echo hi")

    def test_onecmd_normal_dispatch(self, mock_app: MagicMock) -> None:
        """Lines without ! go through normal cmd.Cmd dispatch."""
        with patch.object(ModuleREPL, "default") as mock_default:
            repl = ModuleREPL("tempo", mock_app)
            repl.onecmd("resumu")
            mock_default.assert_called_once_with("resumu")

    def test_emptyline_noop(self, mock_app: MagicMock) -> None:
        """Enter on empty line does nothing."""
        repl = ModuleREPL("tempo", mock_app)
        repl.emptyline()
        mock_app.assert_not_called()

    def test_do_eof_returns_true(self, mock_app: MagicMock) -> None:
        """Ctrl+D (EOF) exits the REPL."""
        repl = ModuleREPL("tempo", mock_app)
        assert repl.do_EOF("") is True

    def test_default_handles_exception(self, mock_app: MagicMock) -> None:
        """Generic exceptions from Typer are caught."""
        mock_app.side_effect = RuntimeError("boom")
        repl = ModuleREPL("tempo", mock_app)
        repl.default("bad-command")  # Should not raise

    def test_history_load_skips_if_no_readline(self, mock_app: MagicMock) -> None:
        """No crash if readline is not available."""
        with patch.dict("sys.modules", {"readline": None}):
            repl = ModuleREPL("tempo", mock_app)
            assert repl._hist_path is None

    def test_history_path(self, mock_app: MagicMock) -> None:
        """History file path is constructed correctly."""
        with patch("A.utils.repl.state_dir") as mock_state_dir:
            mock_state_dir.return_value = Path("/tmp/fake/A")
            repl = ModuleREPL("tempo", mock_app)
            assert str(repl._hist_path) == "/tmp/fake/A/repl/tempo.history"
