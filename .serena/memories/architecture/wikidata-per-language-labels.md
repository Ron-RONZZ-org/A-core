# A.core.wikidata: Per-language Labels via get_property_details()

## Decision
Added `get_property_details()` returning per-language labels, descriptions, and aliases from Wikidata entities, solving the "double API call" problem for A-modules needing per-language data.

## Problem
`get_property_metadata()` returned only a single "best match" label from a prioritized language list. A-modules needing per-language labels (e.g., A-semantika's `label_en`/`label_eo` columns) had to call the API twice with swapped language priorities.

## Solution (implemented in commit 523bfc8, PR #84)
- **`_extract_all_language_metadata()`** — shared private helper returning `{labels, descriptions, aliases}` as per-language dicts
- **`get_property_details(prop_id, languages)`** — public function returning `{id, labels, descriptions, aliases}` with language-code keys
- **`_properties_details(prop_ids, languages)`** — private batch helper
- **Refactored `_extract_entity_metadata()`** — now delegates to the shared helper; behavior unchanged

## Key Design
- **English keys** for `get_property_details()` — mirror Wikidata API shape (`labels`, `descriptions`, `aliases`), not Esperanto (`etikedo`, `priskribo`, `aliasoj`) since this returns raw per-language data
- **Shared helper pattern** — `_extract_all_language_metadata()` iterates the entity dict once; both `_extract_entity_metadata` (best-match) and `get_property_details` (per-language) consume it
- **Batch support** — `_properties_details()` enables multi-property queries in a single API call
- **Backward compatible** — existing `get_property_metadata()` unchanged

## Files modified
- `src/A/core/wikidata/_client.py` — new functions + refactored extraction
- `src/A/core/wikidata/__init__.py` — export `get_property_details`
- `src/A/core/__init__.py` — re-export `get_property_details`
- `tests/test_wikidata.py` — 11 new tests (all 255 pass)

## Related
- Issue #82: feat: add get_property_details() with per-language labels
- A-semantika issue #2: P2 Wikidata integration needs this
