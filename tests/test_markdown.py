# -*- coding: utf-8 -*-
"""Tests for markdown parsing and HTML preview."""

import pytest


def test_render_markdown_basic():
    """Test basic markdown rendering."""
    from A.core.markdown_parser import render_markdown

    result = render_markdown("# Hello\n\nWorld")
    assert "<h1>Hello</h1>" in result
    assert "<p>World</p>" in result


def test_render_markdown_code():
    """Test code block rendering."""
    from A.core.markdown_parser import render_markdown

    markdown_text = "```python\nx = 1\n```"
    result = render_markdown(markdown_text, escape=False)
    # Should contain Pygments output with highlight class
    assert "highlight" in result.lower() or "python" in result.lower()


def test_render_markdown_escape():
    """Test HTML escaping."""
    from A.core.markdown_parser import render_markdown

    # Default escape=True should escape HTML
    result = render_markdown("<script>alert(1)</script>", escape=True)
    assert "&lt;" in result

    # escape=False should preserve HTML
    result = render_markdown("<b>bold</b>", escape=False)
    assert "<b>bold</b>" in result


def test_preview_markdown():
    """Test preview function returns path."""
    from A.core.markdown_html_view import preview_markdown

    # Don't open browser during test
    path = preview_markdown("# Test", open_browser=False)
    assert path.exists()
    assert path.suffix == ".html"


def test_preview_markdown_no_cache():
    """Test preview without caching."""
    from A.core.markdown_html_view import preview_markdown

    path = preview_markdown("# Test", use_cache=False, open_browser=False)
    assert path.exists()
    # Temp files are namedTemporaryFile, may not persist


def test_preview_html():
    """Test HTML preview directly."""
    from A.core.markdown_html_view import preview_html

    html = "<h1>Test</h1>"
    path = preview_html(html, open_browser=False)
    assert path.exists()
    content = path.read_text()
    assert "<h1>Test</h1>" in content


def test_clear_cache():
    """Test cache clearing."""
    from A.core.markdown_html_view import clear_cache

    count = clear_cache()
    assert count >= 0  # May be 0 if cache was already empty


def test_markdown_module_exports():
    """Test modules export correctly."""
    from A import render_markdown, preview_markdown, preview_html, clear_cache

    assert callable(render_markdown)
    assert callable(preview_markdown)
    assert callable(preview_html)
    assert callable(clear_cache)