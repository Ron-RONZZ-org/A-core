"""Console and i18n re-export for A-vorto compatibility."""

from A.utils.output import console
from A.core.i18n import tr as _tr, set_language, get_current_language

def tr(*args):
    """Compatibility wrapper for tr() that accepts multiple language strings.
    
    Usage: tr(eo_text, en_text, fr_text)
    Returns the text for the current language, or first arg if not found.
    """
    if len(args) == 1:
        return _tr(args[0])
    # Multiple strings - try each language in order based on current language
    current = get_current_language()
    langs = ["eo", "en", "fr", "es", "de", "it", "pt"]
    try:
        idx = langs.index(current)
    except ValueError:
        idx = 0
    # Return the string at the current language index, or first available
    if idx < len(args):
        return args[idx]
    return args[0] if args else ""

__all__ = ["console", "tr"]