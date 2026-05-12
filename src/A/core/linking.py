"""Cross-module linking utilities for A.

Bridges A.core.references (text parser) and A.core.links (storage).
Provides sync, display, and HTML rendering for cross-module references
(e.g., vt#uuid for vorto, ec#uuid for encik).
"""

from __future__ import annotations

import html as html_module
import re
from typing import Any

from A.core.links import add_link, remove_all_for_entry
from A.core.references import parse_refs, resolve

# Default prefix mapping: ref_type → A.core.links entry type
PREFIX_MAP: dict[str, str] = {
    "vt": "vorto",
    "ec": "encik",
}
# Reverse mapping for resolve() which expects ref prefix (vt, ec)
_REVERSE_MAP: dict[str, str] = {v: k for k, v in PREFIX_MAP.items()}


def sync_links_for_entry(
    uuid: str,
    source_type: str,
    text_fields: dict[str, Any],
    explicit_links: list[str] | None = None,
    prefix_map: dict[str, str] | None = None,
) -> int:
    """Parse inline refs from text fields, merge with explicit links,
    and sync all to A.core.links.

    Uses clear+rebuild: removes all existing links for this entry,
    then re-adds from the merged set.

    Args:
        uuid: Entry UUID.
        source_type: Entry type for A.core.links (e.g. "vorto", "encik").
        text_fields: Dict of field_name → field_value to scan for
                     vt#/ec# references. Values can be str, list, or dict.
        explicit_links: Explicit UUIDs from the ligiloj JSON column
                        (assumed same source_type).
        prefix_map: Dict mapping ref prefix → entry type.
                    Default: {"vt": "vorto", "ec": "encik"}

    Returns:
        Number of links synced.
    """
    pmap = prefix_map or PREFIX_MAP
    targets: set[tuple[str, str]] = set()  # (target_type, target_uuid)

    # Collect explicit links (intra-module or cross-module with prefix)
    for target_uuid in (explicit_links or []):
        if not target_uuid or target_uuid == uuid:
            continue
        tu = target_uuid.lower()
        # Check for cross-module prefix (ec#uuid, vt#uuid)
        if tu.startswith("ec#"):
            targets.add(("encik", target_uuid[3:]))
        elif tu.startswith("vt#"):
            targets.add(("vorto", target_uuid[3:]))
        else:
            targets.add((source_type, target_uuid))

    # Collect inline refs from text fields (may be cross-module)
    for field_value in text_fields.values():
        if field_value is None:
            continue
        if isinstance(field_value, str):
            refs = parse_refs(field_value)
            for ref in refs:
                target_type = pmap.get(ref.ref_type)
                if target_type and ref.uuid != uuid:
                    targets.add((target_type, ref.uuid))
        elif isinstance(field_value, list):
            for item in field_value:
                if isinstance(item, str):
                    refs = parse_refs(item)
                    for ref in refs:
                        target_type = pmap.get(ref.ref_type)
                        if target_type and ref.uuid != uuid:
                            targets.add((target_type, ref.uuid))
        elif isinstance(field_value, dict):
            for item in field_value.values():
                if isinstance(item, str):
                    refs = parse_refs(item)
                    for ref in refs:
                        target_type = pmap.get(ref.ref_type)
                        if target_type and ref.uuid != uuid:
                            targets.add((target_type, ref.uuid))

    # Clear all existing links for this entry
    remove_all_for_entry(source_type, uuid)

    # Rebuild: resolve short UUIDs to full before storing
    count = 0
    for target_type, target_uuid in targets:
        # Resolve short UUID (8 chars) to full UUID
        resolved_full = target_uuid
        if len(target_uuid) == 8:
            ref_prefix = _REVERSE_MAP.get(target_type, target_type)
            resolved = resolve(ref_prefix, target_uuid)
            if resolved and resolved.uuid and len(resolved.uuid) > 8:
                resolved_full = resolved.uuid
        add_link(source_type, uuid, target_type, resolved_full)
        count += 1

    return count


def remove_entry_links(source_type: str, uuid: str) -> int:
    """Remove all links for an entry from A.core.links.

    Args:
        source_type: Entry type.
        uuid: Entry UUID.

    Returns:
        Number of removed links.
    """
    return remove_all_for_entry(source_type, uuid)


def ref_to_cli(ref_type: str, uuid_short: str) -> str:
    """Render a resolved reference as CLI display string.

    Args:
        ref_type: "vt" or "ec".
        uuid_short: Short UUID (8 chars).

    Returns:
        CLI string with Rich markup.
    """
    resolved = resolve(ref_type, uuid_short)
    if resolved and resolved.title:
        return f"[green]✓[/] {resolved.title} ({ref_type}#{uuid_short})"
    return f"[red]?[/] {ref_type}#{uuid_short}"


def ref_to_html(ref_type: str, uuid: str, title: str = "") -> str:
    """Render a resolved reference as HTML anchor tag.

    Args:
        ref_type: "vt" or "ec".
        uuid: Full UUID.
        title: Display title (resolved if empty).

    Returns:
        HTML anchor string.
    """
    short = uuid[:8]
    if not title:
        resolved = resolve(ref_type, uuid)
        title = resolved.title if resolved and resolved.title else f"{ref_type}#{short}"
    escaped_title = html_module.escape(title)
    return f'<a href="#{ref_type}-{short}">{escaped_title}</a>'


_RESOLVE_REFS_RE = re.compile(
    r'\b(vt|ec)#([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})\b',
    re.IGNORECASE,
)


def resolve_refs_in_html(html_text: str) -> str:
    """Replace vt#uuid / ec#uuid patterns with clickable HTML links.

    Args:
        html_text: HTML text to process.

    Returns:
        HTML with vt#/ec# patterns replaced by anchor tags.
    """
    def _replace(m: re.Match) -> str:
        ref_type = m.group(1).lower()
        uuid = m.group(2).lower()
        return ref_to_html(ref_type, uuid)

    return _RESOLVE_REFS_RE.sub(_replace, html_text)


__all__ = [
    "sync_links_for_entry",
    "remove_entry_links",
    "ref_to_cli",
    "ref_to_html",
    "resolve_refs_in_html",
]