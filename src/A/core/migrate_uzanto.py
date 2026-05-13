"""Migration: import user profile from autish-legacy to A-core config.

Reads ``~/.local/share/autish/uzanto_profilo.toml`` and writes language
and profile fields to ``~/.config/A/config.toml``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from A.core.config import load_config, save_config
from A.core.migration import register_migration, MigrationResult

_LEGACY_PROFILE = Path.home() / ".local" / "share" / "autish" / "uzanto_profilo.toml"

# Fields to migrate from legacy profile to A-core config settings
_MIGRATE_FIELDS: tuple[str, ...] = (
    "nomo", "familia_nomo", "naskig_dato", "naskig_loko",
    "lingvoj", "organizo", "telefonnumeroj", "retposhtadresoj",
)


def _migrate_uzanto() -> MigrationResult:
    """Import user profile from autish-legacy to A-core config."""
    errors: list[str] = []
    source_rows = 0
    migrated_rows = 0

    if not _LEGACY_PROFILE.exists():
        return MigrationResult(
            module="A-core",
            source_db="uzanto_profilo.toml",
            target_table="config",
            source_rows=0,
            migrated_rows=0,
            skipped=True,
            skipped_reason=f"Ne trovita: {_LEGACY_PROFILE}",
        )

    try:
        raw = _LEGACY_PROFILE.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        source_rows = len(data)
    except Exception as e:
        return MigrationResult(
            module="A-core",
            source_db="uzanto_profilo.toml",
            target_table="config",
            source_rows=1,
            migrated_rows=0,
            errors=[str(e)],
        )

    try:
        cfg = load_config()
        changed = False

        # Migrate language (lingvo in config.toml)
        legacy_lang = data.get("lingvo") or data.get("language", "")
        if legacy_lang and isinstance(legacy_lang, str):
            cfg.language = legacy_lang.lower()[:2]
            changed = True
            migrated_rows += 1

        # Migrate profile fields into settings
        for field in _MIGRATE_FIELDS:
            val = data.get(field)
            if val is not None:
                cfg.settings[field] = val
                changed = True
                migrated_rows += 1

        if changed:
            save_config(cfg)
    except Exception as e:
        errors.append(str(e))

    return MigrationResult(
        module="A-core",
        source_db="uzanto_profilo.toml",
        target_table="config",
        source_rows=source_rows,
        migrated_rows=migrated_rows,
        errors=errors,
    )


def register() -> None:
    """Register the uzanto migration."""
    register_migration("A-core", "uzanto_profilo.toml", "config", _migrate_uzanto)
