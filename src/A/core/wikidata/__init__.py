"""A.core.wikidata — Wikidata API client and property catalog.

Provides search and metadata lookup for Wikidata properties, with a
pre-seeded common properties dictionary for offline/quick access.

Usage::

    from A.core.wikidata import search_properties, get_property_metadata

    # Search Wikidata for properties matching a keyword
    results = search_properties("population", languages=["en", "eo"])
    for r in results:
        print(r["ligilo"], r["etikedo"])

    # Get metadata for a specific property
    meta = get_property_metadata("P1082", languages=["en", "eo"])
    print(meta["etikedo"], meta["priskribo"])
"""

from A.core.wikidata._client import (
    get_property_metadata,
    search_languages,
    search_properties,
)
from A.core.wikidata._common import COMMON_PROPERTIES, get_common_properties

__all__ = [
    "COMMON_PROPERTIES",
    "get_common_properties",
    "get_property_metadata",
    "search_languages",
    "search_properties",
]
