"""Tests for A.core.http.fetch_text() — SSRF protection & URL fetching."""

from __future__ import annotations

import socket
from unittest.mock import patch, MagicMock
from urllib.error import URLError

import pytest

from A.core.http import fetch_text, _is_private_ip, _resolve_host, _check_host


# ── _is_private_ip ────────────────────────────────────────────────────────────


class TestIsPrivateIp:
    def test_loopback_v4(self) -> None:
        assert _is_private_ip("127.0.0.1") is True

    def test_loopback_v6(self) -> None:
        assert _is_private_ip("::1") is True

    def test_private_10(self) -> None:
        assert _is_private_ip("10.0.0.1") is True

    def test_private_172(self) -> None:
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.31.255.255") is True

    def test_private_192(self) -> None:
        assert _is_private_ip("192.168.1.1") is True

    def test_link_local_v4(self) -> None:
        assert _is_private_ip("169.254.1.1") is True

    def test_link_local_v6(self) -> None:
        assert _is_private_ip("fe80::1") is True

    def test_public_ip(self) -> None:
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("93.184.216.34") is False

    def test_invalid_string(self) -> None:
        assert _is_private_ip("not-an-ip") is False


# ── _resolve_host ─────────────────────────────────────────────────────────────


class TestResolveHost:
    def test_ip_literal(self) -> None:
        assert _resolve_host("8.8.8.8") == ["8.8.8.8"]

    def test_ip_literal_private(self) -> None:
        assert _resolve_host("127.0.0.1") == ["127.0.0.1"]

    def test_hostname_resolves(self) -> None:
        ips = _resolve_host("example.com")
        assert isinstance(ips, list)
        assert len(ips) >= 1
        # Should not be private
        for ip in ips:
            assert _is_private_ip(ip) is False

    def test_nonexistent_hostname(self) -> None:
        with pytest.raises(URLError):
            _resolve_host("this-domain-does-not-exist-xyz123.test")


# ── _check_host ───────────────────────────────────────────────────────────────


class TestCheckHost:
    def test_public_ip_ok(self) -> None:
        # Should not raise
        _check_host("8.8.8.8")

    def test_public_hostname_ok(self) -> None:
        _check_host("example.com")

    def test_loopback_raises(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            _check_host("127.0.0.1")

    def test_private_raises(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            _check_host("10.0.0.5")

    def test_localhost_raises(self) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            _check_host("127.0.0.2")


# ── fetch_text: scheme validation ─────────────────────────────────────────────


class TestFetchTextScheme:
    def test_file_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            fetch_text("file:///etc/passwd")

    def test_ftp_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            fetch_text("ftp://example.com/file")

    def test_empty_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            fetch_text("localhost:8080")


# ── fetch_text: SSRF (mock to avoid actual DNS/network) ─────────────────────


class TestFetchTextSsrf:
    @patch("A.core.http.urlopen")
    def test_localhost_url_raises(self, mock_urlopen: MagicMock) -> None:
        """fetch_text should reject localhost before making any request."""
        with pytest.raises(ValueError, match="SSRF blocked"):
            fetch_text("http://127.0.0.1:11434")  # Ollama
        mock_urlopen.assert_not_called()

    @patch("A.core.http.urlopen")
    def test_private_ip_url_raises(self, mock_urlopen: MagicMock) -> None:
        with pytest.raises(ValueError, match="SSRF blocked"):
            fetch_text("http://192.168.1.1/admin")
        mock_urlopen.assert_not_called()


# ── fetch_text: successful request ────────────────────────────────────────────


class TestFetchTextSuccess:
    @pytest.mark.skip(reason="Network-dependent — run manually")
    def test_fetch_example_com(self) -> None:
        text = fetch_text("https://example.com/")
        assert "Example Domain" in text
        assert len(text) > 50

    def test_mocked_success(self) -> None:
        """Test with mocked urlopen to avoid network."""
        mock_resp = MagicMock()
        # First read(4096) returns content, second read(remaining) returns empty
        mock_resp.read.side_effect = [b"Hello, World!", b""]
        mock_resp.geturl.return_value = "https://example.com"
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.headers.get.return_value = "text/plain"

        with patch("A.core.http.urlopen", return_value=mock_resp):
            text = fetch_text("https://example.com/hello")
        assert text == "Hello, World!"

    def test_mocked_binary_rejected(self) -> None:
        """Null byte in first 4KB should raise."""
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"\x89PNG\r\n\x1a\n\x00", b""]
        mock_resp.geturl.return_value = "https://example.com/image.png"
        mock_resp.headers.get.return_value = "application/octet-stream"

        with patch("A.core.http.urlopen", return_value=mock_resp):
            with pytest.raises(ValueError, match="binary"):
                fetch_text("https://example.com/image.png")


# ── fetch_text: size limit ────────────────────────────────────────────────────


class TestFetchTextSizeLimit:
    def test_truncation(self) -> None:
        """Content exceeding max_bytes should be truncated."""
        big_content = b"A" * 10_000

        mock_resp = MagicMock()
        # First read(4096) returns initial chunk, second read returns remainder
        mock_resp.read.side_effect = [big_content[:4096], big_content[4096:4096+500]]
        mock_resp.geturl.return_value = "https://example.com/big"
        mock_resp.headers.get.return_value = "text/plain"
        mock_resp.headers.get_content_charset.return_value = "utf-8"

        with patch("A.core.http.urlopen", return_value=mock_resp):
            text = fetch_text("https://example.com/big", max_bytes=500)
        assert len(text) == 500
        assert text == "A" * 500


# ── fetch_text: redirect handling ─────────────────────────────────────────────


class TestFetchTextRedirect:
    def test_redirect_to_public_ok(self) -> None:
        """Redirect to a public URL should work."""
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"Redirected content", b""]
        mock_resp.geturl.return_value = "https://final.example.com"
        mock_resp.headers.get.return_value = "text/plain"
        mock_resp.headers.get_content_charset.return_value = "utf-8"

        with (
            patch("A.core.http.urlopen", return_value=mock_resp),
            patch("A.core.http._check_host") as mock_check,
        ):
            text = fetch_text("https://example.com/redirect")
        assert text == "Redirected content"
        # _check_host should be called twice: once for original, once for redirect
        assert mock_check.call_count == 2

    def test_redirect_to_file_scheme_rejected(self) -> None:
        """Redirect to file:// should be rejected."""
        mock_resp = MagicMock()
        mock_resp.geturl.return_value = "file:///etc/passwd"

        with patch("A.core.http.urlopen", return_value=mock_resp):
            with pytest.raises(ValueError, match="Redirect blocked"):
                fetch_text("https://example.com/evil-redirect")
