"""Verify the band complementarity property of weekly wheat-risk GeoTIFFs.

GEE exports for this pipeline store band_1 (feature band, e.g. NDVI-derived)
and band_last (risk band) such that they are mathematical complements:

    band_1 + band_last = 1.0  (for every valid, finite pixel)

Due to float32 representation, differences are bounded by the float32 machine
epsilon (~1.192e-07). This script reports the mean and maximum absolute
deviation from perfect complementarity for each file, giving a quick sanity
check that the GeoTIFF export pipeline has not introduced corruption.

Usage:
    uv run scripts/verify_geotiff_band_complement.py --input-dir data/raw/france_2025_weekly

Output format (one line per file, sorted by filename):
    fr_wheat_feat_2025_data_001.tif mean_abs_diff= 1.45e-08 max_abs_diff= 5.96e-08
    fr_wheat_feat_2025_data_002.tif mean_abs_diff= 1.38e-08 max_abs_diff= 1.19e-07
    ...

If no valid (finite) pixels exist in a file, both values are reported as nan.
"""
from __future__ import annotations

import argparse
import math
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


def _check_complement(path: Path, band_a: int = 1, band_b: int | None = None) -> tuple[float, float]:
    """Compute mean and max absolute deviation of ``band_a + band_b`` from 1.0.

    Args:
        path: Path to the GeoTIFF file.
        band_a: 1-based index of the first band (default: 1).
        band_b: 1-based index of the second band. Defaults to the last band.

    Returns:
        ``(mean_abs_diff, max_abs_diff)`` computed over pixels where both bands
        are finite. Returns ``(nan, nan)`` if no valid pixels are found.
    """
    with rasterio.open(path) as ds:
        if band_b is None:
            band_b = ds.count
        data_a = ds.read(indexes=band_a).astype(np.float64)
        data_b = ds.read(indexes=band_b).astype(np.float64)

    valid = np.isfinite(data_a) & np.isfinite(data_b)
    if not valid.any():
        return math.nan, math.nan

    diff = np.abs(data_a[valid] + data_b[valid] - 1.0)
    return float(diff.mean()), float(diff.max())


def run_verify(
    input_dir: Path,
    band_a: int = 1,
    band_b: int | None = None,
) -> None:
    """Print band complement check results for all GeoTIFFs in *input_dir*.

    Files are processed in sorted filename order. One line is printed per file.
    """
    files = sorted(input_dir.glob("*.tif*"), key=lambda p: p.name)

    if not files:
        print(f"No GeoTIFF files found in {input_dir}")
        return

    for path in files:
        try:
            mean_diff, max_diff = _check_complement(path, band_a=band_a, band_b=band_b)
            print(f"{path.name} mean_abs_diff= {mean_diff} max_abs_diff= {max_diff}")
        except Exception as exc:
            print(f"ERROR reading {path.name}: {exc}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Verify that band_a + band_b ≈ 1.0 for every valid pixel in each "
            "GeoTIFF (band complementarity check). Differences are expected to "
            "be ≤ float32 machine epsilon (~1.192e-07) for correctly exported files."
        )
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing GeoTIFF (.tif/.tiff) files to verify.",
    )
    p.add_argument(
        "--band-a",
        type=int,
        default=1,
        help="1-based index of the first band (default: 1).",
    )
    p.add_argument(
        "--band-b",
        type=int,
        default=None,
        help="1-based index of the second band (default: last band in the file).",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.input_dir.is_dir():
        raise SystemExit(
            f"--input-dir does not exist or is not a directory: {args.input_dir}"
        )

    run_verify(args.input_dir, band_a=args.band_a, band_b=args.band_b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
