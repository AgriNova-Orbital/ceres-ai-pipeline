"""NDVI time-series forecasting dataset builder.

Why this task instead of supervised risk prediction
---------------------------------------------------
Statistical analysis of the France 2025 weekly GeoTIFFs confirms that
``band_last`` (the "risk" band) is almost exactly ``1 − band_1`` (NDVI) for
every valid pixel — the mean absolute difference is < 2 × float32 machine
epsilon. This means the risk labels are *derived from* the input features at
the same time-step, causing severe target leakage: a model trained on this
data would simply memorise ``risk = 1 − ndvi`` rather than learning any
genuine predictive signal.

The NDVI forecasting task avoids this entirely by:

* Using only feature bands (all except the last risk band) as inputs.
* Predicting the **next week's** NDVI (band 1) from the **previous W weeks'**
  feature bands — a strictly causal, leakage-free prediction.

NPZ file format (one file per spatial patch × time-window)
-----------------------------------------------------------
Each ``.npz`` file saved by this module contains:

``X``   ``(W, C+1, H_p, W_p)`` float32
        Feature bands for weeks ``t … t+W-1``, with NaN/nodata pixels
        imputed to 0.  Channel ``C`` (last) is the float32 valid mask
        (1 = observed, 0 = imputed).

``y``   scalar float32
        Mean NDVI (band 1) of week ``t+W`` over valid pixels.  ``NaN``
        when no valid pixels exist in that week's target window.

``M``   ``(W, 1, H_p, W_p)`` float32
        Standalone validity mask (same data as the last channel of ``X``).

The dataset is compatible with ``modules.wheat_risk.dataset.WheatRiskNpzSequenceDataset``
when the caller sets ``in_channels = X.shape[1]``.

Usage
-----
::

    uv run scripts/build_ndvi_forecast_dataset.py \\
        --input-dir  data/raw/france_2025_weekly \\
        --output-dir data/ndvi_forecast/window4 \\
        --window-size 4 \\
        --patch-size  32 \\
        --step-size   16 \\
        --min-valid-ratio 0.05

See ``scripts/build_ndvi_forecast_dataset.py --help`` for all options.
"""

from __future__ import annotations

import atexit
import csv
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from tqdm import tqdm

try:
    import rasterio
except ImportError as e:
    raise ImportError(
        "rasterio is required. Install it with: uv pip install rasterio"
    ) from e

# ---------------------------------------------------------------------------
# Per-worker globals (used by multiprocessing.Pool initializer pattern)
# ---------------------------------------------------------------------------
_WORKER_SRCS: list[Any | None] | None = None
_WORKER_FEATURE_BANDS: list[int] | None = None
_WORKER_NDVI_BAND: int = 1
_WORKER_PATCH_SIZE: int = 32
_WORKER_EXAMPLES_DIR: Path | None = None
_WORKER_WINDOW_SIZE: int = 4
_WORKER_MIN_VALID_RATIO: float = 0.05


def _close_srcs(srcs: Sequence[Any | None]) -> None:
    for s in srcs:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass


def _build_mask_and_features(src: Any, feature_bands: Sequence[int], win: tuple) -> tuple[np.ndarray, np.ndarray]:
    """Read feature bands and build a ``(1, H, W)`` float32 valid mask.

    Combines the raster nodata mask (``read_masks``) with a finite-value check
    so that both explicit ``nodata`` pixels and NaN-stored GEE invalids are
    handled correctly.

    Returns:
        ``(mask, feat)`` where *mask* is ``(1, H, W)`` float32 (1=valid, 0=invalid)
        and *feat* is ``(C, H, W)`` float32 with the raw band values.
    """
    band_masks = src.read_masks(indexes=list(feature_bands), window=win)  # (C, H, W)
    valid_from_mask = (band_masks > 0).all(axis=0, keepdims=True)  # (1, H, W)
    feat = src.read(indexes=list(feature_bands), window=win).astype(np.float32, copy=False)
    valid_from_finite = np.isfinite(feat).all(axis=0, keepdims=True)
    return (valid_from_mask & valid_from_finite).astype(np.float32), feat


