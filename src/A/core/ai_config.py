"""LLM provider configuration — shared SQLite-backed storage for A-extensions.

Provides a single source of truth for LLM provider settings (provider type,
profile, model, base URL, priority) that both A-agento and A-kunpiloto
(and future modules) use. API keys remain in the system keyring.

Schema matches A-agento's ``provizanto_agordoj`` table for seamless migration.

Usage::

    from A.core.ai_config import save_provider_config, get_configured_provider

    # Configure a provider
    save_provider_config("openai", profile="work", modelo="gpt-4")

    # Auto-discover provider (fallback order)
    provider = get_configured_provider()

    # Explicit provider
    provider = get_configured_provider("deepseek")
    provider = get_configured_provider("openai:work")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from A.data.base import SQLiteDB
from A.core.paths import data_dir


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

PROVIDER_CONFIG_SCHEMA = {
    "provizanto_agordoj": """
        CREATE TABLE IF NOT EXISTS provizanto_agordoj (
            uuid TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT 'default',
            noto TEXT DEFAULT '',
            modelo TEXT DEFAULT '',
            base_url TEXT DEFAULT '',
            prioritato INTEGER NOT NULL DEFAULT 0,
            kreita_je TEXT NOT NULL,
            modifita_je TEXT NOT NULL,
            UNIQUE(provider, profile)
        )
    """,
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProviderConfig:
    """Full metadata for one provider configuration profile.

    Attributes:
        uuid: Unique identifier.
        provider: Provider type ("openai", "deepseek", "ollama", etc.).
        profile: Named profile ("default", "work", "personal").
        noto: User-friendly label.
        modelo: Model name override (empty = provider default).
        base_url: Custom API base URL (empty = provider default).
        prioritato: Priority (lower = tried first in fallback).
        kreita_je: Creation timestamp (ISO 8601).
        modifita_je: Last modification timestamp (ISO 8601).
    """
    uuid: str
    provider: str
    profile: str
    noto: str
    modelo: str
    base_url: str
    prioritato: int
    kreita_je: str
    modifita_je: str


# ---------------------------------------------------------------------------
# Database singleton
# ---------------------------------------------------------------------------

_db: SQLiteDB | None = None


def _get_db() -> SQLiteDB:
    """Get the providers database singleton.

    Returns:
        SQLiteDB instance for ``providers.db``.
    """
    global _db
    if _db is None:
        path = data_dir() / "providers.db"
        _db = SQLiteDB(path, schema=PROVIDER_CONFIG_SCHEMA, module="core")
        # One-shot migration from A-agento
        _ensure_schema()
    return _db


def _ensure_schema() -> None:
    """Create table if missing; auto-migrate from A-agento on first run."""
    db = _get_db()
    count = db.execute_one("SELECT COUNT(*) AS c FROM provizanto_agordoj")
    if count and count["c"] == 0:
        _migrate_from_agento(db)


def _migrate_from_agento(db: SQLiteDB) -> int:
    """Copy provider configs from A-agento's database.

    Called once on first access if the providers table is empty.

    Args:
        db: The providers database.

    Returns:
        Number of rows migrated.
    """
    try:
        from A_agento.data.storage import get_db as get_agento_db
    except ImportError:
        return 0  # A-agento not installed

    try:
        agento = get_agento_db()
        rows = agento.execute("SELECT * FROM provizanto_agordoj")
    except Exception:
        return 0

    if not rows:
        return 0

    count = 0
    for row in rows:
        try:
            db.execute(
                """INSERT OR IGNORE INTO provizanto_agordoj
                   (uuid, provider, profile, noto, modelo, base_url,
                    prioritato, kreita_je, modifita_je)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["uuid"], row["provider"], row["profile"],
                 row["noto"], row["modelo"], row["base_url"],
                 row["prioritato"], row["kreita_je"], row["modifita_je"]),
            )
            count += 1
        except Exception:
            continue
    return count


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def save_provider_config(
    provider: str,
    profile: str = "default",
    noto: str = "",
    modelo: str = "",
    base_url: str = "",
    prioritato: int | None = None,
) -> ProviderConfig:
    """Save or update a provider configuration.

    Provider name is normalized to lowercase. If *prioritato* is None
    on a new entry, it gets ``0`` (highest priority) and existing
    entries are shifted by +1.

    Args:
        provider: Provider type name ("openai", "deepseek", "ollama").
        profile: Profile name ("default", "work", "personal").
        noto: User-friendly label.
        modelo: Model name override.
        base_url: Custom API base URL.
        prioritato: Priority value (lower = tried first). Auto-assigned
                    if None and entry is new.

    Returns:
        The saved ProviderConfig.
    """
    provider = provider.lower()
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    existing = get_provider_config(provider, profile)
    if existing:
        if prioritato is None:
            prioritato = existing.prioritato
        db.execute(
            """UPDATE provizanto_agordoj
               SET noto = ?, modelo = ?, base_url = ?,
                   prioritato = ?, modifita_je = ?
               WHERE uuid = ?""",
            (noto, modelo, base_url, prioritato, now, existing.uuid),
        )
        return ProviderConfig(
            uuid=existing.uuid,
            provider=provider,
            profile=profile,
            noto=noto,
            modelo=modelo,
            base_url=base_url,
            prioritato=prioritato,
            kreita_je=existing.kreita_je,
            modifita_je=now,
        )

    if prioritato is None:
        db.execute("UPDATE provizanto_agordoj SET prioritato = prioritato + 1")
        prioritato = 0

    entry_uuid = str(uuid4())
    db.execute(
        """INSERT INTO provizanto_agordoj
           (uuid, provider, profile, noto, modelo, base_url,
            prioritato, kreita_je, modifita_je)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_uuid, provider, profile, noto, modelo,
         base_url, prioritato, now, now),
    )
    return ProviderConfig(
        uuid=entry_uuid,
        provider=provider,
        profile=profile,
        noto=noto,
        modelo=modelo,
        base_url=base_url,
        prioritato=prioritato,
        kreita_je=now,
        modifita_je=now,
    )


def get_provider_config(
    provider: str,
    profile: str = "default",
) -> ProviderConfig | None:
    """Get a provider configuration by type and profile.

    Args:
        provider: Provider type name.
        profile: Profile name.

    Returns:
        ProviderConfig or None.
    """
    db = _get_db()
    row = db.execute_one(
        "SELECT * FROM provizanto_agordoj WHERE provider = ? AND profile = ?",
        (provider, profile),
    )
    return _row_to_config(row)


def get_provider_config_by_uuid(uuid: str) -> ProviderConfig | None:
    """Get a provider configuration by UUID (supports prefix matching).

    Args:
        uuid: Full UUID or prefix (at least 8 hex chars).

    Returns:
        ProviderConfig or None.
    """
    db = _get_db()
    row = db.execute_one(
        "SELECT * FROM provizanto_agordoj WHERE uuid LIKE ?",
        (f"{uuid}%",),
    )
    return _row_to_config(row)


def list_provider_configs() -> list[ProviderConfig]:
    """List all provider configurations ordered by priority.

    Returns:
        List of ProviderConfig sorted by prioritato ASC, kreita_je DESC.
    """
    db = _get_db()
    rows = db.execute(
        "SELECT * FROM provizanto_agordoj ORDER BY prioritato ASC, kreita_je DESC",
    )
    return [_row_to_config(r) for r in rows if r]


def delete_provider_config(
    provider: str | None = None,
    profile: str = "default",
    uuid: str | None = None,
) -> bool:
    """Delete a provider configuration.

    Deletes by UUID if provided, otherwise by provider+profile.
    Does NOT remove the API key from the system keyring.

    Args:
        provider: Provider type name (required if uuid not given).
        profile: Profile name.
        uuid: Entry UUID (alternative to provider+profile).

    Returns:
        True if deleted, False if not found.
    """
    db = _get_db()
    if uuid:
        existing = db.execute_one(
            "SELECT 1 FROM provizanto_agordoj WHERE uuid = ?", (uuid,),
        )
        if existing is None:
            return False
        db.execute("DELETE FROM provizanto_agordoj WHERE uuid = ?", (uuid,))
        return True

    existing = db.execute_one(
        "SELECT 1 FROM provizanto_agordoj WHERE provider = ? AND profile = ?",
        (provider, profile),
    )
    if existing is None:
        return False
    db.execute(
        "DELETE FROM provizanto_agordoj WHERE provider = ? AND profile = ?",
        (provider, profile),
    )
    return True


# ---------------------------------------------------------------------------
# Reference parsing
# ---------------------------------------------------------------------------


def parse_ref(ref: str) -> tuple[str | None, str | None, str | None]:
    """Parse a provider reference into (uuid, provider, profile).

    Accepts:
    - UUID (full, 36-char with hyphens, or 8+ hex chars)
    - ``provider:profile`` (e.g. "openai:work")
    - Bare provider name (e.g. "openai")

    Args:
        ref: The reference string.

    Returns:
        Tuple of (uuid, provider, profile). Exactly two will be None.
    """
    stripped = ref.strip()
    if len(stripped) == 36 and stripped.count("-") == 4:
        return (stripped, None, None)
    if 8 <= len(stripped) <= 32 and all(c in "0123456789abcdef" for c in stripped.lower()):
        return (stripped, None, None)
    if ":" in stripped:
        parts = stripped.split(":", 1)
        return (None, parts[0], parts[1])
    return (None, stripped, None)


def find_config(ref: str) -> ProviderConfig | None:
    """Find a provider config by UUID, provider, or ``provider:profile``.

    If the ref looks like a UUID but no config matches, falls back to
    looking it up as a provider name.

    Args:
        ref: Reference string (UUID, provider name, or provider:profile).

    Returns:
        ProviderConfig or None.
    """
    uuid, provider, profile = parse_ref(ref)
    if uuid:
        config = get_provider_config_by_uuid(uuid)
        if config:
            return config
        return get_provider_config(ref, profile or "default")
    if provider:
        return get_provider_config(provider, profile or "default")
    return None


# ---------------------------------------------------------------------------
# Fallback / auto-discovery
# ---------------------------------------------------------------------------


def get_fallback_order() -> list[str]:
    """Get unique provider types ordered by fallback priority.

    Returns:
        List of provider type names (e.g. ``["deepseek", "openai"]``),
        ordered by prioritato ASC, kreita_je DESC.
    """
    configs = list_provider_configs()
    seen: set[str] = set()
    ordered: list[str] = []
    for c in configs:
        pt = c.provider.lower()
        if pt and pt not in seen:
            seen.add(pt)
            ordered.append(pt)
    return ordered


def get_provider_with_fallback(**kwargs: Any) -> Any:
    """Get an LLM provider, trying configured providers in priority order.

    Tries each configured provider type in ``prioritato`` order.
    Skips providers without an available API key.

    Args:
        **kwargs: Passed to the provider constructor.

    Returns:
        LLMProvider instance.

    Raises:
        ValueError: If no provider with an available key is configured.
    """
    from A.core.ai import get_provider as _construct
    from A.core.providers import _resolve_api_key

    order = get_fallback_order()
    for pt in order:
        if pt == "ollama" or _resolve_api_key(pt):
            try:
                return _construct(pt, **kwargs)
            except Exception:
                continue

    raise ValueError(
        "No LLM providers configured. "
        "Run `A agento agordi aldoni` to add one, "
        "or use --provizanto to specify one directly."
    )


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def get_configured_provider(
    ref: str | None = None,
    **kwargs: Any,
) -> Any:
    """Resolve a provider reference to an ``LLMProvider`` instance.

    Resolution order:
    1. If *ref* is ``None`` → try fallback order (prioritato-based).
    2. If *ref* is a bare provider name → construct directly.
    3. If *ref* is UUID or ``provider:profile`` → lookup config and construct.

    Args:
        ref: ``None`` (auto-fallback), provider name (``"openai"``),
             ``provider:profile`` (``"openai:work"``), or UUID.
        **kwargs: Passed to the provider constructor (model, temperature, etc.).

    Returns:
        ``LLMProvider`` instance.

    Raises:
        ValueError: If no provider can be resolved.
    """
    from A.core.ai import get_provider as _construct
    from A.core.providers import OpenAICompatibleProvider, OllamaProvider
    from A.core.ai import get_api_key

    if ref is None:
        return get_provider_with_fallback(**kwargs)

    uuid, p_name, profile = parse_ref(ref)

    # Bare provider name — construct directly
    if p_name and not profile and not uuid:
        try:
            return _construct(p_name, **kwargs)
        except ValueError:
            raise ValueError(f"Unknown provider: {p_name}")

    # UUID or provider:profile — need config lookup
    config = find_config(ref)
    if config is None:
        raise ValueError(f"No provider config found for '{ref}'")

    pt = config.provider
    api_key = get_api_key(provider=pt, profile=config.profile)

    # Filter kwargs: remove keys consumed by us
    model = config.modelo or kwargs.get("model")
    base_url = config.base_url or kwargs.get("base_url")
    provider_kwargs = {k: v for k, v in kwargs.items()
                       if k not in ("model", "base_url", "api_key")}

    if pt == "ollama":
        return OllamaProvider(
            model=model or "llama2",
            base_url=base_url or "http://localhost:11434",
            **provider_kwargs,
        )

    return OpenAICompatibleProvider(
        provider_type=pt,
        api_key=api_key,
        model=model,
        base_url=base_url,
        **provider_kwargs,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_config(row: Any) -> ProviderConfig | None:
    """Convert a SQLite row dict to a ProviderConfig dataclass.

    Args:
        row: A SQLite row dict, or None.

    Returns:
        ProviderConfig or None.
    """
    if row is None:
        return None
    return ProviderConfig(
        uuid=row["uuid"],
        provider=row["provider"],
        profile=row["profile"],
        noto=row.get("noto", ""),
        modelo=row.get("modelo", ""),
        base_url=row.get("base_url", ""),
        prioritato=row["prioritato"],
        kreita_je=row["kreita_je"],
        modifita_je=row["modifita_je"],
    )
