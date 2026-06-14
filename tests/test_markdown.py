# -*- coding: utf-8 -*-
"""Tests for markdown parsing and HTML preview."""

import urllib.request

import pytest


@pytest.fixture(autouse=True)
def reset_module_caches():
    """Reset module-level caches before each test to avoid test interaction."""
    from A.core.markdown_html_view import _katex_html_cache, _html_cache_dir

    # Clear KaTeX inline cache
    import A.core.markdown_html_view as mhv
    mhv._katex_html_cache = None
    mhv._html_cache_dir = None


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


def test_render_markdown_block_math():
    """Test KaTeX block math ($$...$$) is parsed by mistune math plugin."""
    from A.core.markdown_parser import render_markdown

    # Block math requires $$ on their own lines
    result = render_markdown("$$\n\\sum_i u_iA_i = 0\n$$")
    # Mistune math plugin should wrap in div.math
    assert '<div class="math">' in result
    assert "sum_i" in result


def test_render_markdown_inline_math():
    """Test KaTeX inline math ($...$) is parsed by mistune math plugin."""
    from A.core.markdown_parser import render_markdown

    result = render_markdown("Inline math $E = mc^2$ is cool")
    # Mistune math plugin should wrap in span.math
    assert '<span class="math">' in result
    assert "mc^2" in result


def test_generate_html_wrapper_includes_katex():
    """Test HTML wrapper includes KaTeX assets (string or callable)."""
    from A.core.markdown_html_view import _generate_html_wrapper, KATEX_HTML, _katex_html_cache

    # Reset module cache to force CDN fallback in test (no network)
    import A.core.markdown_html_view as mhv
    mhv._katex_html_cache = None

    html = _generate_html_wrapper("<p>Test</p>", title="Test")
    # Should contain either inline CSS/JS or CDN references
    has_cdn = "cdn.jsdelivr.net" in html
    has_inline_style = "<style>" in html and "katex" in html.lower()
    assert has_cdn or has_inline_style, "HTML must contain KaTeX assets (CDN or inline)"
    assert "renderMathInElement" in html


def test_cache_key_includes_version():
    """Test cache key includes version prefix."""
    from A.core.markdown_html_view import CACHE_VERSION, _get_cache_key

    key = _get_cache_key("test content")
    assert key.startswith(f"v{CACHE_VERSION}_")
    assert len(key) > len(f"v{CACHE_VERSION}_")  # Has hash suffix


# ── KaTeX offline / inline tests ─────────────────────────────────────────


def test_katex_html_is_callable():
    """Test KATEX_HTML is a callable function, not a string."""
    from A.core.markdown_html_view import KATEX_HTML
    assert callable(KATEX_HTML)


def test_katex_html_fallback_to_cdn(monkeypatch):
    """Test KATEX_HTML() returns CDN fallback when local files don't exist."""
    from A.core.markdown_html_view import KATEX_HTML, _katex_html_cache, _katex_dir
    import A.core.markdown_html_view as mhv

    # Force CDN fallback by making ensure_katex return False
    mhv._katex_html_cache = None
    monkeypatch.setattr(mhv, "_ensure_katex", lambda: False)

    html = KATEX_HTML()
    assert "cdn.jsdelivr.net" in html
    assert "katex.min.css" in html
    assert "katex.min.js" in html
    assert "auto-render.min.js" in html


def test_katex_html_inline_when_local(monkeypatch, tmp_path):
    """Test KATEX_HTML() inlines content when local KaTeX files exist."""
    from A.core.markdown_html_view import KATEX_HTML, _katex_html_cache, _katex_dir
    import A.core.markdown_html_view as mhv

    # Create fake KaTeX files in the expected cache dir
    kdir = tmp_path / "katex" / "0.16.11"
    kdir.mkdir(parents=True)
    (kdir / "katex.min.css").write_text("/* fake katex css */")
    (kdir / "katex.min.js").write_text("// fake katex js")
    (kdir / "auto-render.min.js").write_text("// fake auto-render")

    mhv._katex_html_cache = None
    monkeypatch.setattr("A.core.paths.cache_dir", lambda: tmp_path)

    html = KATEX_HTML()
    assert "/* fake katex css */" in html
    assert "// fake katex js" in html
    assert "// fake auto-render" in html
    assert "renderMathInElement" in html
    assert "cdn.jsdelivr.net" not in html


def test_ensure_katex_download(monkeypatch, tmp_path):
    """Test ensure_katex downloads and caches files."""
    from A.core.markdown_html_view import ensure_katex, KATEX_HTML, _katex_dir
    import A.core.markdown_html_view as mhv

    mhv._katex_html_cache = None

    # Set up temp KaTeX dir with fake files
    fake_katex_dir = tmp_path / "katex" / "0.16.11"
    monkeypatch.setattr(mhv, "_katex_dir", lambda: fake_katex_dir)

    # Mock _ensure_katex to create files and return True
    def _fake_ensure():
        fake_katex_dir.mkdir(parents=True, exist_ok=True)
        (fake_katex_dir / "katex.min.css").write_text("/* css */")
        (fake_katex_dir / "katex.min.js").write_text("// js")
        (fake_katex_dir / "auto-render.min.js").write_text("// auto-render")
        return True

    monkeypatch.setattr(mhv, "_ensure_katex", _fake_ensure)

    assert ensure_katex() is True

    # Verify files were created
    assert (fake_katex_dir / "katex.min.css").exists()
    assert (fake_katex_dir / "katex.min.js").exists()
    assert (fake_katex_dir / "auto-render.min.js").exists()

    # Verify module cache was populated (KATEX_HTML should now use inline)
    html = KATEX_HTML()
    assert "/* css */" in html
    assert "// js" in html

    # Verify no CDN fallback
    assert "cdn.jsdelivr.net" not in html


