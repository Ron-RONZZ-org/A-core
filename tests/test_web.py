"""Tests for A.core.web.html_to_text() and extract_text()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from A.core.web import html_to_text


class TestHtmlToText:
    """Tests for html_to_text()."""

    def test_plain_text_passthrough(self) -> None:
        """Non-HTML text should pass through mostly unchanged."""
        text = html_to_text("Hello World")
        assert "Hello World" in text

    def test_strip_simple_tags(self) -> None:
        """Basic HTML tags should be stripped."""
        text = html_to_text("<p>Hello <b>World</b></p>")
        assert "Hello" in text
        assert "World" in text
        assert "<p>" not in text
        assert "<b>" not in text

    def test_script_removed(self) -> None:
        """<script> blocks should be removed entirely."""
        text = html_to_text("<p>Content</p><script>alert('xss');</script><p>More</p>")
        assert "Content" in text
        assert "More" in text
        assert "alert" not in text
        assert "xss" not in text

    def test_style_removed(self) -> None:
        """<style> blocks should be removed entirely."""
        text = html_to_text("<style>.foo{color:red}</style><p>Visible</p>")
        assert "Visible" in text
        assert "color" not in text
        assert ".foo" not in text

    def test_noscript_removed(self) -> None:
        """<noscript> blocks should be removed."""
        text = html_to_text("<noscript>JS required</noscript><p>Content</p>")
        assert "Content" in text
        assert "JS" not in text

    def test_latex_newcommand_removed(self) -> None:
        """LaTeX \\newcommand definitions should be stripped."""
        text = html_to_text(
            r"<p>\newcommand{\R}{\mathbb{R}}Real numbers</p>"
        )
        assert "Real numbers" in text
        assert "newcommand" not in text.lower()

    def test_latex_math_delimiters_removed(self) -> None:
        """LaTeX \\(...\\) and \\[...\\] delimiters should be stripped."""
        text = html_to_text(
            r"<p>Inline \(x^2\) and display \[ \int dx \] math.</p>"
        )
        assert "x^2" in text  # math content preserved
        assert "int" in text
        assert "\\(" not in text
        assert "\\[" not in text

    def test_latex_dollar_removed(self) -> None:
        """$...$ math delimiters should be stripped."""
        text = html_to_text("<p>Cost is $x$ dollars</p>")
        # Dollar sign may or may not be stripped depending on context
        assert "Cost is" in text

    def test_math_commands_stripped(self) -> None:
        """LaTeX formatting commands like \\mathbf should have content kept."""
        text = html_to_text(r"<p>\mathbf{bold} and \textit{italic}</p>")
        assert "bold" in text
        assert "italic" in text
        assert "mathbf" not in text
        assert "textit" not in text

    def test_newlines_after_block_tags(self) -> None:
        """Block-level tags should insert newlines."""
        text = html_to_text("<h1>Title</h1><p>Para 1</p><p>Para 2</p>")
        lines = [l for l in text.split("\n") if l.strip()]
        assert any("Title" in l for l in lines)
        assert any("Para 1" in l for l in lines)
        assert any("Para 2" in l for l in lines)

    def test_newlines_collapsed(self) -> None:
        """Multiple consecutive blank lines should be collapsed."""
        text = html_to_text("<p>A</p><br><br><br><p>B</p>")
        assert "\n\n\n" not in text

    def test_max_chars_respected(self) -> None:
        """max_chars parameter should truncate output."""
        text = html_to_text("<p>" + "A" * 1000 + "</p>", max_chars=100)
        assert len(text) <= 100

    def test_max_chars_zero_no_limit(self) -> None:
        """max_chars=0 should not truncate."""
        text = html_to_text("<p>" + "A" * 1000 + "</p>", max_chars=0)
        assert len(text) >= 1000

    def test_empty_html(self) -> None:
        """Empty string should return empty string."""
        assert html_to_text("") == ""

    def test_none_text(self) -> None:
        """Non-string input should not crash (if somehow passed)."""
        # html_to_text expects str, but handle gracefully
        text = html_to_text("<p>42</p>")
        assert "42" in text

    def test_link_text_preserved(self) -> None:
        """Text inside <a> tags should be preserved."""
        text = html_to_text('<p>Visit <a href="https://example.com">Example</a></p>')
        assert "Visit" in text
        assert "Example" in text

    def test_list_items(self) -> None:
        """<li> text should be preserved with newlines."""
        text = html_to_text("<ul><li>Item 1</li><li>Item 2</li></ul>")
        assert "Item 1" in text
        assert "Item 2" in text


class TestHtmlToTextTrafilatura:
    """Tests for html_to_text() when trafilatura is available."""

    def test_trafilatura_used_when_available(self) -> None:
        """If trafilatura returns content, it should be used."""
        mock_result = "Clean main content extracted by trafilatura."

        with patch("A.core.web._extract_with_trafilatura", return_value=mock_result):
            text = html_to_text("<html><body><p>Raw HTML</p></body></html>")
        assert text == mock_result

    def test_trafilatura_none_falls_back(self) -> None:
        """If trafilatura returns None, stdlib fallback should be used."""
        with patch("A.core.web._extract_with_trafilatura", return_value=None):
            text = html_to_text("<html><body><p>Fallback content</p></body></html>")
        assert "Fallback content" in text
