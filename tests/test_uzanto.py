"""Tests for uzanto: config fix, service layer, and CLI commands."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from typer.testing import CliRunner

from A.core.testing import patch_paths

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect filesystem for every test; mock keyring module broadly."""
    patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("A.core.keyring.get_password", MagicMock(return_value=None))
    monkeypatch.setattr("A.core.keyring.set_password", MagicMock(return_value=True))
    monkeypatch.setattr("A.core.keyring.delete_password", MagicMock(return_value=True))


@pytest.fixture
def uzanto_app():
    """Import the uzanto Typer app (lazy import to avoid side effects)."""
    from A.core.uzanto_cli import app
    return app


@pytest.fixture(autouse=True)
def set_language_to_eo(monkeypatch):
    """Run CLI tests with Esperanto language for stable assertions."""
    from A.core import i18n
    i18n.set_language("eo")


# ═══════════════════════════════════════════════════════════════════════════════
# config.py — save_config() fix for settings dict
# ═══════════════════════════════════════════════════════════════════════════════


def test_save_config_preserves_settings_dict():
    """save_config() must persist a non-empty settings dict."""
    from A.core.config import load_config, save_config

    cfg = load_config()
    cfg.settings["nomo"] = "Alice"
    cfg.settings["aktivigo"] = True
    cfg.settings["kalkulo"] = 42
    save_config(cfg)

    reloaded = load_config()
    assert reloaded.settings.get("nomo") == "Alice"
    assert reloaded.settings.get("aktivigo") is True
    assert reloaded.settings.get("kalkulo") == 42


def test_save_config_preserves_nested_settings():
    """save_config() must persist lists and dicts inside settings."""
    from A.core.config import load_config, save_config

    cfg = load_config()
    cfg.settings["lingvoj"] = ["eo", "en", "fr"]
    cfg.settings["kontakto"] = {"telefono": "+123", "reta": "a@b.com"}
    save_config(cfg)

    reloaded = load_config()
    assert reloaded.settings.get("lingvoj") == ["eo", "en", "fr"]
    assert reloaded.settings.get("kontakto") == {"telefono": "+123", "reta": "a@b.com"}


def test_save_config_roundtrip_empty_settings():
    """save_config() with empty settings dict must not error."""
    from A.core.config import load_config, save_config

    cfg = load_config()
    save_config(cfg)

    reloaded = load_config()
    assert isinstance(reloaded.settings, dict)
    assert len(reloaded.settings) == 0


def test_save_config_combined_fields():
    """save_config() persists top-level fields alongside settings."""
    from A.core.config import load_config, save_config

    cfg = load_config()
    cfg.language = "fr"
    cfg.verbose = True
    cfg.plugins = ["tempo", "vorto"]
    cfg.aliases = {"g": "vorto serchi"}
    cfg.settings["temo"] = "test"
    save_config(cfg)

    reloaded = load_config()
    assert reloaded.language == "fr"
    assert reloaded.verbose is True
    assert "tempo" in reloaded.plugins
    assert reloaded.aliases.get("g") == "vorto serchi"
    assert reloaded.settings.get("temo") == "test"


# ═══════════════════════════════════════════════════════════════════════════════
# config.py — module-name.key convention
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_module_setting_default():
    """get_module_setting returns default for missing key."""
    from A.core.config import get_module_setting
    assert get_module_setting("nonexistent", "key", "fallback") == "fallback"


def test_set_then_get_module_setting():
    """set_module_setting persists and get_module_setting retrieves."""
    from A.core.config import get_module_setting, set_module_setting

    set_module_setting("filmeto", "default_output", "/tmp/videos")
    assert get_module_setting("filmeto", "default_output") == "/tmp/videos"


def test_module_setting_roundtrip_through_config():
    """Module settings survive a full load/save roundtrip."""
    from A.core.config import load_config, save_config, get_module_setting, set_module_setting

    set_module_setting("vorto", "max_results", 50)
    set_module_setting("filmeto", "default_output", "/path")

    cfg = load_config()
    # New format: stored in top-level [module] sections
    assert cfg.module_settings["vorto"]["max_results"] == 50
    assert cfg.module_settings["filmeto"]["default_output"] == "/path"
    # Legacy flat keys should have been cleaned up
    assert "vorto.max_results" not in cfg.settings
    assert "filmeto.default_output" not in cfg.settings

    # Full roundtrip
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.module_settings["vorto"]["max_results"] == 50
    assert reloaded.module_settings["filmeto"]["default_output"] == "/path"


