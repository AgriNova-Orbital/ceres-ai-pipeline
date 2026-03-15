"""Build an NDVI time-series forecasting dataset from weekly GeoTIFFs.

Why this task?
--------------
Analysis of the France 2025 weekly GeoTIFFs shows that the "risk" band
(band_last) is almost exactly ``1 − band_1`` (NDVI) for every valid pixel —
the mean absolute deviation is < 2 × float32 machine epsilon. Training a
model with these labels causes severe **target leakage**: the model learns
``risk = 1 − ndvi`` rather than any genuine predictive signal.

This script builds a leakage-free supervised dataset instead:

    Input  X  ← feature bands (all except the risk band) from weeks t … t+W−1
    Target y  ← mean NDVI (band 1) of week t+W  (the *next* week)

This is strictly causal: the target is always one time-step in the future, so
no information from the target week leaks into the inputs.

Output format
-------------
::

    output-dir/
    ├── index.csv          # one row: npz_path (relative to output-dir)
    └── examples/
        └── patch_r{row:05d}_c{col:05d}_t{t_start:03d}.npz
            ├── X  (W, C+1, H_p, W_p) float32  – feature bands + valid mask
            ├── y  ()                  float32  – next-week mean NDVI (NaN if unavailable)
            └── M  (W, 1, H_p, W_p)   float32  – standalone valid mask

Usage
-----
::

    uv run scripts/build_ndvi_forecast_dataset.py \\
        --input-dir  data/raw/france_2025_weekly \\
        --output-dir data/ndvi_forecast/window4 \\
        --window-size 4 \\
        --patch-size  32 \\
        --step-size   16

    uv run scripts/build_ndvi_forecast_dataset.py --help
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.services.ndvi_forecast_service import run_ndvi_forecast_build


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Build a leakage-free NDVI time-series forecasting dataset.\n\n"
            "Each NPZ sample contains W consecutive weeks of feature bands as "
            "input (X) and next-week mean NDVI as the target (y)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory of weekly GeoTIFF files.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Root output directory for index.csv and examples/.",
    )
    p.add_argument(
        "--window-size",
        type=int,
        default=4,
        help="Number of input weeks per sample (default: 4).",
    )
    p.add_argument(
        "--patch-size",
        type=int,
        default=32,
        help="Spatial height/width of each patch in pixels (default: 32).",
    )
    p.add_argument(
        "--step-size",
        type=int,
        default=16,
        help="Stride between adjacent patch origins in pixels (default: 16).",
    )
    p.add_argument(
        "--min-valid-ratio",
        type=float,
        default=0.05,
        help=(
            "Minimum mean fraction of valid (non-NaN) pixels across the input "
            "window required to keep a sample (default: 0.05)."
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Number of parallel processes (0 = all CPUs, default: 0).",
    )
    p.add_argument(
        "--gdal-cache-mb",
        type=int,
        default=64,
        help="GDAL I/O cache per process in MiB (default: 64).",
    )
    p.add_argument(
        "--max-patches",
        type=int,
        default=None,
        help="Randomly sub-sample to at most this many spatial locations.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for spatial sub-sampling (default: 42).",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip build if output index.csv already exists.",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.input_dir.is_dir():
        raise SystemExit(
            f"--input-dir does not exist or is not a directory: {args.input_dir}"
        )

    run_ndvi_forecast_build(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        patch_size=args.patch_size,
        step_size=args.step_size,
        window_size=args.window_size,
        min_valid_ratio=args.min_valid_ratio,
        workers=args.workers,
        gdal_cache_mb=args.gdal_cache_mb,
        max_patches=args.max_patches,
        seed=args.seed,
        skip_existing=args.skip_existing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
