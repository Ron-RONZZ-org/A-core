"""Internationalization for A - Esperanto-native."""

from typing import Callable

# Translations - Esperanto as primary
_translations = {
    "eo": {
        "success": "Sukceso",
        "error": "Eraro",
        "warning": "Averto",
        "not_found": "Ne trovita",
        "help": "Helpo",
        "A - minimuma CLI kadro": "A - minimuma CLI kadro",
    },
    "en": {
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "not_found": "Not found",
        "help": "Help",
        "A - minimuma CLI kadro": "A - minimal CLI framework",
    },
    "fr": {
        "success": "Sukceso",
        "error": "Eraro",
        "warning": "Averto",
        "not_found": "Ne trovita",
        "help": "Helpo",
        "A - minimuma CLI kadro": "A - Cadre CLI minimal",
    },
}

_current_lang = "eo"  # Esperanto as default


def set_language(lang: str) -> None:
    """Set the current language."""
    global _current_lang
    if lang not in _translations:
        raise ValueError(f"Unsupported language: {lang}")
    _current_lang = lang


def tr(key: str, lang: str = None) -> str:
    """Translate a key. Falls back to English then key."""
    if lang is None:
        lang = _current_lang
    
    # Try current language first
    if key in _translations.get(lang, {}):
        return _translations[lang][key]
    
    # Fall back to English
    if key in _translations.get("en", {}):
        return _translations["en"][key]
    
    # Fall back to key itself
    return key


def available_languages() -> list[str]:
    """Return list of available language codes."""
    return list(_translations.keys())


def get_current_language() -> str:
    """Return the current language."""
    return _current_lang