def _ndvi_nanmean(src: Any, ndvi_band: int, win: tuple) -> np.float32:
    """Mean NDVI over valid pixels; ``NaN`` when no valid pixels exist."""
    data = src.read(indexes=ndvi_band, window=win).astype(np.float32, copy=False)
    mask_band = src.read_masks(indexes=ndvi_band, window=win) > 0
    valid = mask_band & np.isfinite(data)
    if not valid.any():
        return np.float32(np.nan)
    return np.float32(data[valid].mean())


def build_forecast_patches(
    *,
    srcs: Sequence[Any | None],
    feature_bands: Sequence[int],
    ndvi_band: int,
    patch_size: int,
    window_size: int,
    examples_dir: Path,
    row: int,
    col: int,
    min_valid_ratio: float = 0.05,
) -> list[str]:
    """Build all sliding-window forecast patches for a single spatial tile.

    For a sequence of ``T`` weeks and a lookback of ``W`` weeks, this produces
    up to ``T − W`` NPZ files (one per valid time window).

    Args:
        srcs: Rasterio dataset objects, one per week in temporal order.
              ``None`` entries represent missing weeks.
        feature_bands: 1-based band indices to use as model inputs.
        ndvi_band: 1-based band index for the NDVI (target) band.
        patch_size: Spatial height and width of each patch in pixels.
        window_size: Number of *input* weeks per sample (``W``).
        examples_dir: Directory to write ``.npz`` files into.
        row: Top-left row offset of the spatial patch.
        col: Top-left column offset of the spatial patch.
        min_valid_ratio: Minimum fraction of valid pixels averaged over the
            input window required to keep the patch.  Windows with fewer valid
            pixels than this threshold are skipped.

    Returns:
        List of relative ``examples/<name>.npz`` paths that were written.
    """
    num_weeks = len(srcs)
    window = int(window_size)
    ps = int(patch_size)
    win = ((row, row + ps), (col, col + ps))
    n_feat = len(feature_bands)

    # Pre-read all weeks once.
    feats: list[np.ndarray | None] = []  # (C, H, W) or None
    masks: list[np.ndarray | None] = []  # (1, H, W) float32 or None
    ndvi_targets: list[np.float32] = []  # scalar NDVI mean per week

    for s in srcs:
        if s is None:
            feats.append(None)
            masks.append(None)
            ndvi_targets.append(np.float32(np.nan))
        else:
            valid, feat = _build_mask_and_features(s, feature_bands, win)  # (1,H,W), (C,H,W)
            feat_filled = np.where(valid > 0, feat, np.float32(0.0))
            feats.append(feat_filled)
            masks.append(valid)
            ndvi_targets.append(_ndvi_nanmean(s, ndvi_band, win))

    saved: list[str] = []
    for t_start in range(num_weeks - window):
        t_target = t_start + window

        # Build input window X and mask M.
        x_list: list[np.ndarray] = []
        m_list: list[np.ndarray] = []
        for t in range(t_start, t_start + window):
            if feats[t] is None:
                x_list.append(np.zeros((n_feat, ps, ps), dtype=np.float32))
                m_list.append(np.zeros((1, ps, ps), dtype=np.float32))
            else:
                x_list.append(feats[t])  # type: ignore[arg-type]
                m_list.append(masks[t])  # type: ignore[arg-type]

        X_feat = np.stack(x_list, axis=0)  # (W, C, H_p, W_p)
        M = np.stack(m_list, axis=0)       # (W, 1, H_p, W_p)
        X = np.concatenate([X_feat, M], axis=1)  # (W, C+1, H_p, W_p)

        mean_valid = float(M.mean())
        if mean_valid < float(min_valid_ratio):
            continue

        y = ndvi_targets[t_target]

        npz_name = f"patch_r{row:05d}_c{col:05d}_t{t_start:03d}.npz"
        npz_rel = f"examples/{npz_name}"
        np.savez_compressed(examples_dir / npz_name, X=X, y=y, M=M)
        saved.append(npz_rel)

    return saved


# ---------------------------------------------------------------------------
# Worker pool support
# ---------------------------------------------------------------------------

