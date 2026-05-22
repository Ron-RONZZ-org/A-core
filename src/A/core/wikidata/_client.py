"""Low-level Wikidata API client.

Port of the autish-legacy Wikidata integration, extracted from A-encik.
Provides direct API access to ``wbsearchentities`` and ``wbgetentities``
endpoints.

All functions in this module are internal — use ``A.core.wikidata``
public API instead.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_WIKIDATA_USER_AGENT = "A-core/0.1.0 (Wikidata integration)"


def _language_priority(languages: list[str]) -> list[str]:
    """Ensure 'eo' and 'en' are included as fallbacks."""
    result = list(dict.fromkeys(languages))
    for fallback in ("eo", "en"):
        if fallback not in result:
            result.append(fallback)
    return result


def search_languages(lingvo: str | None) -> list[str]:
    """Resolve language codes for Wikidata search.

    Args:
        lingvo: User-supplied language code(s) or ``None``.

    Returns:
        Prioritised list of language codes with eo/en fallback.
    """
    if lingvo:
        parsed = [
            code.strip()
            for code in lingvo.split(",")
            if re.fullmatch(r"[a-z]{2}", code.strip().lower())
        ]
        if not parsed:
            msg = "Nevalida --lingvo. Uzu 2-litera(j)n kodojn (ekz: eo,en)."
            raise ValueError(msg)
        return _language_priority(parsed)
    env_lang = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").split(".")[0]
    env_code = env_lang.split("_")[0].strip().lower()
    if re.fullmatch(r"[a-z]{2}", env_code):
        return _language_priority([env_code])
    return ["eo", "en"]


def _api_get(params: dict[str, str], *, timeout: float = 45.0) -> dict[str, Any]:
    """Make a GET request to the Wikidata API.

    Args:
        params: Query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On network errors or invalid responses.
    """
    query = urllib.parse.urlencode(params)
    url = f"https://www.wikidata.org/w/api.php?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": _WIKIDATA_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        raise RuntimeError(f"Wikidata API neatingebla (reto: {reason})") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Wikidata API neatingebla (eltempiĝis post {timeout}s)") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Wikidata API respondo nevalida") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Wikidata API respondo nevalida")
    return data


def _extract_all_language_metadata(
    entity: dict[str, Any], *, prop_id: str
) -> dict[str, Any]:
    """Extract per-language labels, descriptions, and aliases from a Wikidata entity.

    Unlike :func:`_extract_entity_metadata`, this returns *all* languages
    present in the entity response without priority-based winnowing.

    Returns:
        dict with keys:
            ``labels``       — ``{lang: str}``
            ``descriptions`` — ``{lang: str}``
            ``aliases``      — ``{lang: [str, ...]}``
    """
    labels: dict[str, str] = {}
    raw_labels = entity.get("labels")
    if isinstance(raw_labels, dict):
        for lang, payload in raw_labels.items():
            if isinstance(payload, dict) and str(payload.get("value") or "").strip():
                labels[lang] = str(payload["value"]).strip()

    descriptions: dict[str, str] = {}
    raw_descs = entity.get("descriptions")
    if isinstance(raw_descs, dict):
        for lang, payload in raw_descs.items():
            if isinstance(payload, dict) and str(payload.get("value") or "").strip():
                descriptions[lang] = str(payload["value"]).strip()

    aliases: dict[str, list[str]] = {}
    raw_aliases = entity.get("aliases")
    if isinstance(raw_aliases, dict):
        for lang, entries in raw_aliases.items():
            if not isinstance(entries, list):
                continue
            values: list[str] = []
            seen: set[str] = set()
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                val = str(entry.get("value") or "").strip()
                if val and val.lower() not in seen:
                    seen.add(val.lower())
                    values.append(val)
            if values:
                aliases[lang] = values

    # Ensure prop_id appears in every language's alias list
    prop_lower = prop_id.lower()
    for lang in list(aliases):
        if prop_lower not in {a.lower() for a in aliases[lang]}:
            aliases[lang].append(prop_lower)
    # If no language has aliases, seed the first available (or "en") with prop_id
    alias_has_prop = any(
        prop_lower in {a.lower() for a in al} for al in aliases.values()
    )
    if not alias_has_prop:
        fallback_lang = next(iter(labels)) if labels else "en"
        aliases.setdefault(fallback_lang, []).append(prop_lower)

    return {"labels": labels, "descriptions": descriptions, "aliases": aliases}


def _extract_entity_metadata(
    entity: dict[str, Any], *, prop_id: str, lang_list: list[str]
) -> dict[str, Any]:
    """Extract label, description, and aliases from a Wikidata entity dict.

    Returns the **best match** per field using language priority.
    For per-language data see :func:`_extract_all_language_metadata`.

    Returns dict with keys: etikedo, priskribo, aliasoj.
    """
    all_meta = _extract_all_language_metadata(entity, prop_id=prop_id)

    label = ""
    for lang in lang_list:
        if lang in all_meta["labels"]:
            label = all_meta["labels"][lang]
            break

    description = ""
    for lang in lang_list:
        if lang in all_meta["descriptions"]:
            description = all_meta["descriptions"][lang]
            break

    alias_values: list[str] = []
    seen: set[str] = set()
    for lang in lang_list:
        if lang not in all_meta["aliases"]:
            continue
        for alias in all_meta["aliases"][lang]:
            if alias.lower() not in seen:
                seen.add(alias.lower())
                alias_values.append(alias)

    return {"etikedo": label, "priskribo": description, "aliasoj": alias_values}


def search_properties(
    query: str, languages: list[str] | None = None
) -> list[dict[str, Any]]:
    """Search Wikidata for properties matching a query.

    Single English search for efficiency (+ prioritized languages).
    Unlike most Wikidata lookups, property IDs (P-numbers) are
    language-agnostic — a single search suffices to find matching
    properties. Multi-language labels are resolved via the separate
    ``_properties_metadata`` enrichment step.

    Args:
        query: Free-text search string.
        languages: Prioritised language codes for label enrichment.
            Defaults to ``["en", "eo"]``.

    Returns:
        List of result dicts with keys: ligilo, priskribo, aliasoj,
        etikedo, fonto.
    """
    if languages is None:
        languages = ["en", "eo"]
    dedup: dict[str, dict[str, Any]] = {}

    seen_lang: set[str] = set()
    for lang in _language_priority(languages):
        if lang in seen_lang:
            continue
        seen_lang.add(lang)
        try:
            data = _api_get({
                "action": "wbsearchentities",
                "format": "json",
                "language": lang,
                "uselang": lang,
                "type": "property",
                "limit": "15",
                "search": query,
            })
        except RuntimeError:
            continue
        results = data.get("search")
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            prop_id = str(item.get("id") or "").strip()
            if not re.fullmatch(r"P\d+", prop_id):
                continue
            ligilo = f"wdt:{prop_id}"
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip()
            aliases: list[str] = []
            match_obj = item.get("match")
            if isinstance(match_obj, dict):
                text = str(match_obj.get("text") or "").strip()
                if text and text.lower() != label.lower():
                    aliases.append(text)
            if prop_id.lower() not in {alias.lower() for alias in aliases}:
                aliases.append(prop_id.lower())
            existing = dedup.get(ligilo)
            if existing is None:
                dedup[ligilo] = {
                    "ligilo": ligilo,
                    "priskribo": description,
                    "aliasoj": aliases,
                    "etikedo": label,
                    "fonto": "wikidata",
                }
            else:
                if not str(existing.get("priskribo") or "") and description:
                    existing["priskribo"] = description
                combined = [str(a) for a in existing.get("aliasoj") or []]
                for alias in aliases:
                    if alias.lower() not in {a.lower() for a in combined}:
                        combined.append(alias)
                existing["aliasoj"] = combined

    # Enrich with property metadata
    if dedup:
        prop_ids = [ligilo.split(":", 1)[1] for ligilo in dedup]
        try:
            metadata = _properties_metadata(prop_ids, languages)
        except RuntimeError:
            metadata = {}
        for ligilo, item in dedup.items():
            prop_id = ligilo.split(":", 1)[1]
            localized = metadata.get(prop_id)
            if not localized:
                continue
            localized_label = str(localized.get("etikedo") or "").strip()
            localized_desc = str(localized.get("priskribo") or "").strip()
            if localized_label:
                item["etikedo"] = localized_label
            if localized_desc:
                item["priskribo"] = localized_desc
            merged: list[str] = []
            for alias in [
                *[str(a) for a in (localized.get("aliasoj") or [])],
                *[str(a) for a in (item.get("aliasoj") or [])],
            ]:
                cleaned = alias.strip()
                if cleaned and cleaned.lower() not in {a.lower() for a in merged}:
                    merged.append(cleaned)
            if merged:
                item["aliasoj"] = merged

    return list(dedup.values())


def _properties_metadata(
    prop_ids: list[str], languages: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    """Fetch metadata for multiple Wikidata properties."""
    if languages is None:
        languages = ["en", "eo"]
    normalized: list[str] = []
    for raw_id in prop_ids:
        candidate = str(raw_id or "").strip().upper()
        if re.fullmatch(r"P\d+", candidate) and candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        return {}
    lang_list = _language_priority(languages)
    data = _api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(normalized),
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    extracted: dict[str, dict[str, Any]] = {}
    for prop_id in normalized:
        entity = entities.get(prop_id)
        if isinstance(entity, dict):
            extracted[prop_id] = _extract_entity_metadata(
                entity, prop_id=prop_id, lang_list=lang_list,
            )
    return extracted


def _properties_details(
    prop_ids: list[str], languages: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    """Fetch **per-language** metadata for multiple Wikidata properties.

    Batch equivalent of :func:`get_property_details` — returns per-language
    labels, descriptions, and aliases for all requested properties in a
    single API call.

    Args:
        prop_ids: Wikidata property IDs (e.g. ``["P1082", "P31"]``).
        languages: Language codes to return data for.
            Defaults to ``["en", "eo"]``.

    Returns:
        ``{prop_id: {"labels": {...}, "descriptions": {...}, "aliases": {...}}}``

    Raises:
        RuntimeError: If the API is unreachable.
    """
    if languages is None:
        languages = ["en", "eo"]
    normalized: list[str] = []
    for raw_id in prop_ids:
        candidate = str(raw_id or "").strip().upper()
        if re.fullmatch(r"P\d+", candidate) and candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        return {}
    lang_list = _language_priority(languages)
    data = _api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(normalized),
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    extracted: dict[str, dict[str, Any]] = {}
    for prop_id in normalized:
        entity = entities.get(prop_id)
        if isinstance(entity, dict):
            extracted[prop_id] = _extract_all_language_metadata(
                entity, prop_id=prop_id,
            )
    return extracted


def get_property_metadata(
    prop_id: str, languages: list[str] | None = None
) -> dict[str, Any]:
    """Fetch metadata for a single Wikidata property.

    Args:
        prop_id: e.g. ``"P1082"``
        languages: Prioritised language codes. Defaults to ``["en", "eo"]``.

    Returns:
        Dict with keys: etikedo, priskribo, aliasoj.

    Raises:
        RuntimeError: If the property is not found or API unreachable.
    """
    if languages is None:
        languages = ["en", "eo"]
    lang_list = _language_priority(languages)
    data = _api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": prop_id,
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    entity = entities.get(prop_id)
    if not isinstance(entity, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas la petitan ID")
    return _extract_entity_metadata(
        entity, prop_id=prop_id, lang_list=lang_list,
    )


def get_property_details(
    prop_id: str, languages: list[str] | None = None
) -> dict[str, Any]:
    """Fetch **per-language** labels, descriptions, and aliases for a Wikidata property.

    Unlike :func:`get_property_metadata` which returns a single best-match,
    this function returns data for *all requested languages* as a dict keyed
    by language code.

    Args:
        prop_id: Wikidata property ID (e.g. ``"P1082"``).
        languages: Language codes to return data for.
            Defaults to ``["en", "eo"]``.

    Returns:
        ``{
            "id": "P1082",
            "labels": {"en": "population", "eo": "loĝantaro"},
            "descriptions": {"en": "...", "eo": "..."},
            "aliases": {"en": ["pop", "p1082"], "eo": ["loĝantaroj", "p1082"]}
        }``

    Raises:
        RuntimeError: If the property is not found or API unreachable.
    """
    if languages is None:
        languages = ["en", "eo"]
    lang_list = _language_priority(languages)
    data = _api_get({
        "action": "wbgetentities",
        "format": "json",
        "ids": prop_id,
        "props": "labels|descriptions|aliases",
        "languages": "|".join(lang_list),
    })
    entities = data.get("entities")
    if not isinstance(entities, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas 'entities'")
    entity = entities.get(prop_id)
    if not isinstance(entity, dict):
        raise RuntimeError("Wikidata API respondo ne enhavas la petitan ID")
    details = _extract_all_language_metadata(entity, prop_id=prop_id)
    details["id"] = prop_id
    return details
