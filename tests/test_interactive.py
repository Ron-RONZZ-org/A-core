"""Tests for A.utils.interactive."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from A.utils.interactive import select_candidate, confirm_action


# ── select_candidate ─────────────────────────────────────────────────────────


def _simple_formatter(item: str, idx: int) -> list[str]:
    return [item, str(len(item))]


COLUMNS = [
    {"header": "Item", "style": "bold"},
    {"header": "Length", "style": "dim", "width": 6},
]


@patch("A.utils.interactive.typer.prompt")
def test_select_valid(mock_prompt):
    """Valid selection returns correct (index, item)."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "2"

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    idx, item = result
    assert idx == 1
    assert item == "banana"


@patch("A.utils.interactive.typer.prompt")
def test_select_skip(mock_prompt):
    """Empty input (Enter) returns None."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = ""

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_invalid_input(mock_prompt):
    """Non-numeric input returns None."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = "abc"

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_out_of_range(mock_prompt):
    """Out-of-range index returns None."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = "999"

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_zero_index(mock_prompt):
    """0 (before 1-based range) returns None."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = "0"

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_last_item(mock_prompt):
    """Last index is valid."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "3"

    result = select_candidate(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    idx, item = result
    assert idx == 2
    assert item == "cherry"


def test_select_empty_list():
    """Empty candidates returns None without prompting."""
    result = select_candidate([], columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_custom_prompt(mock_prompt):
    """Custom prompt text is used."""
    candidates = ["apple"]
    mock_prompt.return_value = "1"

    result = select_candidate(
        candidates,
        columns=COLUMNS,
        row_formatter=_simple_formatter,
        prompt_text="Pick one:",
        default="1",
    )
    assert result is not None
    mock_prompt.assert_called_with("Pick one:", default="1")


@patch("A.utils.interactive.typer.prompt")
def test_select_row_formatter_called(mock_prompt):
    """Row formatter is called for each candidate."""
    candidates = ["a", "b"]
    calls = []

    def spy_formatter(item: str, idx: int) -> list[str]:
        calls.append((item, idx))
        return [item]

    mock_prompt.return_value = "1"
    select_candidate(candidates, columns=[{"header": "X"}], row_formatter=spy_formatter)

    assert calls == [("a", 1), ("b", 2)]


# ── confirm_action ───────────────────────────────────────────────────────────


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_yes_en(mock_prompt, mock_lang):
    """English: entering 'y' returns True, prompt has [y/n]."""
    mock_lang.return_value = "en"
    mock_prompt.return_value = "y"
    assert confirm_action("Proceed?") is True
    mock_prompt.assert_called_once_with("Proceed? [y/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_no_en(mock_prompt, mock_lang):
    """English: entering 'n' returns False."""
    mock_lang.return_value = "en"
    mock_prompt.return_value = "n"
    assert confirm_action("Proceed?") is False


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_yes_eo(mock_prompt, mock_lang):
    """Esperanto: prompt has [j/n], entering 'j' returns True."""
    mock_lang.return_value = "eo"
    mock_prompt.return_value = "j"
    assert confirm_action("Proceed?") is True
    mock_prompt.assert_called_once_with("Proceed? [j/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_yes_fr(mock_prompt, mock_lang):
    """French: prompt has [o/n], entering 'o' returns True."""
    mock_lang.return_value = "fr"
    mock_prompt.return_value = "o"
    assert confirm_action("Proceed?") is True
    mock_prompt.assert_called_once_with("Proceed? [o/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_default_true(mock_prompt, mock_lang):
    """default=True: prompt default is the yes_char; empty input returns True."""
    mock_lang.return_value = "en"
    mock_prompt.return_value = ""
    assert confirm_action("Proceed?", default=True) is True
    mock_prompt.assert_called_once_with("Proceed? [y/n]", default="y")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_default_false_empty(mock_prompt, mock_lang):
    """default=False: prompt default is the no_char; empty input returns False."""
    mock_lang.return_value = "en"
    mock_prompt.return_value = ""
    assert confirm_action("Proceed?", default=False) is False
    mock_prompt.assert_called_once_with("Proceed? [y/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_yes_char_override(mock_prompt, mock_lang):
    """yes_char overrides the language-based default prompt suffix."""
    mock_lang.return_value = "eo"  # eo normally uses [j/n]
    mock_prompt.return_value = "y"
    assert confirm_action("Proceed?", yes_char="y") is True
    mock_prompt.assert_called_once_with("Proceed? [y/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_no_char_override(mock_prompt, mock_lang):
    """no_char overrides the language-based default prompt suffix."""
    mock_lang.return_value = "en"  # en normally uses [y/n]
    mock_prompt.return_value = "x"
    assert confirm_action("Proceed?", no_char="x") is False
    mock_prompt.assert_called_once_with("Proceed? [y/x]", default="x")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_unknown_language_fallback(mock_prompt, mock_lang):
    """Unsupported language falls back to [y/n]."""
    mock_lang.return_value = "de"
    mock_prompt.return_value = "y"
    assert confirm_action("Proceed?") is True
    mock_prompt.assert_called_once_with("Proceed? [y/n]", default="n")


@patch("A.core.i18n.get_current_language")
@patch("A.utils.interactive.typer.prompt")
def test_confirm_retry_on_invalid(mock_prompt, mock_lang):
    """Invalid input retries the prompt (loop continues until valid)."""
    mock_lang.return_value = "en"
    mock_prompt.side_effect = ["maybe", "y"]
    assert confirm_action("Proceed?") is True
    assert mock_prompt.call_count == 2
