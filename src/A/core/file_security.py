"""File path security utilities for the A-ecosystem.

Provides path resolution with traversal detection and glob-pattern
matching. Designed for use by A-kunpiloto's built-in file tools
(``write_file``, ``read_file``) and reusable by any A-module that
needs to validate user-supplied file paths against an allowlist.

Usage::

    from A.core.file_security import resolve_safe_path, match_path_globs

    bases = [Path("/tmp/A"), Path.home() / "Documents"]
    try:
        p = resolve_safe_path("~/Documents/note.md", *bases)
        # p -> PosixPath('/home/user/Documents/note.md')
    except PathTraversalError:
        # path escapes all allowed bases
        ...

    allowed = ["/tmp/A/**", "~/Desktop/*"]
    if match_path_globs(p, allowed):
        # path matches an allowlist pattern
        ...
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Sequence

from A.core.exceptions import PathTraversalError

__all__ = ["resolve_safe_path", "match_path_globs"]


def resolve_safe_path(
    path: str | Path,
    *allowed_bases: Path,
) -> Path:
    """Resolve a user-supplied path and verify it is within allowed bases.

    Steps:
    1. Expand ``~`` to the user's home directory.
    2. Resolve symlinks (``Path.resolve()`` gives the real path).
    3. Verify the resolved path is contained within at least one of the
       *allowed_bases*.

    Args:
        path: The raw path from user input (may contain ``~``, ``..``,
            symlinks, or relative components).
        *allowed_bases: One or more base directories that are considered
            safe. The resolved path must be inside at least one of these.

    Returns:
        The resolved, absolute :class:`Path`.

    Raises:
        PathTraversalError: If the resolved path escapes every allowed
            base directory.

    Example::

        >>> resolve_safe_path("~/foo", Path.home())
        PosixPath('/home/user/foo')

        >>> resolve_safe_path("/etc/passwd", Path.home())
        PathTraversalError: /etc/passwd is not under any allowed base
    """
    expanded = Path(path).expanduser()

    # Resolve relative paths against CWD, then resolve symlinks
    if not expanded.is_absolute():
        expanded = (Path.cwd() / expanded).resolve()
    else:
        expanded = expanded.resolve()

    _validate_within_allowed(expanded, allowed_bases)
    return expanded


def match_path_globs(path: Path, patterns: Sequence[str]) -> bool:
    """Check whether *path* matches any of the given glob patterns.

    Supports the following pattern forms:

    - ``/path/to/dir/**`` — recursively matches everything under ``dir``.
    - ``/path/to/dir/*`` — matches files directly inside ``dir``.
    - ``/path/to/file`` — exact file match.
    - ``**/file`` — matches ``file`` at any depth (relative wildcard).
    - ``~`` is expanded before matching.

    Args:
        path: The absolute path to check.
        patterns: A list of glob patterns (e.g. ``["/tmp/A/**", "~/Docs/*"]``).

    Returns:
        ``True`` if *path* matches at least one pattern.

    Example::

        >>> match_path_globs(Path("/tmp/A/foo/bar.txt"), ["/tmp/A/**"])
        True

        >>> match_path_globs(Path("/etc/passwd"), ["/tmp/A/**"])
        False
    """
    for pattern in patterns:
        raw = pattern.strip()
        if not raw:
            continue

        # Expand ~ in the pattern
        pat = os.path.expanduser(raw)

        if _match_single_pattern(path, pat):
            return True

    return False


def _match_single_pattern(path: Path, pattern: str) -> bool:
    """Check if *path* matches a single glob pattern.

    This is an internal helper that implements the matching logic
    without relying on PurePath.match (which has poor support for
    ``**`` in absolute patterns).
    """
    # 1. Recursive wildcard: /** at pattern end
    #    /tmp/A/**  matches /tmp/A itself and /tmp/A/anything/deeply/nested
    if pattern.endswith("/**"):
        base = Path(pattern[:-3])
        if path == base or _path_is_under(path, base):
            return True

    # 2. Shallow wildcard: /* at pattern end
    #    /tmp/A/*  matches /tmp/A/foo but NOT /tmp/A/sub/bar
    if pattern.endswith("/*"):
        base = Path(pattern[:-2])
        if path.parent == base:
            return True

    # 3. Exact match
    if path == Path(pattern):
        return True

    # 4. fnmatch on last component only (prevents * from crossing /)
    #    /tmp/A/foo*.txt  matches /tmp/A/foo123.txt but not /tmp/A/sub/bar.txt
    pattern_path = Path(pattern)
    if pattern_path.parent == path.parent:
        if fnmatch.fnmatch(path.name, pattern_path.name):
            return True

    # 5. ** recursion anywhere in the pattern
    #    **/file.txt  matches /home/user/any/path/file.txt
    #    /tmp/**/foo.txt  matches /tmp/a/b/foo.txt
    if "**" in pattern:
        parts = pattern_path.parts
        if _match_recursive_parts(path, parts):
            return True

    return False


def _path_is_under(path: Path, base: Path) -> bool:
    """Check if *path* is under *base* directory (recursive)."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _match_recursive_parts(path: Path, pattern_parts: tuple[str, ...]) -> bool:
    """Match a path against a pattern that contains ``**``.

    Splits on ``**`` and verifies each segment matches in order.
    """
    # Split pattern into segments around **
    segments: list[tuple[str, ...]] = []
    current: list[str] = []
    for part in pattern_parts:
        if part == "**":
            if current:
                segments.append(tuple(current))
                current = []
            # Represent ** as a sentinel
            segments.append(("__DOUBLESTAR__",))
        else:
            current.append(part)
    if current:
        segments.append(tuple(current))

    path_parts = path.parts

    return _match_segments(path_parts, 0, segments, 0)


def _match_segments(
    path_parts: tuple[str, ...],
    pi: int,
    segments: list[tuple[str, ...]],
    si: int,
) -> bool:
    """Recursively match path parts against pattern segments.

    Args:
        path_parts: The path split into parts.
        pi: Current index in path_parts.
        segments: The parsed pattern segments.
        si: Current index in segments.

    Returns:
        True if the remaining path matches the remaining segments.
    """
    # Base case: consumed all segments
    if si >= len(segments):
        return pi >= len(path_parts)

    seg = segments[si]

    # ** segment: try matching 0 or more path components
    if seg == ("__DOUBLESTAR__",):
        # Try consuming 0, 1, 2, ... path parts
        for skip in range(len(path_parts) - pi + 1):
            if _match_segments(path_parts, pi + skip, segments, si + 1):
                return True
        return False

    # Regular segment: must match the next N path parts exactly
    if pi + len(seg) > len(path_parts):
        return False

    for i, part in enumerate(seg):
        if not fnmatch.fnmatch(path_parts[pi + i], part):
            return False

    return _match_segments(path_parts, pi + len(seg), segments, si + 1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_within_allowed(
    resolved: Path,
    allowed_bases: Sequence[Path],
) -> None:
    """Check that *resolved* is inside at least one allowed base.

    Raises:
        PathTraversalError: If the path escapes every allowed base.
    """
    for base in allowed_bases:
        base_resolved = base.expanduser().resolve()
        try:
            resolved.relative_to(base_resolved)
            return  # Safe — path is under this base
        except ValueError:
            continue

    # Check if the path equals an allowed base exactly
    for base in allowed_bases:
        base_resolved = base.expanduser().resolve()
        if resolved == base_resolved:
            return

    raise PathTraversalError(str(resolved), [str(b) for b in allowed_bases])