def _cleanup_forecast_worker() -> None:
    global _WORKER_SRCS
    if _WORKER_SRCS is not None:
        _close_srcs(_WORKER_SRCS)
        _WORKER_SRCS = None


def _init_forecast_worker(
    src_paths: Sequence[str | None],
    feature_bands: Sequence[int],
    ndvi_band: int,
    patch_size: int,
    window_size: int,
    examples_dir: str,
    min_valid_ratio: float,
    gdal_cache_mb: int,
) -> None:
    global _WORKER_SRCS, _WORKER_FEATURE_BANDS, _WORKER_NDVI_BAND
    global _WORKER_PATCH_SIZE, _WORKER_WINDOW_SIZE, _WORKER_EXAMPLES_DIR
    global _WORKER_MIN_VALID_RATIO

    rasterio.Env(GDAL_CACHEMAX=int(gdal_cache_mb)).__enter__()
    _WORKER_SRCS = [rasterio.open(p) if p is not None else None for p in src_paths]
    _WORKER_FEATURE_BANDS = [int(b) for b in feature_bands]
    _WORKER_NDVI_BAND = int(ndvi_band)
    _WORKER_PATCH_SIZE = int(patch_size)
    _WORKER_WINDOW_SIZE = int(window_size)
    _WORKER_EXAMPLES_DIR = Path(examples_dir)
    _WORKER_MIN_VALID_RATIO = float(min_valid_ratio)
    atexit.register(_cleanup_forecast_worker)