# ═══════════════════════════════════════════════════════════════════════════════
# config.py — get_setting / set_setting helpers
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_setting_default():
    """get_setting returns default for missing key."""
    from A.core.config import get_setting
    assert get_setting("nonexistent", "fallback") == "fallback"


def test_get_setting_after_set():
    """set_setting persists and get_setting retrieves."""
    from A.core.config import get_setting, set_setting

    set_setting("uzanto.nomo", "Bob")
    assert get_setting("uzanto.nomo") == "Bob"


# ═══════════════════════════════════════════════════════════════════════════════
# uzanto_service.py — profile load / save
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_profile_empty():
    """load_profile returns empty dict when no profile stored."""
    from A.core.uzanto_service import load_profile
    prof = load_profile()
    assert isinstance(prof, dict)
    assert len(prof) == 0


def test_save_then_load_profile():
    """save_profile followed by load_profile returns same data."""
    from A.core.uzanto_service import load_profile, save_profile

    data = {"nomo": "Alice", "lingvoj": ["eo", "en"]}
    save_profile(data)
    reloaded = load_profile()
    assert reloaded["nomo"] == "Alice"
    assert reloaded["lingvoj"] == ["eo", "en"]


def test_save_profile_overwrites():
    """save_profile replaces entire profile."""
    from A.core.uzanto_service import load_profile, save_profile

    save_profile({"nomo": "A", "a": 1})
    save_profile({"nomo": "B"})
    reloaded = load_profile()
    assert reloaded["nomo"] == "B"
    assert "a" not in reloaded


# ── Keyring helpers ───────────────────────────────────────────────────────────


@patch("A.core.uzanto_service.get_password", return_value="sekret123")
def test_master_password_roundtrip(mock_get):
    """set_master_password stores, get_master_password retrieves."""
    from A.core.uzanto_service import get_master_password, set_master_password

    set_master_password("sekret123")
    assert get_master_password() == "sekret123"


@patch("A.core.uzanto_service.get_password", return_value=None)
def test_delete_master_password(mock_get):
    """delete_master_password removes the password."""
    from A.core.uzanto_service import (get_master_password, set_master_password,
                                       delete_master_password)

    set_master_password("sekret123")
    delete_master_password()
    assert get_master_password() is None


@patch("A.core.uzanto_service.get_password", return_value="hf_abc123")
def test_huggingface_api_key_roundtrip(mock_get):
    """set/get HuggingFace API key via keyring."""
    from A.core.uzanto_service import get_huggingface_api_key, set_huggingface_api_key

    set_huggingface_api_key("hf_abc123")
    assert get_huggingface_api_key() == "hf_abc123"


# ── Validation ────────────────────────────────────────────────────────────────


def test_validate_date_valid():
    from A.core.uzanto_service import validate_date
    assert validate_date("2024-01-15") is True
    assert validate_date("1999-12-31") is True


def test_validate_date_invalid():
    from A.core.uzanto_service import validate_date
    assert validate_date("24-01-15") is False
    assert validate_date("not-a-date") is False
    assert validate_date("") is False


def test_normalize_multi_contact_phone():
    from A.core.uzanto_service import normalize_multi_contact
    items = ["003312345678:labo:prima"]
    result = normalize_multi_contact(items, kind="telefono")
    assert result[0]["valoro"] == "003312345678"


def test_normalize_multi_contact_email():
    from A.core.uzanto_service import normalize_multi_contact
    items = ["alice@example.com:hejma:prima", "bob@test.org:labo"]
    result = normalize_multi_contact(items, kind="retposhto")
    assert result[0]["prima"] is True
    assert result[1]["prima"] is False


def test_normalize_multi_contact_invalid_phone():
    from A.core.uzanto_service import normalize_multi_contact
    with pytest.raises(ValueError, match="country code"):
        normalize_multi_contact(["+12345"], kind="telefono")


def test_normalize_multi_contact_invalid_email():
    from A.core.uzanto_service import normalize_multi_contact
    with pytest.raises(ValueError, match="Invalid email"):
        normalize_multi_contact(["not-an-email"], kind="retposhto")


# ── Display helpers ───────────────────────────────────────────────────────────


def test_display_value_none():
    from A.core.uzanto_service import display_value
    assert display_value(None) == "-"


def test_display_value_scalar():
    from A.core.uzanto_service import display_value
    assert display_value("hello") == "hello"
    assert display_value(42) == "42"


def test_display_value_masked_api_key():
    from A.core.uzanto_service import mask_api_key
    assert mask_api_key(None) == "-"
    assert mask_api_key("abcd1234") == "••••1234"
    assert mask_api_key("ab") == "••••"


