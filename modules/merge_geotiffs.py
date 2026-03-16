from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


_PAT_WEEK = re.compile(r"^fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
_PAT_DATA = re.compile(r"^fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
_PAT_WEEK_IN_SUFFIX = re.compile(r"\bW(\d{2})\b", re.IGNORECASE)


def _group_key(name: str) -> str | None:
    m = _PAT_WEEK.match(name)
    if m:
        return f"{m.group(1)}W{m.group(2)}"
    m = _PAT_DATA.match(name)
    if m:
        year = m.group(1)
        suffix = m.group(2)
        m2 = _PAT_WEEK_IN_SUFFIX.search(suffix)
        if m2:
            return f"{year}W{m2.group(1)}"
        return f"{year}_{suffix}"
    return None


def group_split_files(directory: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(directory.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".tif", ".tiff"):
            continue
        key = _group_key(p.name)
        if key is not None:
            groups[key].append(p)
    return {k: sorted(v) for k, v in groups.items()}


def has_gdal() -> bool:
    try:
        from osgeo import gdal  # noqa: F401

        return True
    except ImportError:
        return False


def merge_split_geotiffs(
    directory: Path,
    *,
    out_dir: Path | None = None,
    compress: str = "LZW",
) -> list[Path]:
    try:
        from osgeo import gdal
    except ImportError:
        raise ImportError(
            "GDAL is required for merging. Install with: pip install gdal"
        )

    groups = group_split_files(directory)
    if out_dir is None:
        out_dir = directory / "_merged"
    out_dir.mkdir(parents=True, exist_ok=True)

    merged: list[Path] = []
    for key, files in groups.items():
        if len(files) < 2:
            continue
        out_path = out_dir / f"fr_wheat_feat_{key}.tif"
        vrt_path = out_dir / f"_tmp_{key}.vrt"
        try:
            gdal.BuildVRT(str(vrt_path), [str(f) for f in files])
            gdal.Translate(
                str(out_path),
                str(vrt_path),
                creationOptions=[f"COMPRESS={compress}"],
            )
            merged.append(out_path)
        finally:
            if vrt_path.exists():
                vrt_path.unlink()
    return merged
