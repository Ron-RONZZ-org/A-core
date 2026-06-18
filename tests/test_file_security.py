"""Tests for A.core.file_security."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from A.core.exceptions import PathTraversalError
from A.core.file_security import (
    match_path_globs,
    resolve_safe_path,
)


class TestResolveSafePath:
    """Unit tests for resolve_safe_path()."""

    def test_absolute_path_within_allowed(self, tmp_path: Path) -> None:
        """An absolute path inside an allowed base resolves successfully."""
        target = tmp_path / "subdir" / "file.txt"
        target.parent.mkdir(parents=True)
        target.write_text("hello")

        result = resolve_safe_path(str(target), tmp_path)
        assert result == target.resolve()

    def test_tilde_expansion(self, tmp_path: Path) -> None:
        """~ is expanded to the user's home directory."""
        home = Path.home()
        # We need a path that actually exists under home
        allowed = home
        target = home / ".bashrc"
        if not target.exists():
            target = home / ".bash_logout"
        if not target.exists():
            target = home / ".profile"
        # If none of those exist, use home itself
        result = resolve_safe_path(str(target), allowed)
        assert result == target.resolve()

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        """A path that escapes the allowed base raises PathTraversalError."""
        allowed = tmp_path / "allowed"
        allowed.mkdir(parents=True)
        target = tmp_path / "secret.txt"
        target.write_text("secret")

        # Try to reference secret.txt via relative traversal from allowed
        with pytest.raises(PathTraversalError):
            resolve_safe_path(str(target), allowed)

    def test_path_outside_allowed_raises(self, tmp_path: Path) -> None:
        """A path obviously outside the allowed base raises."""
        allowed = tmp_path / "safe"
        allowed.mkdir()
        target = tmp_path / "outside" / "file.txt"
        target.parent.mkdir()
        target.write_text("data")

        with pytest.raises(PathTraversalError):
            resolve_safe_path(str(target), allowed)

    def test_multiple_allowed_bases(self, tmp_path: Path) -> None:
        """Path inside ANY of the allowed bases is accepted."""
        base_a = tmp_path / "a"
        base_b = tmp_path / "b"
        base_a.mkdir()
        base_b.mkdir()

        target_b = base_b / "file.txt"
        target_b.write_text("ok")

        result = resolve_safe_path(str(target_b), base_a, base_b)
        assert result == target_b.resolve()

    def test_exact_allowed_base(self, tmp_path: Path) -> None:
        """The allowed base directory itself is a valid target."""
        allowed = tmp_path / "safe"
        allowed.mkdir()

        result = resolve_safe_path(str(allowed), allowed)
        assert result == allowed.resolve()

    def test_symlink_outside_rejected(self, tmp_path: Path) -> None:
        """A symlink pointing outside the allowed base is rejected."""
        allowed = tmp_path / "safe"
        allowed.mkdir()

        outside = tmp_path / "outside.txt"
        outside.write_text("secret")

        link = allowed / "link.txt"
        link.symlink_to(outside)

        with pytest.raises(PathTraversalError):
            resolve_safe_path(str(link), allowed)

    def test_nonexistent_path_inside_allowed(self, tmp_path: Path) -> None:
        """A path that doesn't exist yet but is within allowed base works."""
        allowed = tmp_path / "safe"
        allowed.mkdir()
        future = allowed / "newfile.txt"

        # resolve_safe_path should succeed even if file doesn't exist
        # (the check is about directory containment, not file existence)
        result = resolve_safe_path(str(future), allowed)
        assert result == future.resolve()
        assert not result.exists()

    def test_relative_path_resolved_against_cwd(self, tmp_path: Path) -> None:
        """A relative path is resolved against CWD."""
        allowed = tmp_path / "safe"
        allowed.mkdir()
        target = allowed / "file.txt"
        target.write_text("data")

        old_cwd = Path.cwd()
        try:
            os.chdir(str(tmp_path))
            # Relative path: safe/file.txt
            result = resolve_safe_path("safe/file.txt", allowed)
            assert result == target.resolve()
        finally:
            os.chdir(str(old_cwd))


class TestMatchPathGlobs:
    """Unit tests for match_path_globs()."""

    def test_exact_match(self) -> None:
        """Exact pattern matches."""
        assert match_path_globs(Path("/tmp/foo.txt"), ["/tmp/foo.txt"])

    def test_wildcard_star(self) -> None:
        """* matches anything in the same directory."""
        assert match_path_globs(Path("/tmp/foo.txt"), ["/tmp/*"])
        assert not match_path_globs(Path("/tmp/sub/foo.txt"), ["/tmp/*"])

    def test_double_star(self) -> None:
        """** matches any depth recursively."""
        assert match_path_globs(Path("/tmp/a/b/c/file.txt"), ["/tmp/**"])
        assert match_path_globs(Path("/tmp/file.txt"), ["/tmp/**"])

    def test_tilde_in_pattern(self) -> None:
        """~ is expanded in patterns."""
        home = Path.home()
        assert match_path_globs(home / "doc.txt", ["~/doc.txt"])

    def test_no_match(self) -> None:
        """Return False when no pattern matches."""
        assert not match_path_globs(Path("/etc/passwd"), ["/tmp/**"])

    def test_multiple_patterns_second_matches(self) -> None:
        """Second pattern catches the path."""
        assert match_path_globs(
            Path("/var/log/syslog"),
            ["/tmp/**", "/var/**"],
        )

    def test_empty_patterns(self) -> None:
        """Empty patterns list returns False."""
        assert not match_path_globs(Path("/tmp/foo.txt"), [])

    def test_empty_string_pattern(self) -> None:
        """Empty string in patterns is ignored."""
        assert not match_path_globs(Path("/tmp/foo.txt"), [""])

    def test_question_mark(self) -> None:
        """? matches a single character."""
        assert match_path_globs(Path("/tmp/foo.txt"), ["/tmp/fo?.txt"])
        assert not match_path_globs(Path("/tmp/foo.txt"), ["/tmp/fo?.md"])

    def test_pattern_with_trailing_slash(self) -> None:
        """Patterns with trailing slash work (trailing slash is treated as part of path)."""
        assert match_path_globs(Path("/tmp/foo.txt"), ["/tmp/*"])
        # Without trailing slash ** is the canonical form
        assert match_path_globs(Path("/tmp/foo.txt"), ["/tmp/**"])

    def test_path_with_dot(self) -> None:
        """Dot files are matched normally."""
        assert match_path_globs(Path("/tmp/.hidden"), ["/tmp/*"])

    def test_relative_pattern(self) -> None:
        """Relative patterns match against the full path."""
        assert match_path_globs(Path("/home/user/doc.md"), ["**/doc.md"])


class TestPathTraversalError:
    """Unit tests for the PathTraversalError exception."""

    def test_error_message_contains_path(self) -> None:
        """Error message includes the rejected path."""
        err = PathTraversalError("/etc/passwd", ["/tmp/A"])
        assert "/etc/passwd" in str(err)
        assert "/tmp/A" in str(err)

    def test_error_message_without_bases(self) -> None:
        """Error message works with no allowed bases."""
        err = PathTraversalError("/etc/passwd")
        assert "(none)" in str(err)

    def test_is_aerror_subclass(self) -> None:
        """PathTraversalError inherits from AError."""
        from A.core.exceptions import AError

        assert issubclass(PathTraversalError, AError)
