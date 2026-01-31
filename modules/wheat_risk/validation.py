from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from numbers import Real


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_iso_date(value: str, *, name: str) -> str:
    """Validate a strict ISO date string.

    Accepts only the canonical form: YYYY-MM-DD.
    """

    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        raise ValueError(f"{name} must be an ISO date 'YYYY-MM-DD'")

    try:
        d = date.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"{name} must be an ISO date 'YYYY-MM-DD'") from e

    return d.isoformat()


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    """Validate and normalize an inclusive [start_date, end_date] range."""

    start_s = validate_iso_date(start_date, name="start_date")
    end_s = validate_iso_date(end_date, name="end_date")

    start = date.fromisoformat(start_s)
    end = date.fromisoformat(end_s)
    if start > end:
        raise ValueError("start_date must be <= end_date")

    return (start_s, end_s)


def validate_bbox(bbox: Sequence[object]) -> tuple[float, float, float, float]:
    """Validate and normalize a bbox.

    Expected format: [min_lon, min_lat, max_lon, max_lat].
    """

    if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence):
        raise ValueError(
            "bbox must be a sequence of 4 numbers [min_lon, min_lat, max_lon, max_lat]"
        )

    n = len(bbox)
    if n != 4:
        raise ValueError(
            "bbox must have exactly 4 elements [min_lon, min_lat, max_lon, max_lat]; "
            f"got {n}: {bbox!r}"
        )

    vals: list[float] = []
    for i, v in enumerate(bbox):
        if isinstance(v, bool) or not isinstance(v, Real):
            raise ValueError(
                f"bbox[{i}] must be a real number, got {type(v).__name__}: {v!r}"
            )
        vals.append(float(v))

    lon_min, lat_min, lon_max, lat_max = vals

    if not (lon_min < lon_max) or not (lat_min < lat_max):
        raise ValueError(
            "bbox must satisfy min_lon < max_lon and min_lat < max_lat; "
            f"got [{lon_min}, {lat_min}, {lon_max}, {lat_max}]"
        )

    if not (-180.0 <= lon_min <= 180.0) or not (-180.0 <= lon_max <= 180.0):
        raise ValueError(
            "longitude must be within [-180, 180]; "
            f"got min_lon={lon_min}, max_lon={lon_max}"
        )
    if not (-90.0 <= lat_min <= 90.0) or not (-90.0 <= lat_max <= 90.0):
        raise ValueError(
            "latitude must be within [-90, 90]; "
            f"got min_lat={lat_min}, max_lat={lat_max}"
        )

    return (lon_min, lat_min, lon_max, lat_max)
