# -*- coding: utf-8 -*-
"""Web content extraction for LLM consumption.

Provides HTML-to-text conversion with two backends:

1. **trafilatura** (if installed) — intelligent main-content extraction
   that strips navigation, sidebars, and boilerplate.
2. **stdlib HTMLParser** (fallback) — basic tag stripping.

Both paths apply LaTeX noise removal to clean up math markup common in
scientific/educational pages.

Usage::

    from A.core.web import html_to_text, extract_text

    # From raw HTML
    text = html_to_text(html_string)

    # Fetch + extract in one call
    text = extract_text("https://example.com/article")
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

__all__ = [
    "html_to_text",
    "extract_text",
]


# ── Stdlib HTMLParser backend ─────────────────────────────────────────────


class _TextExtractor(HTMLParser):
    """HTML parser that extracts plain text, removing tags, scripts, styles."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True
        if tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


# ── LaTeX noise removal ───────────────────────────────────────────────────

# Patterns that carry no semantic value for LLM consumption.
# These are regex (pattern, replacement) pairs applied in order.
_LATEX_NOISE: list[tuple[str, str]] = [
    (r"\\(?:newcommand|renewcommand|DeclareMathOperator)\*?\{[^}]*\}\{[^}]*\}", ""),
    (r"\\(?:begin|end)\{(?:document|align\*?|equation\*?|enumerate|itemize)\}", ""),
    # Formatting commands: keep content but strip the wrapper
    (r"\\(?:text|mathbf|mathrm|mathbb|mathcal|mathit|mathsf|mathtt|textit|textbf|emph|underline|textrm|textsf|texttt|textsc|textsl)\{([^}]*)\}", r"\1"),
    (r"\\(?:displaystyle|textstyle|scriptstyle|scriptscriptstyle)", ""),
    (r"\\(?:quad|qquad|enspace|thickspace|medspace|;|:)", " "),
    (r"\\(?:left|right|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr)", ""),
    (r"\\(?:label|ref|eqref|pageref)\{[^}]*\}", ""),
    (r"\\(?:hfill|vfill|hspace|vspace)\{[^}]*\}", ""),
    (r"\$|\\\\|\\\(", r""),
    (r"\\\)", ""),
]


def _strip_latex_noise(text: str) -> str:
    """Remove LaTeX formatting markup, preserving semantic content.

    Strips ``\\textbf{...}`` → ``...``, ``\\[`` / ``\\]`` / ``$`` delimiters,
    and other non-semantic LaTeX commands.  Lines consisting entirely of
    short LaTeX definitions are removed to save context budget.
    """
    # Complex patterns via regex
    for pattern, repl in _LATEX_NOISE:
        text = re.sub(pattern, repl, text)

    # Simple literal patterns — str.replace avoids regex escaping quirks
    for literal in (r"\[", r"\]"):
        text = text.replace(literal, "")

    # Remove lines that are entirely short LaTeX command definitions
    lines = [
        line for line in text.split("\n")
        if not (line.strip().startswith("\\") and len(line.strip()) < 120)
    ]
    return "\n".join(lines)


# ── trafilatura backend ───────────────────────────────────────────────────

_trafilatura = None  # type: ignore[assignment]
try:
    import trafilatura as _trafilatura  # type: ignore[no-redef]
except ImportError:
    pass


def _extract_with_trafilatura(html: str) -> str | None:
    """Extract plain text via trafilatura, or *None* if unavailable."""
    if _trafilatura is None:
        return None
    try:
        return _trafilatura.extract(
            html,
            output_format="txt",
            include_links=False,
            include_images=False,
            include_tables=False,
        )
    except Exception:
        return None


def _extract_stdlib(html: str) -> str:
    """Fallback: extract plain text via stdlib HTMLParser."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        return html
    text = extractor.get_text()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ── Public API ────────────────────────────────────────────────────────────


def html_to_text(html: str, max_chars: int = 50_000) -> str:
    """Extract plain text from HTML for LLM consumption.

    Args:
        html: Raw HTML content.
        max_chars: Maximum characters to return (0 = no limit).
            Default 50 000 fits most LLM context windows.

    Returns:
        Clean plain text with LaTeX noise removed.
    """
    text = _extract_with_trafilatura(html)
    if text is None:
        text = _extract_stdlib(html)

    text = _strip_latex_noise(text)
    text = text.strip()

    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars]

    return text


def extract_text(
    url: str,
    *,
    max_chars: int = 50_000,
    max_bytes: int = 5_000_000,
    timeout: int = 15,
) -> str:
    """Fetch a URL and extract plain text in a single call.

    Convenience wrapper around ``A.core.http.fetch_text()`` +
    :func:`html_to_text`.

    Args:
        url: HTTP or HTTPS URL.
        max_chars: Maximum characters for extracted text.
        max_bytes: Maximum HTTP response bytes.
        timeout: Request timeout in seconds.

    Returns:
        Clean plain text.
    """
    from A.core.http import fetch_text

    html = fetch_text(url, max_bytes=max_bytes, timeout=timeout)
    return html_to_text(html, max_chars=max_chars)
