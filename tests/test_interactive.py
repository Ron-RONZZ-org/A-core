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


@patch("A.utils.interactive.typer.confirm")
def test_confirm_yes(mock_confirm):
    """confirm_action returns True when confirmed."""
    mock_confirm.return_value = True
    assert confirm_action("Proceed?") is True
    mock_confirm.assert_called_with("Proceed?", default=False)


@patch("A.utils.interactive.typer.confirm")
def test_confirm_no(mock_confirm):
    """confirm_action returns False when declined."""
    mock_confirm.return_value = False
    assert confirm_action("Proceed?") is False


@patch("A.utils.interactive.typer.confirm")
def test_confirm_default(mock_confirm):
    """Default value is passed to typer.confirm."""
    mock_confirm.return_value = True
    confirm_action("Proceed?", default=True)
    mock_confirm.assert_called_with("Proceed?", default=True)
