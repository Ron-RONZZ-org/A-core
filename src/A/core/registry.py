"""Module registry — fetch, cache, and search the A-module manifest.

Provides:
- ``fetch_registry()`` — download and cache ``modules.json`` from GitHub
- ``search_registry()`` — case-insensitive search by name/description
- ``get_module_info()`` — fetch a single module entry
- ``get_installed_modules()`` — discover already-installed A-modules
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from A.core.exceptions import RegistryError
from A.core.paths import cache_dir, ensure_dirs
from A.core.config import get_setting

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Ron-RONZZ-org/A-core/main/modules.json"
)
ENV_REGISTRY_URL = "A_MODULE_REGISTRY_URL"
CONFIG_REGISTRY_KEY = "module_registry_url"
DEFAULT_CACHE_TTL_SECONDS = 86400  # 24 hours

# ── URL resolution ───────────────────────────────────────────────────────────


def _get_registry_url() -> str:
    """Resolve the registry URL: env var > config > default."""
    env_url = os.environ.get(ENV_REGISTRY_URL)
    if env_url:
        return env_url
    config_url: str | None = get_setting(CONFIG_REGISTRY_KEY)
    if config_url:
        return config_url
    return DEFAULT_REGISTRY_URL


def _get_cache_path() -> Path:
    """Return the path to the cached manifest file."""
    ensure_dirs()
    return cache_dir() / "modules.json"


def _get_cache_ttl() -> int:
    """Return the cache TTL in seconds (configurable)."""
    return int(get_setting("module_cache_ttl", DEFAULT_CACHE_TTL_SECONDS))


# ── Cache invalidation ───────────────────────────────────────────────────────


def _is_cache_valid(cache_path: Path) -> bool:
    """Check whether the local cache is still fresh."""
    if not cache_path.exists():
        return False
    ttl = _get_cache_ttl()
    age = time.time() - cache_path.stat().st_mtime
    return age < ttl


# ── HTTP fetching ────────────────────────────────────────────────────────────


def _fetch_url(url: str) -> str:
    """Download *url* and return its text content.

    Raises ``RegistryError`` on network or HTTP errors.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status != 200:
                raise RegistryError(
                    f"HTTP {resp.status} fetching registry from {url}"
                )
            return resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RegistryError(f"Network error fetching registry: {exc}") from exc
    except OSError as exc:
        raise RegistryError(f"Connection error: {exc}") from exc


# ── Validate manifest structure ──────────────────────────────────────────────


def _validate_manifest(data: Any) -> dict:
    """Validate that *data* is a dict with the required manifest keys.

    Returns the validated dict or raises ``RegistryError``.
    """
    if not isinstance(data, dict):
        raise RegistryError("Registry manifest must be a JSON object")
    if "version" not in data:
        raise RegistryError("Registry manifest missing required field: 'version'")
    if "modules" not in data:
        raise RegistryError("Registry manifest missing required field: 'modules'")
    if not isinstance(data["modules"], list):
        raise RegistryError("Registry manifest 'modules' must be an array")
    return data


# ── Public API ───────────────────────────────────────────────────────────────


def fetch_registry(*, refresh: bool = False) -> dict | None:
    """Fetch the module registry, using cache when possible.

    Parameters
    ----------
    refresh:
        If True, skip the cache and always fetch from the network.

    Returns
    -------
    The parsed manifest dict (``{"version": …, "modules": […]}``) or
    ``None`` if the registry is unreachable and no cache exists.
    """
    cache_path = _get_cache_path()
    url = _get_registry_url()

    # 1. Try cache first (unless refresh requested)
    if not refresh and _is_cache_valid(cache_path):
        try:
            raw = cache_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return _validate_manifest(data)
        except (OSError, json.JSONDecodeError, RegistryError) as exc:
            # Corrupt cache — delete and fall through to re-fetch
            cache_path.unlink(missing_ok=True)

    # 2. Fetch from network
    try:
        raw = _fetch_url(url)
        data = json.loads(raw)
        data = _validate_manifest(data)
        # Write to cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(raw, encoding="utf-8")
        return data
    except (RegistryError, OSError, json.JSONDecodeError) as exc:
        # 3. Network failed — try stale cache as fallback
        if cache_path.exists():
            from A import warning
            warning(
                f"Ne eblas atingi la modul-registron. "
                f"Uzas ka\x0159itan daton (eble malaktuala).\n"
                f"Detalo: {exc}"
            )
            try:
                raw = cache_path.read_text(encoding="utf-8")
                return _validate_manifest(json.loads(raw))
            except (OSError, json.JSONDecodeError, RegistryError):
                cache_path.unlink(missing_ok=True)
                return None
        return None


def search_registry(query: str) -> list[dict]:
    """Search the registry by module *name* or *description*.

    Performs a case-insensitive substring match. Returns matching entries
    sorted alphabetically by ``name``.
    """
    data = fetch_registry()
    if data is None:
        return []
    q = query.lower().strip()
    if not q:
        return sorted(data["modules"], key=lambda m: m.get("name", ""))

    matches = [
        m
        for m in data["modules"]
        if q in m.get("name", "").lower()
        or q in m.get("description", "").lower()
        or q in m.get("display_name", "").lower()
    ]
    return sorted(matches, key=lambda m: m.get("name", ""))


def get_module_info(name: str) -> dict | None:
    """Return the manifest entry for a single module by *name*.

    Matching is case-insensitive.
    """
    data = fetch_registry()
    if data is None:
        return None
    q = name.lower().strip()
    for m in data["modules"]:
        if m.get("name", "").lower() == q:
            return m
    return None


def get_installed_modules() -> list[dict]:
    """Discover installed A-modules via entry points and cross-reference
    with the manifest.

    Returns a list of dicts each with at least ``name`` and ``display_name``.
    If the module is found in the manifest the full entry is returned.
    """
    import importlib.metadata

    installed: list[dict] = []
    try:
        eps = importlib.metadata.entry_points(group="A.commands")
    except TypeError:
        eps = importlib.metadata.entry_points().get("A.commands", [])

    # Build a lookup from name → manifest entry (cached)
    manifest = fetch_registry()
    manifest_lookup: dict[str, dict] = {}
    if manifest:
        for m in manifest["modules"]:
            manifest_lookup[m["name"]] = m

    for ep in eps:
        name = ep.name
        if name in manifest_lookup:
            installed.append(dict(manifest_lookup[name]))
        else:
            installed.append({
                "name": name,
                "display_name": name.capitalize(),
                "pip": f"A-{name}",
                "description": "",
            })

    return sorted(installed, key=lambda m: m.get("name", ""))
