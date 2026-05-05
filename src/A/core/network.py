"""Network connection error classification and formatting.

Provides a single function ``format_connection_error()`` that classifies
socket-level errors into user-friendly i18n messages with remediation
suggestions.

Usage::

    from A.core.network import format_connection_error

    try:
        connect_to_server()
    except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
        raise ConnectionError(
            format_connection_error(e, host, port, "IMAP")
        ) from e
"""

from __future__ import annotations

import socket
import ssl
from typing import Any

from A.core.i18n import tr_multi


def format_connection_error(
    exc: BaseException,
    host: str,
    port: int,
    service_label: str = "Servilo",
) -> str:
    """Classify a socket-level error and return a localized message.

    Detects DNS failures, connection refused, timeouts, SSL errors,
    and other socket errors — each with a human-readable message
    including remediation suggestions.

    Args:
        exc: The exception raised during connection attempt.
        host: Server hostname that was being connected to.
        port: Server port that was being connected to.
        service_label: Short label for the service type
            (e.g. "IMAP", "SMTP", "Sieve"). Displayed in the
            generic fallback message. Use Esperanto nominative.

    Returns:
        Localized error message string (via ``tr_multi``).
    """
    msg_lower = str(exc).lower()

    # DNS resolution failure
    if isinstance(exc, socket.gaierror) or "name or service not known" in msg_lower:
        return tr_multi(
            f"Ne eblas rezolvi la gastigantan nomon {host}.\n"
            f"Kontrolu vian interretan konekton kaj la DNS-agordojn.",
            f"Could not resolve hostname {host}.\n"
            f"Check your internet connection and DNS settings.",
            f"Impossible de résoudre le nom d'hôte {host}.\n"
            f"Vérifiez votre connexion internet et les paramètres DNS.",
        )

    # Connection refused (port not listening, server down)
    if isinstance(exc, ConnectionRefusedError) or "connection refused" in msg_lower:
        return tr_multi(
            f"Konekto rifuzita de {host}:{port}.\n"
            f"Kontrolu ĉu la servilo funkcias kaj la haveno estas ĝusta.",
            f"Connection refused by {host}:{port}.\n"
            f"Verify the server is running and the port is correct.",
            f"Connexion refusée par {host}:{port}.\n"
            f"Vérifiez que le serveur fonctionne et que le port est correct.",
        )

    # Timeout
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timed out" in msg_lower:
        return tr_multi(
            f"Konekto al {host}:{port} eltempiĝis.\n"
            f"Kontrolu vian retkonekton, fajromuron kaj havenon.",
            f"Connection to {host}:{port} timed out.\n"
            f"Check your internet connection, firewall, and port settings.",
            f"La connexion à {host}:{port} a expiré.\n"
            f"Vérifiez votre connexion internet, le pare-feu et le port.",
        )

    # SSL/TLS negotiation failure
    if isinstance(exc, ssl.SSLError) or any(
        t in msg_lower for t in ("ssl", "tls", "certificate verify",
                                 "certificate", "handshake")
    ):
        return tr_multi(
            f"SSL/TLS-eraro dum konekto al {host}:{port}.\n"
            f"Kontrolu la SSL-agordojn de via retpoŝta provizanto.",
            f"SSL/TLS error connecting to {host}:{port}.\n"
            f"Check your email provider's SSL settings.",
            f"Erreur SSL/TLS lors de la connexion à {host}:{port}.\n"
            f"Vérifiez les paramètres SSL de votre fournisseur de messagerie.",
        )

    # Generic fallback with host info
    return tr_multi(
        f"{service_label}-konekto malsukcesis al {host}:{port} — {exc}",
        f"{service_label} connection failed to {host}:{port} — {exc}",
        f"Échec de connexion {service_label} à {host}:{port} — {exc}",
    )


__all__ = [
    "format_connection_error",
]
