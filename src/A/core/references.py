"""Cross-references module for A.

Provides parsing and resolution of vt#uuid and ec#uuid references.
- vt#uuid: reference to a vorto entry
- ec#uuid: reference to an encik entry

Supports markdown link format: [label](vt#uuid) or [label](ec#uuid)
Supports plain format: vt#uuid or ec#uuid
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

# Regex patterns for reference extraction
# Matches [label](vt#uuid) or [label](ec#uuid)
MARKDOWN_LINK_RE = re.compile(
    r'\[([^\]]*)\]\(((?:vt#|ec#)[0-9a-f-]+)\)',
    re.IGNORECASE
)

# Matches plain vt#uuid or ec#uuid (not in markdown)
PLAIN_REF_RE = re.compile(
    r'\b(vt#|ec#)[0-9a-f-]+',
    re.IGNORECASE
)

# UUID pattern (short 8-char or full with/without hyphens)
UUID_RE = re.compile(r'[0-9a-f]{8}(?:-?[0-9a-f]{4}){3}-?[0-9a-f]{12}|[0-9a-f]{8}(?![0-9a-f])', re.IGNORECASE)


@dataclass
class Ref:
    """Represents a parsed reference."""
    ref_type: str  # 'vt' or 'ec'
    uuid: str
    label: str = ""  # Empty for plain refs, populated for markdown
    is_markdown: bool = False
    
    def __post_init__(self):
        # Normalize to lowercase
        self.ref_type = self.ref_type.lower()
        self.uuid = self.uuid.lower()


@dataclass
class ResolvedRef:
    """Resolved reference with entry data."""
    ref_type: str
    uuid: str
    label: str
    exists: bool
    title: str = ""  # Display title (teksto for vorto, titolo for encik)
    data: dict = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


def parse_refs(text: str) -> list[Ref]:
    """Parse all references from text.
    
    Extracts both markdown links [label](vt#uuid) and plain vt#uuid/ec#uuid.
    
    Args:
        text: Text containing references
        
    Returns:
        List of Ref objects
    """
    if not text:
        return []
    
    refs: list[Ref] = []
    seen: set[tuple[str, str]] = set()
    
    # Parse markdown links first
    for match in MARKDOWN_LINK_RE.finditer(text):
        label = match.group(1).strip()
        target = match.group(2).strip()
        
        ref_type, uuid = _split_ref(target)
        if ref_type and uuid:
            key = (ref_type, uuid)
            if key not in seen:
                seen.add(key)
                refs.append(Ref(
                    ref_type=ref_type,
                    uuid=uuid,
                    label=label,
                    is_markdown=True
                ))
    
    # Parse plain references (skip if already found via markdown)
    for match in PLAIN_REF_RE.finditer(text):
        target = match.group(0).strip()
        
        ref_type, uuid = _split_ref(target)
        if ref_type and uuid:
            key = (ref_type, uuid)
            if key not in seen:
                seen.add(key)
                refs.append(Ref(
                    ref_type=ref_type,
                    uuid=uuid,
                    label="",
                    is_markdown=False
                ))
    
    return refs


def _split_ref(ref: str) -> tuple[str, str] | tuple[None, None]:
    """Split a ref string into type and uuid.
    
    Args:
        ref: String like 'vt#uuid' or 'ec#uuid'
        
    Returns:
        Tuple of (type, uuid) or (None, None)
    """
    ref = ref.strip().lower()
    
    if ref.startswith("vt#"):
        uuid = ref[3:].strip()
    elif ref.startswith("ec#"):
        uuid = ref[3:].strip()
    else:
        return None, None
    
    # Validate UUID format
    if not UUID_RE.match(uuid):
        return None, None
    
    ref_type = ref.split("#")[0]
    return ref_type, uuid


def resolve_ref(ref_type: str, uuid: str) -> ResolvedRef:
    """Resolve a reference to entry data.
    
    Attempts to load the entry from the appropriate module:
    - A_vorto for 'vt' refs
    - A_encik for 'ec' refs
    
    Uses runtime detection - gracefully returns not-found if module unavailable.
    
    Args:
        ref_type: 'vt' or 'ec'
        uuid: UUID of the referenced entry
        
    Returns:
        ResolvedRef with exists=True if found
    """
    ref_type = ref_type.lower()
    
    if ref_type == "vt":
        return _resolve_vorto_ref(uuid)
    elif ref_type == "ec":
        return _resolve_encik_ref(uuid)
    else:
        return ResolvedRef(ref_type=ref_type, uuid=uuid, label="", exists=False)


def _resolve_vorto_ref(uuid: str) -> ResolvedRef:
    """Resolve a vorto reference."""
    try:
        from A_vorto.service import get_service

        service = get_service()
        entry = service.get(uuid)  # Uses prefix fallback

        if entry:
            resolved_uuid = entry.get("uuid", uuid)
            return ResolvedRef(
                ref_type="vt",
                uuid=resolved_uuid,
                label=entry.get("teksto", ""),
                exists=True,
                title=entry.get("teksto", ""),
                data=entry
            )
    except ImportError:
        pass  # A_vorto not available
    
    return ResolvedRef(
        ref_type="vt",
        uuid=uuid,
        label="",
        exists=False,
        title=f"vt#{uuid[:8]}"
    )


def _resolve_encik_ref(uuid: str) -> ResolvedRef:
    """Resolve an encik reference."""
    try:
        from A_encik.service import get_service

        service = get_service()
        entry = service.get(uuid)  # Uses prefix fallback

        if entry:
            resolved_uuid = entry.get("uuid", uuid)
            return ResolvedRef(
                ref_type="ec",
                uuid=resolved_uuid,
                label=entry.get("titolo", ""),
                exists=True,
                title=entry.get("titolo", ""),
                data=entry
            )
    except ImportError:
        pass  # A_encik not available
    
    return ResolvedRef(
        ref_type="ec",
        uuid=uuid,
        label="",
        exists=False,
        title=f"ec#{uuid[:8]}"
    )


@lru_cache(maxsize=256)
def resolve_ref_cached(ref_type: str, uuid: str) -> ResolvedRef:
    """Cached version of resolve_ref for performance.
    
    Args:
        ref_type: 'vt' or 'ec'
        uuid: UUID of the referenced entry
        
    Returns:
        ResolvedRef with exists=True if found
    """
    return resolve_ref(ref_type, uuid)


def clear_ref_cache() -> None:
    """Clear the reference resolution cache."""
    resolve_ref_cached.cache_clear()


def get_ref_display(ref_type: str, uuid: str, show_uuid: bool = True) -> str:
    """Get a human-readable display string for a reference.
    
    Args:
        ref_type: 'vt' or 'ec'
        uuid: UUID of the referenced entry
        show_uuid: Whether to show the UUID suffix
        
    Returns:
        Display string like "title (vt#abc123)" or just "title"
    """
    resolved = resolve_ref_cached(ref_type, uuid)
    
    if not resolved.exists:
        prefix = f"{ref_type}#"
        suffix = f"{uuid[:8]}" if show_uuid else ""
        return prefix + suffix
    
    # Use label if available, otherwise title
    display = resolved.label or resolved.title
    
    if show_uuid:
        return f"{display} ({ref_type}#{uuid[:8]})"
    
    return display


def iter_refs(text: str) -> Iterator[Ref]:
    """Iterate over references in text (generator version).
    
    Args:
        text: Text containing references
        
    Yields:
        Ref objects
    """
    yield from parse_refs(text)


def get_refs_in_field(entry: dict, field_name: str) -> list[Ref]:
    """Extract references from a specific field in an entry.
    
    Handles fields that might be:
    - String: plain text
    - List: multiple items
    - Dict: key-value pairs
    
    Args:
        entry: Entry dictionary
        field_name: Name of field to parse
        
    Returns:
        List of Ref objects
    """
    refs: list[Ref] = []
    
    value = entry.get(field_name)
    if value is None:
        return refs
    
    if isinstance(value, str):
        refs.extend(parse_refs(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                refs.extend(parse_refs(item))
    elif isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str):
                refs.extend(parse_refs(v))
    
    return refs


def count_refs(text: str) -> int:
    """Count the number of references in text.
    
    Args:
        text: Text containing references
        
    Returns:
        Number of unique references
    """
    return len(parse_refs(text))


def extract_ref_uuids(text: str, ref_type: str | None = None) -> list[str]:
    """Extract just the UUIDs from references.
    
    Args:
        text: Text containing references
        ref_type: Optional filter to 'vt' or 'ec'
        
    Returns:
        List of UUID strings
    """
    refs = parse_refs(text)
    
    if ref_type:
        ref_type = ref_type.lower()
        refs = [r for r in refs if r.ref_type == ref_type]
    
    return [r.uuid for r in refs]


def is_valid_ref(ref: str) -> bool:
    """Check if a string is a valid reference.
    
    Args:
        ref: String to check (e.g., 'vt#uuid' or 'ec#uuid')
        
    Returns:
        True if valid reference format
    """
    ref_type, uuid = _split_ref(ref)
    return ref_type is not None and uuid is not None


def normalize_ref(ref: str) -> str | None:
    """Normalize a reference to canonical form.
    
    Args:
        ref: String like '#uuid', 'vt#uuid', 'ec#uuid', 'uuid'
        
    Returns:
        Normalized form like 'vt#uuid' or None if invalid
    """
    ref = ref.strip()
    
    # Handle #uuid prefix
    if ref.startswith("#"):
        ref = ref[1:]
    
    # Check for vt# or ec# prefix
    ref_type, uuid = _split_ref(ref)
    
    if ref_type and uuid:
        return f"{ref_type}#{uuid}"
    
    # Might be plain UUID - assume vorto
    if UUID_RE.match(ref):
        return f"vt#{ref}"
    
    return None


# Module-level resolver using cached version
def resolve(ref_type: str, uuid: str) -> ResolvedRef:
    """Resolve a reference (cached version).
    
    This is the main entry point for resolution.
    
    Args:
        ref_type: 'vt' or 'ec'
        uuid: UUID of the referenced entry
        
    Returns:
        ResolvedRef with entry data if found
    """
    return resolve_ref_cached(ref_type, uuid)