# -*- coding: utf-8 -*-
"""Markdown parser using mistune with Pygments syntax highlighting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import mistune
from mistune import HTMLRenderer

if TYPE_CHECKING:
    from pygments.lexers import Lexer
    from pygments.formatters import Formatter


class HighlightRenderer(HTMLRenderer):
    """Markdown renderer with syntax highlighting for code blocks."""

    def __init__(self, escape: bool = True) -> None:
        """Initialize renderer.

        Args:
            escape: Whether to escape HTML characters. Set False only if
                markdown content is trusted.
        """
        super().__init__(escape=escape)

    def block_code(self, code: str, info: str | None = None) -> str:
        """Render code block with syntax highlighting.

        Args:
            code: The code content.
            info: Language info string (e.g., 'python' from ```python).

        Returns:
            HTML string with syntax highlighting.
        """
        if not info:
            # No language specified, escape plain text
            return f"<pre><code>{mistune.escape(code)}</code></pre>\n"

        # Use Pygments for syntax highlighting
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name
            from pygments.formatters import HtmlFormatter

            # Get lexer for the language
            lexer: Lexer = get_lexer_by_name(info, stripall=True)
            formatter: Formatter = HtmlFormatter()
            return highlight(code, lexer, formatter)
        except Exception:
            # Fallback to plain escape
            return f"<pre><code>{mistune.escape(code)}</code></pre>\n"


# Module-level cached markdown parser
_markdown_parser: mistune.Markdown | None = None


def get_parser() -> mistune.Markdown:
    """Get or create the markdown parser.

    Returns:
        Configured mistune Markdown instance.
    """
    global _markdown_parser
    if _markdown_parser is None:
        _markdown_parser = _make_parser()
    return _markdown_parser


def _make_parser(escape: bool = True) -> mistune.Markdown:
    """Create a markdown parser with math support.

    The mistune math plugin's default renderers HTML-escape math content
    (``&`` → ``&amp;``), which breaks LaTeX ``&`` (matrix column separator,
    alignment, etc.). We override the renderers to pass raw LaTeX through.

    Two modifications are applied on top of the plugin:

    1. The inline math regex ``\\$(?!\\s)…(?!\\s)\\$`` is relaxed to
       ``\\$\\s*…\\s*\\$``, allowing whitespace after the opening ``$`` and
       before the closing ``$``.  The upstream pattern rejects ``$ f(x) $``
       (space after ``$``), which is common in LaTeX prose.

    2. The math renderers escape ``&``, ``<``, ``>`` etc. so the HTML DOM
       text node contains proper LaTeX after browser decoding.
    """
    renderer = HighlightRenderer(escape=escape)
    md = mistune.create_markdown(renderer=renderer, plugins=["math"])

    # --- 1. Relax inline math pattern (allow whitespace around $…$) ---
    md.inline.specification["inline_math"] = (
        r"\$\s*(?P<math_text>(?:[^$\\]|\\.)+?)\s*\$"
    )
    # Clear the compiled regex cache so the new pattern takes effect
    md.inline._Parser__sc.clear()

    # --- 2. Override math renderers to use custom HTML escaping. ---
    #
    # The mistune math plugin's default renderers HTML-escape math content,
    # which was originally disabled because & -> &amp; was thought to break
    # LaTeX & (alignment marker). However, the browser decodes &amp; back
    # to & in DOM text nodes, so full HTML escaping is correct and necessary.
    #
    # Without proper escaping, characters like < and > in LaTeX (e.g. T_{<l})
    # are interpreted as HTML tag delimiters, which corrupts the DOM and
    # prevents KaTeX auto-render from finding math delimiters.
    methods = getattr(renderer, "_BaseRenderer__methods", {})
    methods["inline_math"] = lambda text: (
        r'<span class="math">\(' + mistune.escape(text) + r'\)</span>'
    )
    methods["block_math"] = lambda text: (
        '<div class="math">$$\n' + mistune.escape(text) + '\n$$</div>\n'
    )
    return md


def render_markdown(text: str, escape: bool = True) -> str:
    """Render markdown text to HTML.

    Args:
        text: Markdown content.
        escape: Whether to escape HTML. Set False only for trusted content.

    Returns:
        Rendered HTML string.
    """
    md = _make_parser(escape=escape)
    return md(text)


__all__ = [
    "HighlightRenderer",
    "get_parser",
    "render_markdown",
]