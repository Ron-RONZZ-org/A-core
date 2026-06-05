"""Partial date/time parsing utilities for A plugins.

Ported from autish-legacy (taglibro.py, kalendaro.py).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional


def parse_partial_date(token: str, *, ref: Optional[date] = None) -> date:
    """Parse a partial date token into a ``datetime.date``.

    Supports three formats:
    - ``YYYYMMDD`` (8 digits) — full date
    - ``MMDD`` (4 digits) — month+day, year from ``ref``
    - ``DD`` (2 digits) — day, month+year from ``ref``

    Args:
        token: Date string in YYYYMMDD, MMDD, or DD format.
        ref: Reference date for filling in missing parts.
             Defaults to ``date.today()``.

    Returns:
        Parsed ``date`` object.

    Raises:
        ValueError: If token is empty, non-numeric, or has invalid length.
    """
    raw = str(token).strip()
    if not raw or not raw.isdigit():
        raise ValueError(
            f"Nevalida dato: {token!r}. Uzu YYYYMMDD, MMDD aŭ DD."
        )
    today = ref or date.today()
    if len(raw) == 8:
        return datetime.strptime(raw, "%Y%m%d").date()
    if len(raw) == 4:
        return datetime.strptime(f"{today.year}{raw}", "%Y%m%d").date()
    if len(raw) == 2:
        return datetime.strptime(
            f"{today.year}{today.month:02d}{raw}", "%Y%m%d"
        ).date()
    raise ValueError(
        f"Nevalida dato-formo: {token!r}. Uzu YYYYMMDD (8), MMDD (4), aŭ DD (2)."
    )


def parse_partial_datetime(
    token: Optional[str] = None, *, ref: Optional[date] = None
) -> str:
    """Parse a partial datetime token into an ISO 8601 string (UTC).

    Format: ``YYYYMMDD_HHMM``, ``MMDD_HHMM``, or ``DD_HHMM``.
    If time is omitted, defaults to the current time.
    If the entire token is ``None`` or empty, returns the current time.

    Args:
        token: Datetime string in YYYYMMDD_HHMM (or shorter date + _HHMM).
               If ``None`` or empty, returns current UTC time.
        ref: Reference date for filling in missing date parts.

    Returns:
        ISO 8601 datetime string in UTC (e.g. ``"2026-04-21T09:15:00+00:00"``).

    Raises:
        ValueError: If the token has an invalid date or time portion.
    """
    if not token or not str(token).strip():
        return datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        ).isoformat()

    raw = str(token).strip()
    now_local = datetime.now().astimezone()

    if "_" in raw:
        date_part, time_part = raw.split("_", 1)
        date_part = date_part.strip()
        time_part = time_part.strip()
    else:
        date_part = raw
        time_part = f"{now_local.hour:02d}{now_local.minute:02d}"

    if not re.fullmatch(r"\d{4}", time_part):
        raise ValueError(
            f"Nevalida tempo: {time_part!r}. Uzu HHMM (ekz: 0930)."
        )

    d = parse_partial_date(date_part, ref=ref or now_local.date())
    hh = int(time_part[:2])
    mm = int(time_part[2:])

    if hh > 23 or mm > 59:
        raise ValueError(f"Nevalida horo/minuto: {hh:02d}:{mm:02d}.")

    dt_local = datetime(
        d.year,
        d.month,
        d.day,
        hh,
        mm,
        tzinfo=now_local.tzinfo or timezone.utc,
    )
    return (
        dt_local.astimezone(timezone.utc)
        .replace(second=0, microsecond=0)
        .isoformat()
    )


def date_range(
    dato_de: str | None = None,
    dato_gis: str | None = None,
    *,
    ref: date | None = None,
) -> tuple[str | None, str | None]:
    """Convert partial date bounds into ISO 8601 range strings (start/end of day).

    Strips hyphens from input, then calls :func:`parse_partial_date` on each
    bound, returning UTC ISO strings for start-of-day (``dato_de``) and
    end-of-day (``dato_gis``).

    A ``None`` bound means "unbounded" — the corresponding return value is
    also ``None``.

    Args:
        dato_de: Start date (YYYYMMDD, MMDD, DD, or YYYY-MM-DD).
        dato_gis: End date (same formats).
        ref: Reference date for filling in missing parts in partial tokens.
             Defaults to ``date.today()``.

    Returns:
        Tuple ``(iso_start, iso_end)`` where each is an ISO 8601 string
        or ``None`` if the corresponding input was ``None``.

    Raises:
        ValueError: If a token cannot be parsed.
    """
    def _strip_hyphens(val: str | None) -> str | None:
        if val is None:
            return None
        return val.strip().replace("-", "")

    start: str | None = None
    end: str | None = None

    raw_de = _strip_hyphens(dato_de)
    raw_gis = _strip_hyphens(dato_gis)

    if raw_de:
        d = parse_partial_date(raw_de, ref=ref)
        start = d.isoformat() + "T00:00:00+00:00"
    if raw_gis:
        d = parse_partial_date(raw_gis, ref=ref)
        end = d.isoformat() + "T23:59:59+00:00"

    return (start, end)


__all__ = [
    "parse_partial_date",
    "parse_partial_datetime",
    "date_range",
]