# ── Encryption roundtrip ──────────────────────────────────────────────────────


def test_encrypt_decrypt_profile():
    from A.core.uzanto_service import encrypt_profile, decrypt_profile
    data = {"nomo": "Alice", "sekreta": "valoro"}
    blob = encrypt_profile(data, "mypassword")
    assert decrypt_profile(blob, "mypassword") == data


# ═══════════════════════════════════════════════════════════════════════════════
# uzanto_cli.py — CLI commands (Typer CliRunner)
# ═══════════════════════════════════════════════════════════════════════════════


def test_uzanto_vidi_empty(uzanto_app):
    """A uzanto vidi should show default/empty state."""
    result = runner.invoke(uzanto_app, ["vidi"])
    assert result.exit_code == 0
    assert "eo" in result.stdout or "Lingvo" in result.stdout


def test_uzanto_vidi_with_profile(uzanto_app):
    """A uzanto vidi shows stored profile fields."""
    from A.core.uzanto_service import save_profile
    save_profile({"nomo": "Alice"})

    result = runner.invoke(uzanto_app, ["vidi"])
    assert result.exit_code == 0
    assert "Alice" in result.stdout


@patch("A.core.uzanto_cli.edit_file", return_value=True)
def test_uzanto_modifi_opens_editor(mock_edit, uzanto_app):
    """A uzanto modifi opens the config file in $EDITOR."""
    from A.core.paths import config_dir

    # Pre-create config so edit_file gets a real path
    from A.core.config import load_config, save_config
    save_config(load_config())

    result = runner.invoke(uzanto_app, ["modifi"])
    assert result.exit_code == 0
    # Verify edit_file was called with the config path
    expected_path = config_dir() / "config.toml"
    mock_edit.assert_called_once_with(expected_path)


def test_uzanto_export_plain(tmp_path, uzanto_app):
    """A uzanto eksporti without encryption writes JSON."""
    from A.core.uzanto_service import save_profile
    save_profile({"nomo": "Alice"})

    out = tmp_path / "profile.json"
    result = runner.invoke(uzanto_app, ["eksporti", str(out)], input="n\n")
    assert result.exit_code == 0

    import json
    data = json.loads(out.read_text("utf-8"))
    assert data["profile"]["nomo"] == "Alice"


def test_uzanto_export_encrypted(tmp_path, uzanto_app):
    """A uzanto eksporti with --pasvorto writes encrypted file."""
    from A.core.uzanto_service import save_profile, decrypt_profile
    save_profile({"nomo": "Sekreto"})

    out = tmp_path / "profile.enc"
    result = runner.invoke(uzanto_app, ["eksporti", str(out), "--pasvorto", "sekret123"])
    assert result.exit_code == 0

    blob = out.read_bytes()
    decrypted = decrypt_profile(blob, "sekret123")
    assert decrypted["profile"]["nomo"] == "Sekreto"


def test_uzanto_import_plain(tmp_path, uzanto_app):
    """A uzanto importi reads plain JSON profile."""
    data = {"language": "eo", "profile": {"nomo": "Bob"}}
    src = tmp_path / "profile.json"
    src.write_text(__import__("json").dumps(data), encoding="utf-8")

    result = runner.invoke(uzanto_app, ["importi", str(src), "--anstatauigi"])
    assert result.exit_code == 0

    from A.core.uzanto_service import load_profile
    assert load_profile().get("nomo") == "Bob"


def test_uzanto_import_missing_file(uzanto_app):
    """A uzanto importi on nonexistent path should error."""
    result = runner.invoke(uzanto_app, ["importi", "/nonexistent/path.json"])
    assert result.exit_code != 0


@patch("A.core.uzanto_service.get_password", return_value="sekret123")
def test_uzanto_password_set_and_verify(mock_get, uzanto_app):
    """A uzanto pasvorto sets the master password."""
    from A.core.uzanto_service import get_master_password

    result = runner.invoke(uzanto_app, ["pasvorto"],
                           input="sekret123\nsekret123\nsekret123\n")
    assert result.exit_code == 0
    assert get_master_password() == "sekret123"


def test_uzanto_password_too_short(uzanto_app):
    """A uzanto pasvorto rejects short passwords."""
    result = runner.invoke(uzanto_app, ["pasvorto"], input="ab\nab\n")
    assert result.exit_code != 0


def test_uzanto_helpo_shows_help(uzanto_app):
    """A uzanto --helpo shows help text."""
    result = runner.invoke(uzanto_app, ["--helpo"])
    assert result.exit_code == 0
    assert "uzanto" in result.stdout or "Administri" in result.stdout
