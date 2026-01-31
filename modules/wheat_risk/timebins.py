"""Weekly time bin utilities.

This module is pure-Python and intentionally has no Earth Engine dependency.

The public API is `week_bins(start_date, end_date)`, which returns contiguous
weekly bins as ISO date strings.

Date semantics:
- Inputs use inclusive end-date semantics: the provided `end_date` is included.
- Each returned bin is an inclusive [bin_start, bin_end] date range.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Union


DateLike = Union[str, date, datetime]


def _to_date(value: DateLike, *, name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            raise ValueError(f"{name} must be an ISO date 'YYYY-MM-DD'") from e

    raise TypeError(f"{name} must be a str, date, or datetime")


def week_bins(start_date: DateLike, end_date: DateLike) -> list[tuple[str, str]]:
    """Return contiguous weekly bins.

    Args:
        start_date: Range start date.
        end_date: Range end date.

    Returns:
        List of (bin_start, bin_end) ISO date strings.

        Inputs use inclusive end-date semantics.
        Bins are contiguous and non-overlapping. Each bin is at most 7 days
        (inclusive). The last bin may be shorter.

    Raises:
        ValueError: If start_date is after end_date.
        TypeError: If inputs are not supported date-like types.
    """

    start = _to_date(start_date, name="start_date")
    end = _to_date(end_date, name="end_date")

    if start > end:
        raise ValueError("start_date must be <= end_date")

    if start == end:
        d = start.isoformat()
        return [(d, d)]

    bins: list[tuple[str, str]] = []
    cur = start

    while cur <= end:
        bin_end = cur + timedelta(days=6)
        if bin_end > end:
            bin_end = end
        bins.append((cur.isoformat(), bin_end.isoformat()))
        cur = bin_end + timedelta(days=1)

    return bins
