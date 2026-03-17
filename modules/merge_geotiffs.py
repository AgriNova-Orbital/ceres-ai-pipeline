from __future__ import annotations

import importlib
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from modules.wheat_risk.features import required_feature_names

FINAL_BANDS: tuple[str, ...] = required_feature_names() + ("risk",)

_PAT_WEEK = re.compile(r"^fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
_PAT_WEEK_TILE = re.compile(
    r"^fr_wheat_feat_(\d{4})W(\d{2})-\d+-\d+\.tif(?:f)?$",
    re.IGNORECASE,
)
_PAT_DATA = re.compile(r"^fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
_PAT_WEEK_IN_SUFFIX = re.compile(r"\bW(\d{2})\b", re.IGNORECASE)
_PAT_WEEK_KEY = re.compile(r"^\d{4}W\d{2}$", re.IGNORECASE)
_TMP_DIR_NAME = "._ingest_tmp"


def _group_key(name: str) -> str | None:
    m = _PAT_WEEK.match(name)
    if m:
        return f"{m.group(1)}W{m.group(2)}"
    m = _PAT_WEEK_TILE.match(name)
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


def _canonical_name_for_key(key: str) -> str:
    return f"fr_wheat_feat_{key}.tif"


def _staging_path(directory: Path, canonical_name: str) -> Path:
    tmp_dir = directory / _TMP_DIR_NAME
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir / canonical_name


def _cleanup_staging_dir(path: Path) -> None:
    try:
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def _import_gdal() -> Any:
    try:
        return importlib.import_module("osgeo.gdal")
    except ImportError as e:
        raise ImportError(
            "GDAL is required for merging. Install with: pip install gdal"
        ) from e


def _import_rasterio() -> Any:
    try:
        return importlib.import_module("rasterio")
    except ImportError as e:
        raise ImportError(
            "rasterio is required for GeoTIFF validation. Install with: uv pip install rasterio"
        ) from e


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
        _import_gdal()
        return True
    except ImportError:
        return False


def validate_canonical_geotiff(path: Path) -> dict[str, object]:
    if _PAT_WEEK.match(path.name) is None:
        raise RuntimeError(
            "Expected canonical weekly filename like fr_wheat_feat_YYYYWww.tif"
        )

    rasterio = _import_rasterio()

    try:
        with rasterio.open(path) as ds:
            if ds.width <= 0 or ds.height <= 0:
                raise RuntimeError(f"{path.name}: raster dimensions must be > 0")
            if ds.count != len(FINAL_BANDS):
                raise RuntimeError(
                    f"{path.name}: expected {len(FINAL_BANDS)} bands, got {ds.count}"
                )
            if any(str(dtype).lower() != "float32" for dtype in ds.dtypes):
                raise RuntimeError(f"{path.name}: expected float32 dtype for all bands")
            if ds.nodata is None or float(ds.nodata) != -32768.0:
                raise RuntimeError(f"{path.name}: expected nodata=-32768")
            if ds.crs is None:
                raise RuntimeError(f"{path.name}: CRS is required")

            descriptions = tuple((desc or "").strip() for desc in ds.descriptions)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Could not read canonical GeoTIFF {path.name}: {e}") from e

    warnings: list[str] = []
    present = [desc for desc in descriptions if desc]
    if not present:
        warnings.append(f"{path.name}: band descriptions missing")
    elif len(present) != len(FINAL_BANDS):
        warnings.append(f"{path.name}: band descriptions partially missing")
    elif tuple(descriptions) != FINAL_BANDS:
        warnings.append(
            f"{path.name}: unexpected band descriptions {list(descriptions)!r}"
        )

    return {
        "path": str(path),
        "warnings": warnings,
        "band_descriptions": list(descriptions),
    }


def _report_warnings(report: dict[str, object]) -> list[str]:
    values = report.get("warnings", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def _move_sources_to_tiles(directory: Path, key: str, sources: list[Path]) -> None:
    tiles_dir = directory / "_tiles" / key
    tiles_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        target = tiles_dir / src.name
        if target.exists():
            target.unlink()
        src.replace(target)


def _merge_into_canonical(
    directory: Path,
    *,
    key: str,
    sources: list[Path],
    compress: str,
) -> dict[str, object]:
    gdal = _import_gdal()
    canonical_name = _canonical_name_for_key(key)
    staged_path = _staging_path(directory, canonical_name)
    vrt_path = staged_path.with_suffix(".vrt")
    final_path = directory / canonical_name

    try:
        gdal.BuildVRT(str(vrt_path), [str(src) for src in sources])
        gdal.Translate(
            str(staged_path),
            str(vrt_path),
            creationOptions=[f"COMPRESS={compress}"],
        )
        report = validate_canonical_geotiff(staged_path)
        if final_path.exists():
            final_path.unlink()
        staged_path.replace(final_path)
        _move_sources_to_tiles(directory, key, sources)
        return report
    finally:
        if vrt_path.exists():
            vrt_path.unlink()
        if staged_path.exists():
            staged_path.unlink()
        _cleanup_staging_dir(staged_path.parent)


def _normalize_single_source(
    directory: Path, *, key: str, source: Path
) -> dict[str, object]:
    canonical_name = _canonical_name_for_key(key)
    staged_path = _staging_path(directory, canonical_name)
    final_path = directory / canonical_name

    try:
        shutil.copy2(source, staged_path)
        report = validate_canonical_geotiff(staged_path)
        if final_path.exists():
            final_path.unlink()
        source.replace(final_path)
        return report
    finally:
        if staged_path.exists():
            staged_path.unlink()
        _cleanup_staging_dir(staged_path.parent)


def ingest_downloaded_geotiffs(
    directory: Path,
    *,
    compress: str = "LZW",
) -> dict[str, object]:
    merged_weeks: list[str] = []
    normalized_weeks: list[str] = []
    failed_weeks: list[str] = []
    unknown_files: list[str] = []
    warnings: list[str] = []

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".tif", ".tiff"):
            continue
        if _group_key(path.name) is None:
            unknown_files.append(path.name)

    for key, files in sorted(group_split_files(directory).items()):
        if _PAT_WEEK_KEY.match(key) is None:
            continue

        canonical_files = [p for p in files if _PAT_WEEK.match(p.name)]
        transport_files = [p for p in files if _PAT_WEEK.match(p.name) is None]

        if canonical_files:
            try:
                report = validate_canonical_geotiff(canonical_files[0])
            except Exception as e:
                failed_weeks.append(key)
                warnings.append(f"{key}: {e}")
                continue

            warnings.extend(_report_warnings(report))
            if transport_files:
                warnings.append(
                    f"{key}: canonical GeoTIFF already exists; leaving {len(transport_files)} transport file(s) in place"
                )
            continue

        try:
            if len(transport_files) == 1:
                report = _normalize_single_source(
                    directory,
                    key=key,
                    source=transport_files[0],
                )
                normalized_weeks.append(key)
            elif len(transport_files) >= 2:
                report = _merge_into_canonical(
                    directory,
                    key=key,
                    sources=transport_files,
                    compress=compress,
                )
                merged_weeks.append(key)
            else:
                continue
        except Exception as e:
            failed_weeks.append(key)
            warnings.append(f"{key}: {e}")
            continue

        warnings.extend(_report_warnings(report))

    return {
        "merged_weeks": merged_weeks,
        "single_tile_weeks_normalized": normalized_weeks,
        "failed_weeks": failed_weeks,
        "unknown_files": unknown_files,
        "warnings": warnings,
    }


def merge_split_geotiffs(
    directory: Path,
    *,
    out_dir: Path | None = None,
    compress: str = "LZW",
) -> list[Path]:
    gdal = _import_gdal()

    groups = group_split_files(directory)
    if out_dir is None:
        out_dir = directory / "_merged"
    out_dir.mkdir(parents=True, exist_ok=True)

    merged: list[Path] = []
    for key, files in groups.items():
        if len(files) < 2:
            continue
        out_path = out_dir / _canonical_name_for_key(key)
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
