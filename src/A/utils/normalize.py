"""Text normalization utilities - zero dependencies.

Provides French ligature normalization and text folding for search.
"""

import re
import unicodedata
from collections.abc import Callable


def normalize_french_ligatures(text: str, direction: str = "fold") -> str:
    """Normalize French ligatures in both directions.

    Args:
        text: Input text
        direction:
            "fold" - œ/Œ→oe/OE (for search indexing)
            "expand" - oe/OE→œ/Œ (for display/writing when language is French)

    Returns:
        Normalized text

    Examples:
        >>> normalize_french_ligatures("cœur", "fold")
        'coeur'
        >>> normalize_french_ligatures("coeur", "expand")
        'cœur'
    """
    if direction == "fold":
        return (
            text.replace("œ", "oe")
            .replace("Œ", "OE")
            .replace("æ", "ae")
            .replace("Æ", "AE")
        )
    elif direction == "expand":
        # Use word boundary detection to avoid false matches
        text = re.sub(r"(?<![a-zA-Z])oe(?![a-zA-Z])", "œ", text)
        text = re.sub(r"(?<![a-zA-Z])OE(?![a-zA-Z])", "Œ", text)
        text = re.sub(r"(?<![a-zA-Z])ae(?![a-zA-Z])", "æ", text)
        text = re.sub(r"(?<![a-zA-Z])AE(?![a-zA-Z])", "Æ", text)
        return text
    return text


def fold_search_text(text: str) -> str:
    """Normalize text for accent-insensitive, case-insensitive search.

    Combines NFKD decomposition (accent stripping), ligature folding,
    and case folding into one operation.

    Args:
        text: Input text

    Returns:
        Normalized text for searching

    Examples:
        >>> fold_search_text("Cœur")
        'coeur'
        >>> fold_search_text("Été")
        'ete'
        >>> fold_search_text("Straße")
        'strasse'
    """
    if not text:
        return ""
    # Step 1: French ligature folding
    folded = normalize_french_ligatures(text, "fold")
    # Step 2: NFKD decomposition + remove combining characters (accents)
    normalized = unicodedata.normalize("NFKD", folded)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    # Step 3: Case folding
    return stripped.casefold()


# Convenience: all normalizers and their directions
NORMALIZERS: dict[str, tuple[Callable[[str], str], Callable[[str], str]]] = {
    "french_ligatures": (
        lambda t: normalize_french_ligatures(t, "fold"),
        lambda t: normalize_french_ligatures(t, "expand"),
    ),
}

__all__ = [
    "normalize_french_ligatures",
    "fold_search_text",
    "NORMALIZERS",
]