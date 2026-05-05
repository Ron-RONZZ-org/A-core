"""Output utilities with calm, minimal styling."""

from typing import Any

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text


# Minimal styles - dim for info, bold for emphasis/signaling
STYLES = {
    "info": Style(dim=True),
    "success": Style(color="green", bold=True),
    "warning": Style(color="yellow", bold=True),
    "error": Style(color="red", bold=True),
    "label": Style(bold=True),
}

console = Console(markup=True, emoji=False, highlight=False, safe_box=True)


def info(message: str, nl: bool = True) -> None:
    """Print info message (dim).
    
    Args:
        message: Message to print
        nl: If False, don't print newline
    """
    console.print(message, style=STYLES["info"], end="" if not nl else "\n")


def success(message: str) -> None:
    """Print success message (muted green)."""
    console.print(f"[✓] {message}", style=STYLES["success"])


def warning(message: str) -> None:
    """Print warning message (yellow)."""
    console.print(f"[!] {message}", style=STYLES["warning"])


def error(message: str) -> None:
    """Print error message (red)."""
    console.print(f"[✗] {message}", style=STYLES["error"])


def label(text: str) -> str:
    """Format a label (bold)."""
    return Text(text, style=STYLES["label"])


def print_table(
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    title: str | None = None,
    max_col_width: int = 50,
) -> None:
    """Print data as a formatted table.

    Args:
        columns: List of column definitions.
                 Each dict: {"header": str, "key": str, "style": str, "width": int, "no_wrap": bool}
        rows: List of row data (dicts with keys matching column "key").
        title: Optional table title.
        max_col_width: Maximum column width for overflow.

    Example:
        print_table(
            columns=[
                {"header": "UUID", "key": "uuid", "style": "dim"},
                {"header": "Nomo", "key": "nomo"},
                {"header": "Kategorio", "key": "kategorio"},
            ],
            rows=[
                {"uuid": "abc123", "nomo": "Test", "kategorio": "vorto"},
                {"uuid": "def456", "nomo": "Example", "kategorio": "frazo"},
            ],
            title="Vortoj",
        )
    """
    if not rows:
        info("Neniuj rezultoj.")
        return

    table = Table(title=title, show_header=True, header_style="bold")

    for col in columns:
        header = col.get("header", "")
        key = col.get("key", "")
        style = col.get("style", "")
        width = col.get("width")
        no_wrap = col.get("no_wrap", False)

        table.add_column(
            header,
            style=style or "",
            width=width,
            no_wrap=no_wrap,
            max_width=max_col_width if not width else None,
        )

    for row in rows:
        values = []
        for col in columns:
            key = col.get("key", "")
            val = row.get(key)

            # Handle various data types
            if val is None:
                values.append("-")
            elif isinstance(val, bool):
                values.append("1" if val else "0")
            elif isinstance(val, list):
                # Handle JSON arrays (kategorioj, lingvoj, etc.)
                if val and isinstance(val[0], dict):
                    # List of dicts: extract "valoro" or first value
                    extracted = [str(v.get("valoro", v.get("nomo", str(v)))) for v in val]
                    values.append(", ".join(extracted) if extracted else "-")
                else:
                    values.append(", ".join(str(v) for v in val))
            elif isinstance(val, dict):
                # Handle JSON objects (kampoj)
                values.append(", ".join(f"{k}:{v}" for k, v in val.items()) if val else "-")
            else:
                values.append(str(val))

        table.add_row(*values)

    console.print(table)