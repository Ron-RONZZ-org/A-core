# -*- coding: utf-8 -*-
"""HTML preview for markdown with KaTeX math rendering.

Supports offline KaTeX by downloading assets on first use and inlining
them into HTML (avoids Chrome ``file://`` CORS restrictions on local
``<script>``/``<link>`` tags).

- Phase 1: inline KaTeX into HTML (offline after first download)
- Phase 2 (future): ``encik serve`` local HTTP server for rich browsing
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from A.core.markdown_parser import render_markdown

if TYPE_CHECKING:
    from typing import Optional


# Cache directory for rendered HTML
_html_cache_dir: Path | None = None

# Cache version — bump when HTML template or KaTeX assets change
CACHE_VERSION = 3

# KaTeX version — pinned for reproducibility (matches autish-legacy)
KATEX_VERSION = "0.16.11"

# CDN base URL for KaTeX
_KATEX_CDN = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist"

# Files to download from KaTeX CDN (css, js, auto-render)
_KATEX_FILES = {
    "katex.min.css": f"{_KATEX_CDN}/katex.min.css",
    "katex.min.js": f"{_KATEX_CDN}/katex.min.js",
    "auto-render.min.js": f"{_KATEX_CDN}/contrib/auto-render.min.js",
}

# KaTeX auto-render configuration block — wrapped in DOMContentLoaded so it
# works both when inlined in <head> (DOM not yet ready) and via CDN onload.
_AUTO_RENDER_CONFIG = """document.addEventListener('DOMContentLoaded', function() {
    renderMathInElement(document.body, {
        delimiters: [
          {left: '$$', right: '$$', display: true},
          {left: '$', right: '$', display: false},
          {left: '\\\\[', right: '\\\\]', display: true},
          {left: '\\\\(', right: '\\\\)', display: false}
        ],
        throwOnError: false,
        strict: 'ignore'
    });
});"""


# ── KaTeX asset management ───────────────────────────────────────────────


def _katex_dir() -> Path:
    """Return the local KaTeX cache directory path.

    ``~/.cache/A/katex/{version}/`` — versioned so old dirs are left in place
    when the KaTeX version is bumped.
    """
    from A.core.paths import cache_dir as _cd
    return _cd() / "katex" / KATEX_VERSION


def _ensure_katex() -> bool:
    """Download KaTeX CSS/JS assets to local cache on first use.

    Uses atomic ``.part`` → rename pattern to avoid corrupt files from
    partial downloads. Safe for concurrent processes on the same filesystem.

    Returns:
        True if assets are available locally, False on any failure.
    """
    kdir = _katex_dir()
    kdir.mkdir(parents=True, exist_ok=True)

    all_available = True
    for filename, url in _KATEX_FILES.items():
        dest = kdir / filename
        if dest.exists():
            continue

        # Atomic download: write to .part, then rename
        part = dest.with_suffix(".part")
        try:
            urllib.request.urlretrieve(url, part)
            part.rename(dest)
        except Exception:
            all_available = False
            part.unlink(missing_ok=True)
            break

    return all_available


def _inline_katex_html() -> str:
    """Build KaTeX HTML snippet by inlining locally cached files.

    Returns:
        ``<style>`` block with CSS + ``<script>`` blocks with JS, all inlined.
    """
    kdir = _katex_dir()

    css_path = kdir / "katex.min.css"
    js_path = kdir / "katex.min.js"
    auto_render_path = kdir / "auto-render.min.js"

    parts: list[str] = []

    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
        # Replace relative font URLs (url(fonts/...)) with absolute CDN URLs
        # so fonts load correctly when the HTML file is opened from /tmp/.
        css_content = css_content.replace(
            "url(fonts/", f"url({_KATEX_CDN}/fonts/"
        )
        parts.append(f"<style>\n{css_content}\n</style>")

    if js_path.exists():
        js_content = js_path.read_text(encoding="utf-8")
        parts.append(f"<script>\n{js_content}\n</script>")

    if auto_render_path.exists():
        auto_render_content = auto_render_path.read_text(encoding="utf-8")
        parts.append(
            f"<script>\n{auto_render_content}\n"
            f"{_AUTO_RENDER_CONFIG}\n"
            f"</script>"
        )

    return "\n".join(parts)


def _cdn_katex_html() -> str:
    """Build KaTeX HTML snippet using CDN URLs (fallback).

    Returns:
        ``<link>`` and ``<script>`` tags pointing to the KaTeX CDN.
    """
    return (
        f'<link rel="stylesheet" href="{_KATEX_CDN}/katex.min.css">\n'
        f'<script defer src="{_KATEX_CDN}/katex.min.js"></script>\n'
        f'<script defer src="{_KATEX_CDN}/contrib/auto-render.min.js"\n'
        f'  onload="{_AUTO_RENDER_CONFIG}">\n'
        f"</script>"
    )


# Module-level cache: avoid re-reading files on every call
_katex_html_cache: str | None = None


def KATEX_HTML() -> str:
    """Return the KaTeX HTML snippet for embedding in HTML pages.

    Prefers locally cached (inlined) assets for offline use.
    Falls back to CDN URLs if local assets are unavailable.

    The result is cached in memory after the first successful call,
    avoiding repeated filesystem reads and download attempts.

    Returns:
        HTML string (``<style>``/``<script>`` blocks or CDN ``<link>``/``<script>``).
    """
    global _katex_html_cache
    if _katex_html_cache is not None:
        return _katex_html_cache

    # Attempt inline (local) path
    if _ensure_katex():
        result = _inline_katex_html()
    else:
        result = _cdn_katex_html()

    _katex_html_cache = result
    return result


def ensure_katex() -> bool:
    """Explicitly trigger KaTeX download.

    Can be called at startup (e.g., from ``agordi``) to pre-cache KaTeX
    assets before going offline.

    Returns:
        True if assets are available locally.
    """
    success = _ensure_katex()
    if success:
        # Pre-populate module cache so KATEX_HTML() doesn't re-check
        global _katex_html_cache
        _katex_html_cache = _inline_katex_html()
    return success


# ── Cache directory ──────────────────────────────────────────────────────


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


# ── HTML page template ──────────────────────────────────────────────────


def _generate_html_wrapper(content: str, title: str = "Preview") -> str:
    """Wrap HTML content in a full page template with KaTeX support.

    Args:
        content: The HTML body content.
        title: Page title.

    Returns:
        Complete HTML page.
    """
    katex_html = KATEX_HTML()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {katex_html}
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


# ── Cache helpers ───────────────────────────────────────────────────────


def _get_cache_key(text: str) -> str:
    """Generate cache key from markdown text.

    Includes cache version to invalidate old entries when
    the HTML template changes (e.g. new KaTeX version).

    Args:
        text: The markdown text.

    Returns:
        Version-prefixed SHA256 hash as hex string.
    """
    return f"v{CACHE_VERSION}_" + hashlib.sha256(text.encode()).hexdigest()[:16]


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


# ── Public preview functions ────────────────────────────────────────────


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
    """Clear the HTML and KaTeX cache directories.

    Returns:
        Number of files deleted (HTML + KaTeX).
    """
    count = 0
    # Clear HTML cache
    cache_dir = get_cache_dir()
    if cache_dir.exists():
        for file in cache_dir.glob("*.html"):
            file.unlink()
            count += 1

    # Clear KaTeX cache (all version dirs)
    from A.core.paths import cache_dir as _pd
    katex_root = _pd() / "katex"
    if katex_root.exists():
        for ver_dir in katex_root.iterdir():
            if ver_dir.is_dir():
                for f in ver_dir.iterdir():
                    f.unlink()
                    count += 1
                ver_dir.rmdir()

    return count


__all__ = [
    "preview_markdown",
    "preview_html",
    "clear_cache",
    "get_cache_dir",
    "KATEX_HTML",
    "ensure_katex",
    "KATEX_VERSION",
    "CACHE_VERSION",
]
