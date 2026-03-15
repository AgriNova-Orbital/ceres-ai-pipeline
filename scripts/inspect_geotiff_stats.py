"""Inspect per-band pixel statistics for raw GeoTIFF inputs.

Designed for GEE exports where nodata is stored as NaN float32 (nodata=null
in raster metadata). Prints NaN ratio, finite ratio, zero ratio, and
nanmin/nanmax/nanmean for each requested band, helping users understand
data quality before running the expensive build step.

Usage:
    uv run scripts/inspect_geotiff_stats.py --input-dir data/raw/france_2025_weekly
    uv run scripts/inspect_geotiff_stats.py --input-dir data/raw/france_2025_weekly --bands 1,11

Output format (one block per file, sorted by filename):
    ====...====
    file: fr_wheat_feat_2025_data_001.tif
    global_nan_ratio: 0.769
    global_finite_ratio: 0.231
    band_1_nan_ratio: 0.999
    band_1_zero_ratio: 0.0
    band_1_min: -0.283
    band_1_max: 0.911
    band_1_mean: 0.513
    band_11_nan_ratio: 0.999
    ...
    ====...====
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import rasterio
except ImportError as e:
    raise SystemExit(
        "rasterio is required. Install it with: uv pip install rasterio"
    ) from e

_SEP = "=" * 100


def _compute_band_stats(data: np.ndarray, total_pixels: int) -> dict[str, float]:
    """Compute nan_ratio, zero_ratio, finite min/max/mean for a 2-D band array."""
    flat = data.ravel()
    nan_count = int(np.isnan(flat).sum())
    zero_count = int((flat == 0.0).sum())  # NaN != 0.0, so NaNs are excluded
    finite = flat[np.isfinite(flat)]
    return {
        "nan_ratio": nan_count / total_pixels,
        "zero_ratio": zero_count / total_pixels,
        "min": float(finite.min()) if finite.size > 0 else float("nan"),
        "max": float(finite.max()) if finite.size > 0 else float("nan"),
        "mean": float(finite.mean()) if finite.size > 0 else float("nan"),
    }


def inspect_file(path: Path, band_indices: Sequence[int] | None = None) -> None:
    """Print pixel statistics for one GeoTIFF file.

    Args:
        path: Path to the GeoTIFF.
        band_indices: 1-based band numbers to report. If None, reports the
            first and last band (matching the production profile: first feature
            band and the risk band).
    """
    with rasterio.open(path) as ds:
        band_count = ds.count
        total_pixels_per_band = ds.width * ds.height

        # Read all bands at once for the global NaN ratio.
        all_data = ds.read().astype(np.float32)  # (C, H, W)

    total_pixels_all = all_data.size
    global_nan_count = int(np.isnan(all_data).sum())
    global_nan_ratio = global_nan_count / total_pixels_all
    global_finite_ratio = 1.0 - global_nan_ratio

    if band_indices is None:
        band_indices = [1, band_count] if band_count > 1 else [1]
    # Clamp to valid range and deduplicate while preserving order.
    seen: set[int] = set()
    valid_bands: list[int] = []
    for b in band_indices:
        if 1 <= b <= band_count and b not in seen:
            valid_bands.append(b)
            seen.add(b)

    print(_SEP)
    print(f"file: {path.name}")
    print(f"global_nan_ratio: {global_nan_ratio}")
    print(f"global_finite_ratio: {global_finite_ratio}")
    for b in valid_bands:
        band_data = all_data[b - 1]  # 0-indexed into loaded array
        stats = _compute_band_stats(band_data, total_pixels_per_band)
        prefix = f"band_{b}"
        print(f"{prefix}_nan_ratio: {stats['nan_ratio']}")
        print(f"{prefix}_zero_ratio: {stats['zero_ratio']}")
        print(f"{prefix}_min: {stats['min']}")
        print(f"{prefix}_max: {stats['max']}")
        print(f"{prefix}_mean: {stats['mean']}")
    print(_SEP)


def run_inspect(
    input_dir: Path,
    band_indices: Sequence[int] | None = None,
) -> None:
    """Inspect all GeoTIFFs in *input_dir*, sorted by filename."""
    files = sorted(input_dir.glob("*.tif*"), key=lambda p: p.name)

    if not files:
        print(f"No GeoTIFF files found in {input_dir}")
        return

    print(f"Inspecting {len(files)} GeoTIFF file(s) in {input_dir}")
    for path in files:
        try:
            inspect_file(path, band_indices=band_indices)
        except Exception as exc:
            print(f"ERROR reading {path.name}: {exc}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Print per-band pixel statistics (NaN ratio, finite ratio, zero ratio, "
            "min, max, mean) for GeoTIFF files in an input directory. "
            "Designed for GEE exports where masked pixels are stored as NaN float32."
        )
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing GeoTIFF (.tif/.tiff) files to inspect.",
    )
    p.add_argument(
        "--bands",
        type=str,
        default=None,
        help=(
            "Comma-separated 1-based band numbers to report per file "
            "(e.g. '1,11'). Defaults to the first and last band."
        ),
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    band_indices: list[int] | None = None
    if args.bands is not None:
        try:
            band_indices = [int(b.strip()) for b in args.bands.split(",") if b.strip()]
        except ValueError:
            raise SystemExit(f"Invalid --bands value: {args.bands!r}. Expected comma-separated integers.")

    if not args.input_dir.is_dir():
        raise SystemExit(f"--input-dir does not exist or is not a directory: {args.input_dir}")

    run_inspect(args.input_dir, band_indices=band_indices)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
