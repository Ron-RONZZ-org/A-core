# -*- coding: utf-8 -*-
"""HTTP utilities for fetching remote content.

Safe by default: SSRF-protected, size-limited, timeout-controlled.

Usage::

    from A.core.http import fetch_text

    try:
        text = fetch_text("https://example.com/page")
    except (ValueError, URLError) as exc:
        error(str(exc))
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

__all__ = ["fetch_text"]

# Private and link-local IP ranges — requests resolving to these are rejected
# to prevent Server-Side Request Forgery (SSRF) attacks.
_PRIVATE_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # private class A
    ipaddress.ip_network("172.16.0.0/12"),      # private class B
    ipaddress.ip_network("192.168.0.0/16"),     # private class C
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("169.254.0.0/16"),     # link-local IPv4
    ipaddress.ip_network("fe80::/10"),          # link-local IPv6
]

_SSRF_MSG = (
    "SSRF blocked: {host} resolves to private/reserved IP {ip}. "
    "Only public http/https URLs are allowed."
)


def _is_private_ip(host: str) -> bool:
    """Check whether *host* is a private or link-local IP address.

    Args:
        host: IP address string (IPv4 or IPv6).

    Returns:
        True if the address falls in a private/reserved range.
    """
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _resolve_host(host: str) -> list[str]:
    """Resolve a hostname to one or more IP address strings.

    Args:
        host: Hostname *or* IP string (e.g. ``"example.com"``, ``"127.0.0.1"``).

    Returns:
        List of unique IP address strings.

    Raises:
        URLError: If DNS resolution fails.
    """
    # Already an IP literal — skip resolution
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass

    try:
        addrs = socket.getaddrinfo(host, 80)
    except OSError as exc:
        raise URLError(f"DNS resolution failed for {host!r}: {exc}") from exc

    # Deduplicate: the same IP may be returned for IPv4 and IPv6
    return list({addr[4][0] for addr in addrs})


def _check_host(host: str) -> None:
    """Validate that *host* does **not** resolve to a private IP.

    Args:
        host: Hostname or IP string.

    Raises:
        ValueError: If the host resolves to a private/reserved IP.
        URLError: If DNS resolution fails.
    """
    ips = _resolve_host(host)
    for ip in ips:
        if _is_private_ip(ip):
            raise ValueError(_SSRF_MSG.format(host=host, ip=ip))


# ── Public API ────────────────────────────────────────────────────────────────


def fetch_text(url: str, *, max_bytes: int = 5_000_000, timeout: int = 15) -> str:
    """Fetch a URL and return its body as decoded text.

    Args:
        url: HTTP or HTTPS URL to fetch.
        max_bytes: Maximum number of bytes to read.  The response is
            truncated (without error) if it exceeds this limit.
        timeout: Request timeout in seconds.

    Returns:
        Decoded text content (UTF-8 by default; falls back to the
        charset declared in the ``Content-Type`` header, then Latin-1).

    Raises:
        ValueError: If the URL scheme is not http/https, or if the
            host resolves to a private / link-local IP (SSRF guard).
        URLError: If the network request fails (DNS, connection
            refused, HTTP error, timeout, etc.).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Blocked URL scheme: {parsed.scheme!r}. "
            f"Only http:// and https:// are allowed."
        )

    host = parsed.hostname
    _check_host(host)

    req = Request(url, headers={"User-Agent": "A-core/1.0 (+https://github.com/Ron-RONZZ-org/A-core)"})
    resp = urlopen(req, timeout=timeout)

    # After possible redirects: validate final resolved IP
    final_url = resp.geturl()
    if final_url != url:
        final_parsed = urlparse(final_url)
        if final_parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Redirect blocked: scheme {final_parsed.scheme!r}. "
                f"Only http/https targets are allowed."
            )
        _check_host(final_parsed.hostname)

    # Binary-content guard: reject trivial binary (null byte in first 4 KB)
    chunk = resp.read(4096)
    if b"\0" in chunk:
        raise ValueError(
            f"URL {url} appears to return binary content (null byte detected). "
            f"Only text content is supported."
        )

    # Read remaining response up to max_bytes
    remaining = max_bytes - len(chunk)
    if remaining > 0:
        chunk += resp.read(remaining)

    raw = chunk[:max_bytes]

    # Decode with charset detection
    charset = resp.headers.get_content_charset()
    if charset:
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            pass

    # Fallback chain
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")
