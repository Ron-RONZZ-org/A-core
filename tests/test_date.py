"""Tests for A.utils.date module."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest


class TestParsePartialDate:
    """Tests for parse_partial_date."""

    def test_full_yyyymmdd(self):
        """8-digit YYYYMMDD parses correctly."""
        from A.utils.date import parse_partial_date

        result = parse_partial_date("20260421")
        assert result == date(2026, 4, 21)

    def test_mmdd_with_ref(self):
        """4-digit MMDD uses year from ref."""
        from A.utils.date import parse_partial_date

        result = parse_partial_date("0421", ref=date(2026, 5, 1))
        assert result == date(2026, 4, 21)

    def test_dd_with_ref(self):
        """2-digit DD uses month+year from ref."""
        from A.utils.date import parse_partial_date

        result = parse_partial_date("21", ref=date(2026, 4, 1))
        assert result == date(2026, 4, 21)

    def test_default_ref_is_today(self):
        """When ref is None, uses date.today()."""
        from A.utils.date import parse_partial_date

        # Can't easily test dynamic today, but should not raise
        result = parse_partial_date("01")
        assert isinstance(result, date)

    def test_empty_string_raises(self):
        """Empty token raises ValueError."""
        from A.utils.date import parse_partial_date

        with pytest.raises(ValueError):
            parse_partial_date("")

    def test_non_digit_raises(self):
        """Non-numeric token raises ValueError."""
        from A.utils.date import parse_partial_date

        with pytest.raises(ValueError):
            parse_partial_date("abcd")

    def test_invalid_length_raises(self):
        """Token with invalid digit length raises ValueError."""
        from A.utils.date import parse_partial_date

        with pytest.raises(ValueError):
            parse_partial_date("123")  # 3 digits — not valid

    def test_invalid_date_raises(self):
        """Invalid date (e.g. month 13) raises ValueError."""
        from A.utils.date import parse_partial_date

        with pytest.raises(ValueError):
            parse_partial_date("1321")


class TestParsePartialDatetime:
    """Tests for parse_partial_datetime."""

    def test_full_format(self):
        """Full YYYYMMDD_HHMM parses correctly (converts to UTC)."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("20260421_0915")
        # 09:15 local time → should be a valid UTC time on April 21
        assert "2026-04-21" in result
        assert "T" in result
        assert result.endswith("+00:00")

    def test_mmdd_format(self):
        """MMDD_HHMM uses year from ref date."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("0421_0915", ref=date(2026, 5, 1))
        assert "2026-04-21" in result
        assert result.endswith("+00:00")

    def test_dd_format(self):
        """DD_HHMM uses month+year from ref."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("21_0915", ref=date(2026, 4, 1))
        assert "2026-04-21" in result
        assert result.endswith("+00:00")

    def test_date_only_defaults_time_to_now(self):
        """When time is omitted, defaults to current time."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("20260421")
        assert "2026-04-21T" in result

    def test_none_returns_now(self):
        """None input returns current UTC time."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime(None)
        assert "T" in result
        assert result.endswith("+00:00")

    def test_empty_returns_now(self):
        """Empty string returns current UTC time."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("")
        assert "T" in result
        assert result.endswith("+00:00")

    def test_invalid_time_raises(self):
        """Invalid HHMM time raises ValueError."""
        from A.utils.date import parse_partial_datetime

        with pytest.raises(ValueError):
            parse_partial_datetime("20260421_2560")

    def test_invalid_date_raises(self):
        """Invalid date raises ValueError."""
        from A.utils.date import parse_partial_datetime

        with pytest.raises(ValueError):
            parse_partial_datetime("20261301_0000")

    def test_missing_underscore_date_only(self):
        """Date without underscore still works (time defaults to now)."""
        from A.utils.date import parse_partial_datetime

        result = parse_partial_datetime("20260421")
        assert "2026-04-21" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
