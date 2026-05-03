"""Tests for A.core.registry."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from A.core.registry import (
    DEFAULT_REGISTRY_URL,
    ENV_REGISTRY_URL,
    _get_registry_url,
    _is_cache_valid,
    _validate_manifest,
    fetch_registry,
    get_installed_modules,
    get_module_info,
    search_registry,
)
from A.core.exceptions import RegistryError


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def valid_manifest() -> dict:
    return {
        "version": 1,
        "schema_version": "1.0",
        "updated": "2026-05-03T00:00:00Z",
        "modules": [
            {
                "name": "tempo",
                "display_name": "Tempo",
                "pip": "A-tempo",
                "description": "# Tempo\n\nClock plugin.\n\n## Installation\n\n```\npip install A-tempo\n```\n",
            },
            {
                "name": "vorto",
                "display_name": "Vorto",
                "pip": "A-vorto",
                "description": "# Vorto\n\nWordbook plugin.\n\n## Installation\n\n```\npip install A-vorto\n```\n",
            },
        ],
    }


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    cache = tmp_path / ".cache" / "A"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


# ── _get_registry_url ────────────────────────────────────────────────────────


def test_registry_url_default():
    """Default URL is the GitHub raw URL."""
    url = _get_registry_url()
    assert url == DEFAULT_REGISTRY_URL


def test_registry_url_from_env(monkeypatch):
    """Env var overrides default."""
    monkeypatch.setenv(ENV_REGISTRY_URL, "https://example.com/modules.json")
    assert _get_registry_url() == "https://example.com/modules.json"


def test_registry_url_from_config(monkeypatch):
    """Config value overrides default (but env still wins)."""
    monkeypatch.delenv(ENV_REGISTRY_URL, raising=False)
    with patch("A.core.registry.get_setting") as mock_get:
        mock_get.return_value = "https://config.example.com/modules.json"
        assert _get_registry_url() == "https://config.example.com/modules.json"


# ── _is_cache_valid ──────────────────────────────────────────────────────────


def test_cache_valid(cache_dir):
    """Cache file within TTL is valid."""
    cache_path = cache_dir / "modules.json"
    cache_path.write_text("{}", encoding="utf-8")
    assert _is_cache_valid(cache_path)


def test_cache_expired(cache_dir):
    """Cache file older than TTL is invalid."""
    cache_path = cache_dir / "modules.json"
    cache_path.write_text("{}", encoding="utf-8")
    # Set mtime far in the past
    old_time = time.time() - 999999
    os.utime(cache_path, (old_time, old_time))
    assert not _is_cache_valid(cache_path)


def test_cache_missing(cache_dir):
    """Non-existent cache is invalid."""
    cache_path = cache_dir / "modules.json"
    assert not _is_cache_valid(cache_path)


# ── _validate_manifest ───────────────────────────────────────────────────────


def test_validate_valid(valid_manifest):
    """Valid manifest passes validation."""
    result = _validate_manifest(valid_manifest)
    assert result == valid_manifest


def test_validate_not_dict():
    """Non-dict raises RegistryError."""
    with pytest.raises(RegistryError):
        _validate_manifest([])


def test_validate_missing_version(valid_manifest):
    """Missing version key raises RegistryError."""
    del valid_manifest["version"]
    with pytest.raises(RegistryError):
        _validate_manifest(valid_manifest)


def test_validate_missing_modules(valid_manifest):
    """Missing modules key raises RegistryError."""
    del valid_manifest["modules"]
    with pytest.raises(RegistryError):
        _validate_manifest(valid_manifest)


def test_validate_modules_not_list(valid_manifest):
    """Non-list modules raises RegistryError."""
    valid_manifest["modules"] = {}
    with pytest.raises(RegistryError):
        _validate_manifest(valid_manifest)


# ── fetch_registry ───────────────────────────────────────────────────────────


@patch("A.core.registry._get_cache_path")
@patch("A.core.registry._fetch_url")
def test_fetch_registry_success(
    mock_fetch, mock_cache_path, cache_dir, valid_manifest
):
    """Successful HTTP fetch returns valid manifest and writes cache."""
    mock_cache_path.return_value = cache_dir / "modules.json"
    mock_fetch.return_value = json.dumps(valid_manifest)

    result = fetch_registry(refresh=True)
    assert result == valid_manifest
    assert (cache_dir / "modules.json").exists()


@patch("A.core.registry._get_cache_path")
@patch("A.core.registry._fetch_url")
def test_fetch_registry_offline_with_cache(
    mock_fetch, mock_cache_path, cache_dir, valid_manifest
):
    """Offline fallback uses stale cache."""
    cache_path = cache_dir / "modules.json"
    cache_path.write_text(json.dumps(valid_manifest), encoding="utf-8")
    mock_cache_path.return_value = cache_path
    mock_fetch.side_effect = RegistryError("Network error")

    result = fetch_registry(refresh=True)
    assert result == valid_manifest


@patch("A.core.registry._get_cache_path")
@patch("A.core.registry._fetch_url")
def test_fetch_registry_offline_no_cache(
    mock_fetch, mock_cache_path, cache_dir
):
    """Offline with no cache returns None."""
    mock_cache_path.return_value = cache_dir / "modules.json"
    mock_fetch.side_effect = RegistryError("Network error")

    result = fetch_registry(refresh=True)
    assert result is None


@patch("A.core.registry._get_cache_path")
@patch("A.core.registry._fetch_url")
def test_fetch_registry_corrupt_cache(
    mock_fetch, mock_cache_path, cache_dir
):
    """Corrupt cache with no network returns None."""
    cache_path = cache_dir / "modules.json"
    cache_path.write_text("not json", encoding="utf-8")
    mock_cache_path.return_value = cache_path
    mock_fetch.side_effect = RegistryError("Network error")

    result = fetch_registry(refresh=True)
    assert result is None
    # Corrupt cache should be deleted
    assert not cache_path.exists()


@patch("A.core.registry._get_cache_path")
def test_fetch_registry_uses_cache(
    mock_cache_path, cache_dir, valid_manifest
):
    """When cache is valid, no HTTP call is made."""
    cache_path = cache_dir / "modules.json"
    cache_path.write_text(json.dumps(valid_manifest), encoding="utf-8")
    mock_cache_path.return_value = cache_path

    with patch("A.core.registry._fetch_url") as mock_fetch:
        result = fetch_registry()
        assert result == valid_manifest
        mock_fetch.assert_not_called()


# ── search_registry ──────────────────────────────────────────────────────────


@patch("A.core.registry.fetch_registry")
def test_search_by_name(mock_fetch, valid_manifest):
    """Search by name returns matching module."""
    mock_fetch.return_value = valid_manifest
    results = search_registry("tempo")
    assert len(results) == 1
    assert results[0]["name"] == "tempo"


@patch("A.core.registry.fetch_registry")
def test_search_by_description(mock_fetch, valid_manifest):
    """Search by description returns matching module."""
    mock_fetch.return_value = valid_manifest
    results = search_registry("wordbook")
    assert len(results) == 1
    assert results[0]["name"] == "vorto"


@patch("A.core.registry.fetch_registry")
def test_search_case_insensitive(mock_fetch, valid_manifest):
    """Search is case-insensitive."""
    mock_fetch.return_value = valid_manifest
    results = search_registry("TEMPO")
    assert len(results) == 1
    assert results[0]["name"] == "tempo"


@patch("A.core.registry.fetch_registry")
def test_search_no_match(mock_fetch, valid_manifest):
    """No match returns empty list."""
    mock_fetch.return_value = valid_manifest
    results = search_registry("nonexistent")
    assert results == []


@patch("A.core.registry.fetch_registry")
def test_search_empty_query(mock_fetch, valid_manifest):
    """Empty query returns all modules."""
    mock_fetch.return_value = valid_manifest
    results = search_registry("")
    assert len(results) == 2


@patch("A.core.registry.fetch_registry")
def test_search_registry_unavailable(mock_fetch):
    """Registry unavailable returns empty list."""
    mock_fetch.return_value = None
    results = search_registry("tempo")
    assert results == []


# ── get_module_info ──────────────────────────────────────────────────────────


@patch("A.core.registry.fetch_registry")
def test_get_module_info_found(mock_fetch, valid_manifest):
    """Existing module returns its info dict."""
    mock_fetch.return_value = valid_manifest
    info = get_module_info("tempo")
    assert info is not None
    assert info["name"] == "tempo"


@patch("A.core.registry.fetch_registry")
def test_get_module_info_not_found(mock_fetch, valid_manifest):
    """Non-existing module returns None."""
    mock_fetch.return_value = valid_manifest
    info = get_module_info("nonexistent")
    assert info is None


@patch("A.core.registry.fetch_registry")
def test_get_module_info_case_insensitive(mock_fetch, valid_manifest):
    """Lookup is case-insensitive."""
    mock_fetch.return_value = valid_manifest
    info = get_module_info("TEMPO")
    assert info is not None
    assert info["name"] == "tempo"


@patch("A.core.registry.fetch_registry")
def test_get_module_info_unavailable(mock_fetch):
    """Registry unavailable returns None."""
    mock_fetch.return_value = None
    info = get_module_info("tempo")
    assert info is None


# ── get_installed_modules ────────────────────────────────────────────────────


@patch("A.core.registry.fetch_registry")
@patch("importlib.metadata.entry_points")
def test_get_installed_modules_some(
    mock_ep, mock_fetch, valid_manifest
):
    """Installed modules are discovered via entry points."""
    mock_fetch.return_value = valid_manifest

    # Mock entry points
    ep1 = MagicMock()
    ep1.name = "tempo"
    mock_ep.return_value = [ep1]

    installed = get_installed_modules()
    assert len(installed) == 1
    assert installed[0]["name"] == "tempo"
    assert installed[0]["display_name"] == "Tempo"


@patch("A.core.registry.fetch_registry")
@patch("importlib.metadata.entry_points")
def test_get_installed_modules_none(mock_ep, mock_fetch, valid_manifest):
    """No installed modules returns empty list."""
    mock_fetch.return_value = valid_manifest
    mock_ep.return_value = []

    installed = get_installed_modules()
    assert installed == []


@patch("A.core.registry.fetch_registry")
@patch("importlib.metadata.entry_points")
def test_get_installed_modules_unknown(mock_ep, mock_fetch, valid_manifest):
    """Unknown (not in manifest) modules still appear."""
    mock_fetch.return_value = valid_manifest

    ep1 = MagicMock()
    ep1.name = "unknown-module"
    mock_ep.return_value = [ep1]

    installed = get_installed_modules()
    assert len(installed) == 1
    assert installed[0]["name"] == "unknown-module"
    assert installed[0]["display_name"] == "Unknown-module"
    assert installed[0]["pip"] == "A-unknown-module"
