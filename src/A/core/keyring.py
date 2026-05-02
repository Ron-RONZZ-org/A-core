"""Keyring abstraction for secure credential storage.

Wraps the ``keyring`` library with graceful fallback when unavailable.
Designed as a pair to ``crypto.py`` — keyring handles OS-level credential
storage, crypto handles user-managed encryption.

Usage::

    from A.core.keyring import get_password, set_password, delete_password

    set_password("myapp/db", "password", "sekret123")
    pw = get_password("myapp/db", "password")
    delete_password("myapp/db", "password")
"""

from __future__ import annotations


def _keyring_available() -> bool:
    """Check if the keyring library is available at call time."""
    try:
        import keyring  # noqa: F401
        return True
    except ImportError:
        return False


def get_password(service: str, key: str) -> str | None:
    """Retrieve a password from the system keyring.

    Args:
        service: Service name (e.g. ``"A-lien/{account_uuid}"``)
        key: Key within the service (e.g. ``"password"``)

    Returns:
        The stored password, or ``None`` if not found or keyring unavailable
    """
    if not _keyring_available():
        return None
    try:
        import keyring
        return keyring.get_password(service, key)
    except Exception:  # pragma: no cover
        return None


def set_password(service: str, key: str, password: str) -> bool:
    """Store a password in the system keyring.

    Args:
        service: Service name
        key: Key within the service
        password: The password to store

    Returns:
        ``True`` if stored successfully, ``False`` if keyring unavailable
    """
    if not _keyring_available():
        return False
    try:
        import keyring
        keyring.set_password(service, key, password)
        return True
    except Exception:  # pragma: no cover
        return False


def delete_password(service: str, key: str) -> bool:
    """Remove a password from the system keyring.

    Idempotent — returns ``True`` even if the entry does not exist.

    Args:
        service: Service name
        key: Key within the service

    Returns:
        ``True`` if deleted (or not found), ``False`` if keyring unavailable
    """
    if not _keyring_available():
        return False
    try:
        import keyring
        keyring.delete_password(service, key)
        return True
    except keyring.errors.PasswordDeleteError:
        return True  # Already gone — idempotent
    except Exception:  # pragma: no cover
        return False


__all__ = [
    "get_password",
    "set_password",
    "delete_password",
]
