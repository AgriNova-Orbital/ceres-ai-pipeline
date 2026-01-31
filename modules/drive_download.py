from __future__ import annotations

import re
from typing import Any


_PAT_WEEK = re.compile(r"^fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
_PAT_DATA = re.compile(r"^fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
_PAT_WEEK_IN_SUFFIX = re.compile(r"\bW(\d{2})\b", re.IGNORECASE)
_PAT_NUM_IN_SUFFIX = re.compile(r"\b(\d{1,3})\b")


def _sort_key_for_name(name: str) -> tuple[int, int, str]:
    """Return a stable sort key for a GeoTIFF name.

    Supports both:
    - fr_wheat_feat_YYYYWww.tif
    - fr_wheat_feat_YYYY_data_<suffix>.tif (tries to extract Wxx from suffix)
    """

    m = _PAT_WEEK.match(name)
    if m:
        return int(m.group(1)), int(m.group(2)), name

    m = _PAT_DATA.match(name)
    if m:
        year = int(m.group(1))
        suffix = m.group(2)
        m2 = _PAT_WEEK_IN_SUFFIX.search(suffix)
        if m2:
            return year, int(m2.group(1)), name
        m3 = _PAT_NUM_IN_SUFFIX.search(suffix)
        if m3:
            return year, int(m3.group(1)), name
        # Unknown suffix ordering; keep week=0 and sort by name for stability.
        return year, 0, name

    # Unknown pattern; push to the end.
    return 9999, 99, name


def filter_weekly_geotiffs(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter and sort weekly GeoTIFF files from a Drive listing."""

    out: list[dict[str, Any]] = []
    for f in files:
        name = str(f.get("name", ""))
        if not name.lower().endswith((".tif", ".tiff")):
            continue
        if _PAT_WEEK.match(name) or _PAT_DATA.match(name):
            out.append(f)

    # If files use numeric reverse suffix (001 newest), sort those by number DESC
    # to get oldest->newest.
    numeric_map: dict[str, int] = {}
    for f in out:
        name = str(f.get("name", ""))
        m = _PAT_DATA.match(name)
        if not m:
            continue
        suffix = m.group(2)
        if _PAT_WEEK_IN_SUFFIX.search(suffix):
            continue
        m3 = _PAT_NUM_IN_SUFFIX.search(suffix)
        if m3:
            numeric_map[name] = int(m3.group(1))

    def sort_key(f: dict[str, Any]) -> tuple[int, int, int, str]:
        name = str(f.get("name", ""))
        y, w, _ = _sort_key_for_name(name)
        if name in numeric_map:
            # Put numeric-suffix files after explicit Wxx files for the same year
            # (avoids mixing incomparable schemes). Within numeric suffix, sort by DESC.
            return y, 1, -numeric_map[name], name
        return y, 0, w, name

    out.sort(key=sort_key)
    return out