def _forecast_worker(coord: tuple[int, int]) -> list[str]:
    if _WORKER_SRCS is None or _WORKER_FEATURE_BANDS is None or _WORKER_EXAMPLES_DIR is None:
        raise RuntimeError("Forecast worker was not initialized correctly")
    row, col = int(coord[0]), int(coord[1])
    return build_forecast_patches(
        srcs=_WORKER_SRCS,
        feature_bands=_WORKER_FEATURE_BANDS,
        ndvi_band=_WORKER_NDVI_BAND,
        patch_size=_WORKER_PATCH_SIZE,
        window_size=_WORKER_WINDOW_SIZE,
        examples_dir=_WORKER_EXAMPLES_DIR,
        row=row,
        col=col,
        min_valid_ratio=_WORKER_MIN_VALID_RATIO,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_ndvi_forecast_build(
    *,
    input_dir: Path,
    output_dir: Path,
    patch_size: int,
    step_size: int,
    window_size: int,
    min_valid_ratio: float = 0.05,
    workers: int = 0,
    gdal_cache_mb: int = 64,
    max_patches: int | None = None,
    seed: int = 42,
    skip_existing: bool = False,
) -> None:
    """Build an NDVI-forecasting NPZ dataset from weekly GeoTIFFs.

    For each spatial patch location and each valid sliding window of
    ``window_size`` consecutive weeks, one NPZ file is created.

    Args:
        input_dir: Directory of weekly GeoTIFF files.
        output_dir: Root output directory; will be created if needed.
        patch_size: Spatial size of each patch (pixels, square).
        step_size: Stride between patch origins (pixels).
        window_size: Number of input weeks per sample.
        min_valid_ratio: Minimum mean valid-pixel fraction over the input
            window for a sample to be kept.
        workers: Number of parallel processes (0 = all CPUs).
        gdal_cache_mb: GDAL cache per process in MiB.
        max_patches: Randomly sub-sample spatial locations to at most this
            many before sliding-window expansion.
        seed: RNG seed for spatial sub-sampling.
        skip_existing: If True and output ``index.csv`` already exists,
            return immediately.
    """
    # Import locally to keep the module importable without dataset_service.
    from modules.services.dataset_service import _find_geotiffs, _resolve_workers

    index_csv = output_dir / "index.csv"
    examples_dir = output_dir / "examples"

    if skip_existing and index_csv.exists():
        print(f"Skipping: {index_csv} already exists")
        return

    if patch_size <= 0:
        raise ValueError("patch_size must be > 0")
    if step_size <= 0:
        raise ValueError("step_size must be > 0")
    if window_size < 2:
        raise ValueError("window_size must be >= 2 (need at least 1 input + 1 target week)")

    resolved_workers = _resolve_workers(int(workers))
    os.environ["GDAL_CACHEMAX"] = str(gdal_cache_mb)

    tifs = _find_geotiffs(input_dir)
    if not tifs:
        raise RuntimeError(f"No matching GeoTIFFs found in {input_dir}")

    # Build sorted list of source paths (None = missing week).
    padded_paths: list[Path | None] = [p for p, *_ in tifs]
    num_weeks = len(padded_paths)
    if num_weeks <= window_size:
        raise RuntimeError(
            f"Not enough weeks ({num_weeks}) for window_size={window_size}: need > {window_size}"
        )

    print(f"NDVI forecast build: {num_weeks} weeks, window={window_size}, producing up to {num_weeks - window_size} targets/spatial-patch")

    srcs: list[Any | None] = []
    try:
        for p in padded_paths:
            srcs.append(rasterio.open(p) if p is not None else None)
        first = next((s for s in srcs if s is not None), None)
        if first is None:
            raise RuntimeError("All weeks are missing; nothing to build")

        h, w = first.height, first.width
        band_count = first.count
        for s in srcs:
            if s is None:
                continue
            if s.height != h or s.width != w or s.count != band_count:
                raise RuntimeError("GeoTIFFs must have the same height/width/band-count")

        if band_count < 2:
            raise RuntimeError(f"Expected ≥2 bands (features + NDVI target), got {band_count}")

        # All bands except the last are treated as input features; band 1 is NDVI (target).
        feature_bands = list(range(1, band_count))  # drop the risk (last) band entirely
        ndvi_band = 1  # NDVI is always band 1 in this dataset

        step = int(step_size)
        rows = list(range(0, h - patch_size + 1, step))
        cols = list(range(0, w - patch_size + 1, step))
        if not rows or not cols:
            raise RuntimeError("Patch grid is empty: check patch-size vs raster dimensions")

        coords = [(r, c) for r in rows for c in cols]
        if max_patches is not None:
            if max_patches <= 0:
                raise ValueError("max_patches must be > 0")
            if max_patches < len(coords):
                rng = np.random.default_rng(int(seed))
                idx = rng.choice(len(coords), size=int(max_patches), replace=False)
                coords = [coords[int(i)] for i in idx]

        print(f"Spatial patch locations: {len(coords)}")
        print(f"Workers: {resolved_workers}")

        output_dir.mkdir(parents=True, exist_ok=True)
        examples_dir.mkdir(parents=True, exist_ok=True)

        all_npz_rels: list[str] = []

        if resolved_workers == 1:
            for row, col in tqdm(coords, desc="Building NDVI forecast patches", unit="patch"):
                saved = build_forecast_patches(
                    srcs=srcs,
                    feature_bands=feature_bands,
                    ndvi_band=ndvi_band,
                    patch_size=patch_size,
                    window_size=window_size,
                    examples_dir=examples_dir,
                    row=row,
                    col=col,
                    min_valid_ratio=min_valid_ratio,
                )
                all_npz_rels.extend(saved)
        else:
            src_paths = [str(p) if p is not None else None for p in padded_paths]
            chunk_size = max(1, len(coords) // max(1, resolved_workers * 8))
            with mp.Pool(
                processes=resolved_workers,
                initializer=_init_forecast_worker,
                initargs=(
                    src_paths,
                    feature_bands,
                    ndvi_band,
                    int(patch_size),
                    int(window_size),
                    str(examples_dir),
                    float(min_valid_ratio),
                    int(gdal_cache_mb),
                ),
            ) as pool:
                for saved in tqdm(
                    pool.imap_unordered(_forecast_worker, coords, chunksize=chunk_size),
                    total=len(coords),
                    desc="Building NDVI forecast patches",
                    unit="patch",
                ):
                    all_npz_rels.extend(saved)

        all_npz_rels.sort()
        with index_csv.open("w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=["npz_path"])
            wtr.writeheader()
            wtr.writerows({"npz_path": r} for r in all_npz_rels)

        print(f"Wrote {index_csv} with {len(all_npz_rels)} examples")
    finally:
        _close_srcs(srcs)
