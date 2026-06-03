"""Tests for A.utils.interactive."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from A.utils.interactive import (
    select_candidate,
    select_candidates,
    confirm_action,
)


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


def test_confirm_yes():
    """confirm_action returns True when confirmed."""
    from unittest.mock import patch as _p
    with _p("A.utils.interactive.typer.prompt", return_value="y"), \
         _p("A.core.i18n.get_current_language", return_value="en"):
        assert confirm_action("Proceed?") is True


def test_confirm_no():
    """confirm_action returns False when declined."""
    from unittest.mock import patch as _p
    with _p("A.utils.interactive.typer.prompt", return_value="n"), \
         _p("A.core.i18n.get_current_language", return_value="en"):
        assert confirm_action("Proceed?") is False


def test_confirm_default():
    """Default value is respected."""
    from unittest.mock import patch as _p
    with _p("A.utils.interactive.typer.prompt", return_value=""), \
         _p("A.core.i18n.get_current_language", return_value="en"):
        assert confirm_action("Proceed?", default=True) is True
        assert confirm_action("Proceed?", default=False) is False


def test_confirm_esperanto():
    """confirm_action accepts J (Jes) in Esperanto locale."""
    from unittest.mock import patch as _p
    with _p("A.utils.interactive.typer.prompt", return_value="j"), \
         _p("A.core.i18n.get_current_language", return_value="eo"):
        assert confirm_action("Proceed?") is True


def test_confirm_french():
    """confirm_action accepts O (Oui) in French locale."""
    from unittest.mock import patch as _p
    with _p("A.utils.interactive.typer.prompt", return_value="o"), \
         _p("A.core.i18n.get_current_language", return_value="fr"):
        assert confirm_action("Proceed?") is True


def _capture_prompt_text(return_value: str = "") -> tuple[list[str], str]:
    """Capture the prompt text passed to typer.prompt.

    Returns (captured_texts, return_value) for use as side_effect.
    """
    captured: list[str] = []

    def _side_effect(text: str, **kwargs: object) -> str:
        captured.append(text)
        return return_value

    return captured, _side_effect  # type: ignore[return-value]


# ── Prompt abbreviation tests ──────────────────────────────────────────────


def test_prompt_abbrev_default_true_english():
    """Shows [Y/n] when default=True in English."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="en"):
        confirm_action("Go?", default=True)
    assert "[Y/n]" in captured[0]


def test_prompt_abbrev_default_false_english():
    """Shows [y/N] when default=False in English."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="en"):
        confirm_action("Go?", default=False)
    assert "[y/N]" in captured[0]


def test_prompt_abbrev_default_true_esperanto():
    """Shows [J/n] when default=True in Esperanto."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="eo"):
        confirm_action("Go?", default=True)
    assert "[J/n]" in captured[0]


def test_prompt_abbrev_default_false_esperanto():
    """Shows [j/N] when default=False in Esperanto."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="eo"):
        confirm_action("Go?", default=False)
    assert "[j/N]" in captured[0]


def test_prompt_abbrev_default_true_french():
    """Shows [O/n] when default=True in French."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="fr"):
        confirm_action("Go?", default=True)
    assert "[O/n]" in captured[0]


def test_prompt_abbrev_default_false_french():
    """Shows [o/N] when default=False in French."""
    from unittest.mock import patch as _p
    captured, side_effect = _capture_prompt_text("")
    with _p("A.utils.interactive.typer.prompt", side_effect=side_effect), \
         _p("A.core.i18n.get_current_language", return_value="fr"):
        confirm_action("Go?", default=False)
    assert "[o/N]" in captured[0]


# ── select_candidates ──────────────────────────────────────────────────────


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_valid(mock_prompt):
    """Space-separated input returns correct list of (index, item)."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "1 3"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    assert len(result) == 2
    assert result[0] == (0, "apple")
    assert result[1] == (2, "cherry")


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_skip(mock_prompt):
    """Empty input (Enter) returns None."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = ""

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_invalid_tokens(mock_prompt):
    """Non-numeric tokens are silently skipped; valid ones still selected."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "1 abc 3"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    assert len(result) == 2
    assert result[0] == (0, "apple")
    assert result[1] == (2, "cherry")


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_all_invalid(mock_prompt):
    """Only invalid tokens returns None (same as cancel)."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = "abc xyz !!!"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_out_of_range(mock_prompt):
    """Out-of-range indices are silently skipped."""
    candidates = ["apple", "banana"]
    mock_prompt.return_value = "1 999"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    assert len(result) == 1
    assert result[0] == (0, "apple")


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_duplicates(mock_prompt):
    """Duplicate indices (e.g. '1 1 6') are deduplicated."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "1 1 1"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    assert len(result) == 1
    assert result[0] == (0, "apple")


@patch("A.utils.interactive.typer.prompt")
def test_select_candidates_single(mock_prompt):
    """Single number input works (same as select_candidate but returns list)."""
    candidates = ["apple", "banana", "cherry"]
    mock_prompt.return_value = "2"

    result = select_candidates(candidates, columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is not None
    assert len(result) == 1
    assert result[0] == (1, "banana")


def test_select_candidates_empty_list():
    """Empty candidates returns None without prompting."""
    result = select_candidates([], columns=COLUMNS, row_formatter=_simple_formatter)
    assert result is None
