"""User profile service — load, save, validate, encrypt profile data.

Provides the business-logic layer for the ``uzanto`` CLI, separating
data access, validation, and encryption from command dispatch.

Usage::

    from A.core.uzanto_service import (
        load_profile, save_profile,
        get_master_password, set_master_password, delete_master_password,
        encrypt_profile, decrypt_profile,
        normalize_multi_contact, validate_date,
    )
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from A.core.config import load_config, save_config
from A.core.crypto import encrypt, decrypt
from A.core.keyring import get_password, set_password, delete_password

# ── Constants ─────────────────────────────────────────────────────────────────

_KEYRING_SERVICE = "A-uzanto"
_KEYRING_KEY = "master"
_KEYRING_API_SERVICE = "A-uzanto"
_KEYRING_API_KEY = "huggingface-api-key"

_STANDARD_FIELDS: tuple[str, ...] = (
    "nomo",
    "familia_nomo",
    "naskig_dato",
    "naskig_loko",
    "lingvoj",
    "organizo",
    "organiza_identiga_numero",
    "telefonnumeroj",
    "retposhtadresoj",
    "api_slosilo_huggingface",
)

# ── Profile load / save ──────────────────────────────────────────────────────


def load_profile() -> dict[str, Any]:
    """Load user profile from the ``[uzanto]`` config section.

    Returns:
        Dict of profile fields (may be empty if none configured).
    """
    cfg = load_config()
    # New format: top-level [uzanto] section
    return dict(cfg.module_settings.get("uzanto", {}))


def save_profile(profile: dict[str, Any]) -> None:
    """Persist user profile to the ``[uzanto]`` config section.

    Only touches the ``[uzanto]`` section — does **not** wipe other
    module settings (fixes pre-existing bug that destroyed plugin config).

    Args:
        profile: Dict of profile fields to persist.
    """
    cfg = load_config()
    # Only write to [uzanto] section
    cfg.module_settings["uzanto"] = dict(profile)
    # Clean up any legacy dot-notation keys that were migrated
    for key in list(cfg.settings):
        if key.startswith("uzanto."):
            del cfg.settings[key]
    save_config(cfg)


# ── Master password (system keyring) ─────────────────────────────────────────


def get_master_password() -> str | None:
    """Retrieve master password from system keyring.

    Returns:
        The stored password, or ``None`` if not set or keyring unavailable.
    """
    return get_password(_KEYRING_SERVICE, _KEYRING_KEY)


def set_master_password(password: str) -> bool:
    """Store master password in system keyring.

    Args:
        password: The password to store.

    Returns:
        ``True`` if stored successfully.
    """
    return set_password(_KEYRING_SERVICE, _KEYRING_KEY, password)


def delete_master_password() -> bool:
    """Remove master password from system keyring (idempotent).

    Returns:
        ``True`` if removed or already absent.
    """
    return delete_password(_KEYRING_SERVICE, _KEYRING_KEY)


# ── HuggingFace API key (system keyring) ────────────────────────────────────


def get_huggingface_api_key() -> str | None:
    """Retrieve HuggingFace API key from system keyring.

    Consistent with :func:`A.core.ai.save_api_key`.

    Returns:
        The stored API key, or ``None``.
    """
    return get_password(_KEYRING_API_SERVICE, _KEYRING_API_KEY)


def set_huggingface_api_key(api_key: str) -> bool:
    """Store HuggingFace API key in system keyring.

    Args:
        api_key: The API key to store.

    Returns:
        ``True`` if stored successfully.
    """
    return set_password(_KEYRING_API_SERVICE, _KEYRING_API_KEY, api_key)


def delete_huggingface_api_key() -> bool:
    """Remove HuggingFace API key from system keyring.

    Returns:
        ``True`` if removed or already absent.
    """
    return delete_password(_KEYRING_API_SERVICE, _KEYRING_API_KEY)


# ── Profile encryption / decryption ─────────────────────────────────────────


def encrypt_profile(data: dict[str, Any], password: str) -> bytes:
    """Encrypt profile data with a password (AES-256-GCM).

    Args:
        data: Profile dict to encrypt.
        password: Encryption password.

    Returns:
        Encrypted binary blob.
    """
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return encrypt(plaintext, password)


def decrypt_profile(blob: bytes, password: str) -> dict[str, Any]:
    """Decrypt profile data with a password.

    Args:
        blob: Encrypted binary blob from :func:`encrypt_profile`.
        password: Decryption password.

    Returns:
        Decrypted profile dict.

    Raises:
        ValueError: If the password is wrong or data is corrupt.
    """
    plaintext = decrypt(blob, password)
    return json.loads(plaintext.decode("utf-8"))


# ── Validation ───────────────────────────────────────────────────────────────


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHONE_RE = re.compile(r"^00\d{2,15}\d+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_date(value: str) -> bool:
    """Check whether a string is a valid ``YYYY-MM-DD`` date.

    Args:
        value: Date string to validate.

    Returns:
        ``True`` if the format matches.
    """
    return bool(_DATE_RE.match(value))


def normalize_multi_contact(items: list[str], *, kind: str) -> list[dict[str, Any]]:
    """Parse structured multi-contact items from ``valoro:etikedo:prima`` format.

    Each item follows the legacy autish format::

        value:label:primary

    Only ``value`` is required. When no label is supplied the item is
    marked as primary with label ``"ĉefa"``.

    Args:
        items: List of raw strings in ``valoro:etikedo[:prima]`` format.
        kind: ``"telefono"`` or ``"retposhto"`` — drives format validation.

    Returns:
        List of dicts with keys ``valoro``, ``etikedo``, ``prima``.

    Raises:
        ValueError: If any item fails format or validation rules.
    """
    out: list[dict[str, Any]] = []
    for raw in items:
        parts = [p.strip() for p in raw.split(":")]
        if len(parts) < 1:
            raise ValueError(f"Invalid format: {raw!r}. Expected valoro:etikedo[:prima]")

        value = parts[0]
        if len(parts) == 1:
            etikedo = "ĉefa"
            prima = True
        else:
            etikedo = parts[1]
            prima = len(parts) >= 3 and parts[2].lower() in ("prima", "primary", "1", "jes")

        if kind == "telefono" and not _PHONE_RE.match(value):
            raise ValueError(
                f"Phone number must start with country code (00...): {value!r}"
            )
        elif kind == "retposhto" and not _EMAIL_RE.match(value):
            raise ValueError(f"Invalid email address: {value!r}")

        out.append({"valoro": value, "etikedo": etikedo, "prima": prima})

    # Enforce at most one primary
    primary_indices = [i for i, item in enumerate(out) if item.get("prima")]
    if len(primary_indices) > 1:
        raise ValueError("Only one entry can be marked as primary.")
    if out and not primary_indices:
        out[0]["prima"] = True

    return out


# ── Display helpers ──────────────────────────────────────────────────────────


def display_value(val: object) -> str:
    """Format a profile value for human-readable display.

    Handles lists, dicts, scalars, and URL rendering.

    Args:
        val: Raw profile value.

    Returns:
        Formatted string.
    """
    if val is None:
        return "-"
    if isinstance(val, list):
        parts: list[str] = []
        for item in val:
            if isinstance(item, dict):
                value = str(item.get("valoro", ""))
                tag = str(item.get("etikedo", ""))
                prima = bool(item.get("prima"))
                suffix = " (prima)" if prima else ""
                parts.append(f"{value} ({tag}){suffix}")
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "-"
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def mask_api_key(key: str | None) -> str:
    """Mask an API key for display, showing only the last 4 characters.

    Args:
        key: The API key (or ``None``).

    Returns:
        Masked string like ``"••••abcd"``.
    """
    if not key:
        return "-"
    if len(key) > 4:
        return "••••" + key[-4:]
    return "••••"


__all__ = [
    "load_profile",
    "save_profile",
    "get_master_password",
    "set_master_password",
    "delete_master_password",
    "get_huggingface_api_key",
    "set_huggingface_api_key",
    "delete_huggingface_api_key",
    "encrypt_profile",
    "decrypt_profile",
    "validate_date",
    "normalize_multi_contact",
    "display_value",
    "mask_api_key",
    "_STANDARD_FIELDS",
]
