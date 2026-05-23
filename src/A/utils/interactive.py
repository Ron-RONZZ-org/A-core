"""
Generic interactive selection utilities for A CLI.

Provides a reusable "show numbered table → prompt for selection" pattern
that can be used across all A-modules.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

import typer
from rich.table import Table
from rich.box import SIMPLE as BOX_SIMPLE

from A import tr_multi
from A.utils.output import info, console

T = TypeVar("T")


def select_candidate(
    candidates: list[T],
    *,
    columns: list[dict[str, Any]],
    row_formatter: Callable[[T, int], list[str]],
    prompt_text: str | None = None,
    default: str = "",
) -> tuple[int, T] | None:
    """Display a numbered table of *candidates* and prompt the user to
    select one.

    Parameters
    ----------
    candidates:
        The items to present for selection.
    columns:
        Rich ``Table`` column definitions **without** the auto ``#`` column.
        Each entry: ``{"header": str, "style": str | None, "width": int | None}``.
    row_formatter:
        ``Callable[[item, 1-based-index], list[str]]`` that returns the cell
        values for a single row.
    prompt_text:
        Prompt shown to the user.  Defaults to a tr()-translated message.
    default:
        Default input when the user presses Enter (``""`` = skip).

    Returns
    -------
    A ``(0-based-index, item)`` tuple or ``None`` if the user skipped.
    """
    if not candidates:
        return None

    # Build table (no per-column colors — greyscale-accessible)
    table = Table(show_header=True, box=BOX_SIMPLE)
    table.add_column("#", width=3)
    for col in columns:
        table.add_column(
            col.get("header", ""),
            style=col.get("style"),
            width=col.get("width"),
        )

    for i, item in enumerate(candidates, 1):
        cells = row_formatter(item, i)
        table.add_row(str(i), *cells)

    console.print(table)

    n = len(candidates)
    info(tr_multi(f"{n} rezultoj", f"{n} results", f"{n} r\u00e9sultats"))

    text = prompt_text or tr_multi(
        "Elektu numeron por vidi detalojn (a\u016d Enter por preteriri)",
        "Select a number to view details (or Enter to skip)",
        "Choisissez un num\u00e9ro (ou Entr\u00e9e pour ignorer)",
    )
    raw = typer.prompt(text, default=default)
    if not raw.strip():
        return None

    try:
        idx = int(raw.strip()) - 1
    except ValueError:
        return None

    if 0 <= idx < len(candidates):
        return (idx, candidates[idx])
    return None


def confirm_action(
    message: str,
    *,
    default: bool = False,
) -> bool:
    """Display a locale-aware yes/no confirmation prompt.

    Shows uppercase letter for the default option:
    - default=True: [J/n] (eo), [Y/n] (en), [O/n] (fr)
    - default=False: [j/N] (eo), [y/N] (en), [o/N] (fr)
    Accepts both the full word (jes/yes/oui) and single letter (j/y/o).

    Parameters
    ----------
    message:
        The question to show.
    default:
        Default answer (used when user presses Enter).

    Returns
    -------
    ``True`` if confirmed, ``False`` otherwise.
    """
    from A.core.i18n import get_current_language

    lang = get_current_language()

    # Locale-specific prompt and accepted inputs
    # Uppercase letter = default option per terminal convention
    if lang == "eo":
        yes_letter, no_letter = ("J", "n") if default else ("j", "N")
        yes_words = {"j", "jes"}
        no_words = {"n", "ne"}
    elif lang == "fr":
        yes_letter, no_letter = ("O", "n") if default else ("o", "N")
        yes_words = {"o", "oui"}
        no_words = {"n", "non"}
    else:
        yes_letter, no_letter = ("Y", "n") if default else ("y", "N")
        yes_words = {"y", "yes"}
        no_words = {"n", "no"}

    prompt_abbr = f"[{yes_letter}/{no_letter}]"

    for _attempt in range(10):
        raw = typer.prompt(f"{message} {prompt_abbr}", default="").strip().lower()
        if not raw:
            return default
        if raw in yes_words:
            return True
        if raw in no_words:
            return False

    # After 10 failed attempts, fall back to default
    return default