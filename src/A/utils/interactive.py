"""
Generic interactive selection utilities for A CLI.

Provides a reusable "show numbered table → prompt for selection" pattern
that can be used across all A-modules.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

import typer
from rich.table import Table

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

    # Build table
    table = Table(show_header=True, header_style="dim", box=None)
    table.add_column("#", style="dim", width=3)
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


_CONFIRM_PROMPTS: dict[str, tuple[str, str]] = {
    "eo": ("j", "n"),  # jes / ne
    "en": ("y", "n"),  # yes / no
    "fr": ("o", "n"),  # oui / non
}


def confirm_action(
    message: str,
    *,
    default: bool = False,
    yes_char: str | None = None,
    no_char: str | None = None,
) -> bool:
    """Display a yes/no confirmation prompt with locale-aware characters.

    The prompt suffix adapts to the current language:
    - eo: ``[j/n]`` (jes/ne)
    - en: ``[y/n]`` (yes/no)
    - fr: ``[o/n]`` (oui/non)

    Parameters
    ----------
    message:
        The question to show.
    default:
        Default answer (used when user presses Enter).
    yes_char:
        Override the "yes" character (default: from current language).
    no_char:
        Override the "no" character (default: from current language).

    Returns
    -------
    ``True`` if confirmed, ``False`` otherwise.
    """
    from A.core.i18n import get_current_language

    lang = get_current_language()
    default_yes, default_no = _CONFIRM_PROMPTS.get(lang, ("y", "n"))
    yes = (yes_char or default_yes).lower()
    no = (no_char or default_no).lower()

    prompt_suffix = f" [{yes}/{no}]"
    default_str = yes if default else no

    while True:
        raw = typer.prompt(message + prompt_suffix, default=default_str)
        raw = raw.strip().lower()
        if raw == yes:
            return True
        if raw == no or not raw:
            return default
