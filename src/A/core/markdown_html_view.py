# -*- coding: utf-8 -*-
"""HTML preview for markdown with browser rendering and caching."""

from __future__ import annotations

import hashlib
import tempfile
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from A.core.markdown_parser import render_markdown

if TYPE_CHECKING:
    from typing import Optional


# Cache directory for rendered HTML
_html_cache_dir: Path | None = None


def get_cache_dir() -> Path:
    """Get or create the HTML cache directory.

    Returns:
        Path to the cache directory.
    """
    global _html_cache_dir
    if _html_cache_dir is None:
        from A.core.paths import cache_dir
        _html_cache_dir = cache_dir() / "markdown"
        _html_cache_dir.mkdir(parents=True, exist_ok=True)
    return _html_cache_dir


def _generate_html_wrapper(content: str, title: str = "Preview") -> str:
    """Wrap HTML content in a full page template.

    Args:
        content: The HTML body content.
        title: Page title.

    Returns:
        Complete HTML page.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
        }}
        pre {{
            background: #f5f5f5;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
        }}
        code {{
            font-family: 'Fira Code', 'Consolas', monospace;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 0;
            padding-left: 1rem;
            color: #666;
        }}
        img {{
            max-width: 100%;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>"""


def _get_cache_key(text: str) -> str:
    """Generate cache key from markdown text.

    Args:
        text: The markdown text.

    Returns:
        SHA256 hash as hex string.
    """
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _get_cached_html(text: str) -> Path | None:
    """Get cached HTML file if exists.

    Args:
        text: The markdown text.

    Returns:
        Path to cached HTML or None if not cached.
    """
    cache_key = _get_cache_key(text)
    cache_file = get_cache_dir() / f"{cache_key}.html"
    if cache_file.exists():
        return cache_file
    return None


def _save_cached_html(text: str, html: str) -> Path:
    """Save rendered HTML to cache.

    Args:
        text: The original markdown text.
        html: Rendered HTML content.

    Returns:
        Path to the cached file.
    """
    cache_key = _get_cache_key(text)
    cache_file = get_cache_dir() / f"{cache_key}.html"
    cache_file.write_text(html, encoding="utf-8")
    return cache_file


def preview_markdown(
    text: str,
    use_cache: bool = True,
    open_browser: bool = True,
    title: str = "Preview",
) -> Path:
    """Render markdown to HTML and open in browser.

    Args:
        text: Markdown content.
        use_cache: Whether to use caching (lazy render).
        open_browser: Whether to open in browser.
        title: Page title.

    Returns:
        Path to the rendered HTML file.
    """
    # Try cache first
    if use_cache:
        cached = _get_cached_html(text)
        if cached is not None:
            if open_browser:
                webbrowser.open(cached.as_uri())
            return cached

    # Render markdown
    html_body = render_markdown(text, escape=False)
    full_html = _generate_html_wrapper(html_body, title=title)

    # Save to cache or temp
    if use_cache:
        html_path = _save_cached_html(text, full_html)
    else:
        # Use temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(full_html)
            html_path = Path(f.name)

    # Open in browser
    if open_browser:
        webbrowser.open(html_path.as_uri())

    return html_path


def preview_html(
    html: str,
    open_browser: bool = True,
    title: str = "Preview",
) -> Path:
    """Open HTML content directly in browser.

    Args:
        html: HTML content (already rendered).
        open_browser: Whether to open in browser.
        title: Page title.

    Returns:
        Path to the rendered HTML file.
    """
    full_html = _generate_html_wrapper(html, title=title)

    # Use temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(full_html)
        html_path = Path(f.name)

    if open_browser:
        webbrowser.open(html_path.as_uri())

    return html_path


def clear_cache() -> int:
    """Clear the HTML cache directory.

    Returns:
        Number of files deleted.
    """
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        return 0

    count = 0
    for file in cache_dir.glob("*.html"):
        file.unlink()
        count += 1
    return count


__all__ = [
    "preview_markdown",
    "preview_html",
    "clear_cache",
    "get_cache_dir",
]