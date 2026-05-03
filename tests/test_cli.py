"""CLI tests for A-core."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from A.cli import app

runner = CliRunner()


# ── A list (deprecated) ──────────────────────────────────────────────────────


@patch("A.cli.modulo_ls")
def test_list_deprecation(mock_modulo_ls):
    """Old A list shows deprecation warning and delegates."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "malrekomendita" in result.stdout or "deprecated" in result.stdout
    mock_modulo_ls.assert_called_once_with(instalita=True)


# ── A modulo ls ──────────────────────────────────────────────────────────────


@patch("A.cli.fetch_registry")
@patch("A.cli.get_installed_modules")
def test_modulo_ls_installed(mock_installed, mock_fetch):
    """A modulo ls --instalita shows installed modules."""
    mock_installed.return_value = [
        {"name": "tempo", "display_name": "Tempo", "pip": "A-tempo"},
    ]

    result = runner.invoke(app, ["modulo", "ls", "--instalita"])
    assert result.exit_code == 0
    assert "Tempo" in result.stdout
    assert "A-tempo" in result.stdout


@patch("A.cli.fetch_registry")
@patch("A.cli.get_installed_modules")
def test_modulo_ls_installed_empty(mock_installed, mock_fetch):
    """A modulo ls --instalita with no modules shows message."""
    mock_installed.return_value = []

    result = runner.invoke(app, ["modulo", "ls", "--instalita"])
    assert result.exit_code == 0
    assert "Neniuj" in result.stdout or "No modules" in result.stdout


@patch("A.cli.fetch_registry")
@patch("A.cli.get_installed_modules")
def test_modulo_ls_all(mock_installed, mock_fetch):
    """A modulo ls shows all modules with status."""
    mock_fetch.return_value = {
        "version": 1,
        "modules": [
            {"name": "tempo", "display_name": "Tempo", "description": "# T\n\nClock."},
            {"name": "vorto", "display_name": "Vorto", "description": "# V\n\nWords."},
        ],
    }
    mock_installed.return_value = [{"name": "tempo"}]

    result = runner.invoke(app, ["modulo", "ls"])
    assert result.exit_code == 0
    assert "Tempo" in result.stdout
    assert "Vorto" in result.stdout
    assert "\u2713" in result.stdout  # checkmark for installed


@patch("A.cli.fetch_registry")
def test_modulo_ls_no_manifest(mock_fetch):
    """A modulo ls with no registry shows error."""
    mock_fetch.return_value = None

    result = runner.invoke(app, ["modulo", "ls"])
    assert result.exit_code != 0


# ── A modulo serci ───────────────────────────────────────────────────────────


@patch("A.cli.search_registry")
@patch("A.cli.fetch_registry")
def test_modulo_serci_no_results(mock_fetch, mock_search):
    """A modulo serci with no matches shows message."""
    mock_search.return_value = []

    result = runner.invoke(app, ["modulo", "serci", "xyzzy"])
    assert result.exit_code == 0
    assert "Neniuj" in result.stdout or "No results" in result.stdout


@patch("A.cli._show_module_info")
@patch("A.cli.search_registry")
@patch("A.cli.fetch_registry")
def test_modulo_serci_one_result(mock_fetch, mock_search, mock_show):
    """Single search result shows info directly."""
    mock_search.return_value = [{"name": "tempo", "display_name": "Tempo"}]

    result = runner.invoke(app, ["modulo", "serci", "tempo"])
    assert result.exit_code == 0
    mock_show.assert_called_once()


@patch("A.cli.select_candidate")
@patch("A.cli.search_registry")
@patch("A.cli.fetch_registry")
def test_modulo_serci_multi_select(mock_fetch, mock_search, mock_select):
    """Multiple search results use interactive selection."""
    mock_search.return_value = [
        {"name": "tempo", "display_name": "Tempo"},
        {"name": "vorto", "display_name": "Vorto"},
    ]
    mock_select.return_value = (0, mock_search.return_value[0])

    result = runner.invoke(app, ["modulo", "serci", "o"])
    assert result.exit_code == 0


# ── A modulo info ────────────────────────────────────────────────────────────


@patch("A.cli.get_module_info")
@patch("A.cli.get_installed_modules")
def test_modulo_info_found(mock_installed, mock_info):
    """A modulo info shows module panel."""
    mock_installed.return_value = [{"name": "tempo"}]
    mock_info.return_value = {
        "name": "tempo",
        "display_name": "Tempo",
        "pip": "A-tempo",
        "description": "# Tempo\n\nClock.",
    }

    result = runner.invoke(app, ["modulo", "info", "tempo"])
    assert result.exit_code == 0
    assert "Tempo" in result.stdout
    assert "A-tempo" in result.stdout


@patch("A.cli.get_module_info")
@patch("A.cli.fetch_registry")
def test_modulo_info_not_found(mock_fetch, mock_info):
    """A modulo info on unknown module shows error."""
    mock_info.return_value = None
    mock_fetch.return_value = {"version": 1, "modules": []}

    result = runner.invoke(app, ["modulo", "info", "nonexistent"])
    assert result.exit_code != 0
    assert "ne trovita" in result.stdout or "not found" in result.stdout
