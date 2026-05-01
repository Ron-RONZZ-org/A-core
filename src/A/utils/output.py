"""Output utilities with calm, minimal styling."""

from rich.console import Console
from rich.style import Style
from rich.text import Text


# Minimal styles - no bold, no highlighs by default
STYLES = {
    "info": Style(dim=True),
    "success": Style(color="green", dim=True),
    "warning": Style(color="yellow"),
    "error": Style(color="red"),
    "label": Style(bold=True),
}

console = Console(markup=True, emoji=False, highlight=False, safe_box=True)


def info(message: str) -> None:
    """Print info message (dim)."""
    console.print(message, style=STYLES["info"])


def success(message: str) -> None:
    """Print success message (muted green)."""
    console.print(f"[✓] {message}", style=STYLES["success"])


def warning(message: str) -> None:
    """Print warning message (yellow)."""
    console.print(f"[!] {message}", style=STYLES["warning"])


def error(message: str) -> None:
    """Print error message (red)."""
    console.print(f"[!] {message}", style=STYLES["error"])


def label(text: str) -> str:
    """Format a label (bold)."""
    return Text(text, style=STYLES["label"])