def test_render_markdown_math_html_escaping():
    """Test that math content with HTML special chars is properly escaped.

    LaTeX expressions like T_{<l} and alignment markers like & must be
    HTML-escaped in the output so the browser's HTML parser doesn't
    interpret them as tag delimiters or entity references. The browser
    decodes entities back in DOM text nodes, so KaTeX receives correct
    LaTeX.
    """
    from A.core.markdown_parser import render_markdown

    # Block math with < character (e.g. T_{<l} in LaTeX)
    result = render_markdown("$$\nT_{<l}\n$$")
    assert '<div class="math">' in result
    assert "&lt;" in result, (
        "Expected < to be HTML-escaped to &lt; in math content"
    )
    assert "<l" not in result.replace("&lt;", ""), (
        "Unexpected raw < in math HTML output"
    )

    # Block math with > character (e.g. \\tau > 0 in LaTeX)
    result = render_markdown("$$\n\\tau > 0\n$$")
    assert "&gt;" in result, (
        "Expected > to be HTML-escaped to &gt; in math content"
    )

    # Block math with & character (aligned environment)
    result = render_markdown("$$\n\\begin{aligned}\n&\\text{hello}\n\\end{aligned}\n$$")
    assert "&amp;" in result, (
        "Expected & to be HTML-escaped to &amp; in math content"
    )

    # Inline math with <
    result = render_markdown("$T_{<l}$")
    assert '<span class="math">' in result
    assert "&lt;" in result, (
        "Expected < to be HTML-escaped in inline math"
    )


def test_render_markdown_inline_math_spaces():
    """Test inline math with whitespace around $ delimiters.

    The upstream mistune math plugin uses ``\\$(?!\\s)…(?!\\s)\\$`` which
    rejects a space after the opening ``$``. Our override relaxes this
    to ``\\$\\s*…\\s*\\$`` so that ``$ f(x) $`` (common in LaTeX prose)
    is parsed correctly.
    """
    from A.core.markdown_parser import render_markdown

    # Space after opening $ (was rejected by upstream regex)
    result = render_markdown("$ f(a)=f(b) $")
    assert '<span class="math">' in result, (
        "Expected inline math with space after $ to be parsed"
    )
    assert "f(a)=f(b)" in result

    # Space before closing $
    result = render_markdown("$f(a)=f(b) $")
    assert '<span class="math">' in result

    # Spaces both sides
    result = render_markdown("$ f(a)=f(b) $")
    assert '<span class="math">' in result

    # No spaces (should still work)
    result = render_markdown("$f(a)=f(b)$")
    assert '<span class="math">' in result

    # Underscores inside math must NOT be parsed as emphasis
    result = render_markdown("$a_{b}$")
    assert '<span class="math">' in result
    assert "<em>" not in result, (
        "Underscores inside $...$ must not become <em>"
    )

    # Realistic LaTeX fragment with space after $
    result = render_markdown("$ \\text{Let } \\mathbf{x} \\in \\mathbb{R}^d$")
    assert '<span class="math">' in result
    assert "<em>" not in result


def test_ensure_katex_partial_cleanup(monkeypatch, tmp_path):
    """Test partial download failure is handled gracefully."""
    from A.core.markdown_html_view import _ensure_katex
    import A.core.markdown_html_view as mhv

    fake_katex_dir = tmp_path / "katex" / "0.16.11"
    monkeypatch.setattr(mhv, "_katex_dir", lambda: fake_katex_dir)

    # Mock urlretrieve to fail immediately
    def _failing_urlretrieve(url, dest):
        raise OSError("Network error")

    monkeypatch.setattr("urllib.request.urlretrieve", _failing_urlretrieve)

    result = _ensure_katex()
    assert result is False

    # No .part files should remain
    assert list(fake_katex_dir.glob("*.part")) == []


def test_clear_cache_clears_katex(monkeypatch, tmp_path):
    """Test clear_cache also cleans KaTeX downloads."""
    from A.core.markdown_html_view import clear_cache, get_cache_dir, _katex_dir
    import A.core.markdown_html_view as mhv

    monkeypatch.setattr("A.core.paths.cache_dir", lambda: tmp_path)

    # Create some HTML cache files
    (get_cache_dir() / "v3_test.html").write_text("content")

    # Create KaTeX cache
    kdir = _katex_dir()
    kdir.mkdir(parents=True)
    (kdir / "katex.min.css").write_text("/* css */")

    count = clear_cache()
    assert count >= 2  # HTML + KaTeX files

    # Verify cleanup
    assert not (kdir / "katex.min.css").exists()
    assert not kdir.exists()  # Version dir removed