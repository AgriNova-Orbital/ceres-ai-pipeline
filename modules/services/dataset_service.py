from __future__ import annotations

import atexit
import csv
import multiprocessing as mp
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from tqdm import tqdm

try:
    import rasterio
except ImportError as e:
    raise ImportError(
        "rasterio is required for this module. Install it (e.g. `uv pip install rasterio`)."
    ) from e

WEEK_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
DATA_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
WEEK_IN_SUFFIX = re.compile(r"\bW(\d{2})\b", re.IGNORECASE)
NUM_IN_SUFFIX = re.compile(r"\b(\d{1,3})\b")
DATE8_IN_TEXT = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
DATE_SEP_IN_TEXT = re.compile(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)")

_WORKER_SRCS: list[Any | None] | None = None
_WORKER_FEATURE_BANDS: list[int] | None = None
_WORKER_RISK_BAND: int | None = None
_WORKER_PATCH_SIZE: int | None = None
_WORKER_EXAMPLES_DIR: Path | None = None
_WORKER_ENV: Any | None = None
_WORKER_MIN_VALID_RATIO: float = 0.05

def fill_missing_weeks(
    items: Sequence[tuple[int, object]], *, expected_len: int
) -> tuple[list[object | None], np.ndarray]:
    if expected_len <= 0:
        raise ValueError("expected_len must be > 0")

    by_idx: dict[int, object] = {int(k): v for k, v in items}

    values: list[object | None] = []
    mask = np.zeros((expected_len,), dtype=bool)
    for i, week_idx in enumerate(range(-expected_len, 0)):
        if week_idx in by_idx:
            values.append(by_idx[week_idx])
            mask[i] = True
        else:
            values.append(None)
    return values, mask

def fill_missing_dates(
    items: Sequence[tuple[date, object]], *, expected_len: int, step_days: int
) -> tuple[list[object | None], list[date], np.ndarray]:
    if expected_len <= 0:
        raise ValueError("expected_len must be > 0")
    if step_days <= 0:
        raise ValueError("step_days must be > 0")

    by_date: dict[date, object] = {}
    for d, v in items:
        by_date[d] = v

    start = min(by_date.keys())
    dates = [start + timedelta(days=i * step_days) for i in range(expected_len)]
    values: list[object | None] = []
    mask = np.zeros((expected_len,), dtype=bool)
    for i, d in enumerate(dates):
        if d in by_date:
            values.append(by_date[d])
            mask[i] = True
        else:
            values.append(None)
    return values, dates, mask

def _to_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None

def _extract_date_from_text(text: str) -> date | None:
    m = DATE_SEP_IN_TEXT.search(text)
    if m:
        d = _to_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d is not None:
            return d
    m2 = DATE8_IN_TEXT.search(text)
    if m2:
        d = _to_date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        if d is not None:
            return d
    return None

def _parse_temporal_filename(
    filename: str,
) -> tuple[date | None, int | None, int | None] | None:
    m_plain8 = re.match(r"fr_wheat_feat_(\d{8})\.tif(?:f)?$", filename, re.IGNORECASE)
    if m_plain8:
        ymd = m_plain8.group(1)
        d = _to_date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))
        if d is not None:
            return d, None, int(ymd[0:4])

    m_plain_sep = re.match(
        r"fr_wheat_feat_(\d{4})[-_](\d{2})[-_](\d{2})\.tif(?:f)?$",
        filename,
        re.IGNORECASE,
    )
    if m_plain_sep:
        y = int(m_plain_sep.group(1))
        d = _to_date(y, int(m_plain_sep.group(2)), int(m_plain_sep.group(3)))
        if d is not None:
            return d, None, y

    m_week = WEEK_PATTERN.match(filename)
    if m_week:
        y = int(m_week.group(1))
        wk = int(m_week.group(2))
        try:
            d = date.fromisocalendar(y, wk, 1)
        except ValueError:
            d = None
        return d, wk, y

    m_data = DATA_PATTERN.match(filename)
    if not m_data:
        return None

    y = int(m_data.group(1))
    suffix = m_data.group(2)

    d2 = _extract_date_from_text(suffix)
    if d2 is not None:
        return d2, None, y

    w = WEEK_IN_SUFFIX.search(suffix)
    if w:
        wk = int(w.group(1))
        try:
            d3 = date.fromisocalendar(y, wk, 1)
        except ValueError:
            d3 = None
        return d3, wk, y

    n = NUM_IN_SUFFIX.search(suffix)
    if n:
        return None, int(n.group(1)), y

    return None, 0, y

def _find_geotiffs(
    input_dir: Path,
) -> list[tuple[Path, date | None, int | None, int | None]]:
    tifs: list[tuple[Path, date | None, int | None, int | None]] = []
    for p in input_dir.glob("*.tif*"):
        parsed = _parse_temporal_filename(p.name)
        if parsed is None:
            continue
        d, idx, year = parsed
        tifs.append((p, d, idx, year))

    tifs.sort(
        key=lambda x: (
            x[1] is None,
            x[1] if x[1] is not None else date.max,
            x[2] if x[2] is not None else 10**9,
            x[0].name,
        )
    )
    return tifs

def _resolve_workers(workers: int) -> int:
    if workers < 0:
        raise ValueError("workers must be >= 0")
    if workers == 0:
        return max(1, int(os.cpu_count() or 1))
    return workers

def _close_srcs(srcs: Sequence[Any | None]) -> None:
    for s in srcs:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass

def _build_patch_and_save(
    *,
    row: int,
    col: int,
    patch_size: int,
    srcs: Sequence[Any | None],
    feature_bands: Sequence[int],
    risk_band: int,
    examples_dir: Path,
    min_valid_ratio: float = 0.05,
) -> str | None:
    x_seq: list[np.ndarray] = []
    m_seq: list[np.ndarray] = []
    y_seq: list[np.float32] = []

    ps = int(patch_size)
    win = ((row, row + ps), (col, col + ps))
    for s in srcs:
        if s is None:
            x_seq.append(np.zeros((len(feature_bands), ps, ps), dtype=np.float32))
            m_seq.append(np.zeros((1, ps, ps), dtype=np.float32))
            y_seq.append(np.float32(np.nan))
            continue

        feat = s.read(indexes=feature_bands, window=win).astype(np.float32, copy=False)

        # Build a per-pixel valid mask combining the raster nodata mask and
        # finite-value check. read_masks() returns 255 for valid pixels and 0
        # for nodata/masked pixels; np.isfinite guards against NaN/inf values
        # that were stored without an explicit nodata marker.
        band_masks = s.read_masks(indexes=feature_bands, window=win)  # (C, H, W) uint8
        valid_from_mask = (band_masks > 0).all(axis=0, keepdims=True)  # (1, H, W)
        valid_from_finite = np.isfinite(feat).all(axis=0, keepdims=True)  # (1, H, W)
        valid = (valid_from_mask & valid_from_finite).astype(np.float32)  # (1, H, W)

        # Impute invalid pixels to 0 so X is always finite; the mask channel
        # tells the model which positions are real observations.
        feat = np.where(valid > 0, feat, np.float32(0.0))

        x_seq.append(feat)
        m_seq.append(valid)

        risk = s.read(indexes=risk_band, window=win).astype(np.float32, copy=False)
        risk_mask_band = s.read_masks(indexes=risk_band, window=win) > 0  # (H, W)
        risk_finite = np.isfinite(risk) & risk_mask_band
        y_val = np.float32(risk[risk_finite].mean()) if risk_finite.any() else np.float32(np.nan)
        y_seq.append(y_val)

    X_feat = np.stack(x_seq, axis=0)       # (T, C, H, W)
    M = np.stack(m_seq, axis=0)            # (T, 1, H, W)
    X = np.concatenate([X_feat, M], axis=1)  # (T, C+1, H, W) – mask appended as last channel
    y = np.asarray(y_seq, dtype=np.float32)

    mean_valid_ratio = float(M.mean())
    if mean_valid_ratio < float(min_valid_ratio):
        return None

    npz_name = f"patch_r{row:05d}_c{col:05d}.npz"
    npz_rel = f"examples/{npz_name}"
    np.savez_compressed(examples_dir / npz_name, X=X, y=y, M=M)
    return npz_rel

def _cleanup_worker_srcs() -> None:
    global _WORKER_ENV
    global _WORKER_SRCS
    if _WORKER_SRCS is not None:
        _close_srcs(_WORKER_SRCS)
        _WORKER_SRCS = None
    if _WORKER_ENV is not None:
        try:
            _WORKER_ENV.__exit__(None, None, None)
        except Exception:
            pass
        _WORKER_ENV = None

def _init_patch_worker(
    src_paths: Sequence[str | None],
    feature_bands: Sequence[int],
    risk_band: int,
    patch_size: int,
    examples_dir: str,
    gdal_cache_mb: int,
    min_valid_ratio: float,
) -> None:
    global _WORKER_ENV
    global _WORKER_SRCS
    global _WORKER_FEATURE_BANDS
    global _WORKER_RISK_BAND
    global _WORKER_PATCH_SIZE
    global _WORKER_EXAMPLES_DIR
    global _WORKER_MIN_VALID_RATIO

    _WORKER_ENV = rasterio.Env(GDAL_CACHEMAX=int(gdal_cache_mb))
    _WORKER_ENV.__enter__()
    _WORKER_SRCS = [rasterio.open(p) if p is not None else None for p in src_paths]
    _WORKER_FEATURE_BANDS = [int(i) for i in feature_bands]
    _WORKER_RISK_BAND = int(risk_band)
    _WORKER_PATCH_SIZE = int(patch_size)
    _WORKER_EXAMPLES_DIR = Path(examples_dir)
    _WORKER_MIN_VALID_RATIO = float(min_valid_ratio)

    atexit.register(_cleanup_worker_srcs)

def _build_patch_worker(coord: tuple[int, int]) -> str | None:
    if (
        _WORKER_SRCS is None
        or _WORKER_FEATURE_BANDS is None
        or _WORKER_RISK_BAND is None
        or _WORKER_PATCH_SIZE is None
        or _WORKER_EXAMPLES_DIR is None
    ):
        raise RuntimeError("Patch worker was not initialized correctly")

    row, col = int(coord[0]), int(coord[1])
    return _build_patch_and_save(
        row=row,
        col=col,
        patch_size=_WORKER_PATCH_SIZE,
        srcs=_WORKER_SRCS,
        feature_bands=_WORKER_FEATURE_BANDS,
        risk_band=_WORKER_RISK_BAND,
        examples_dir=_WORKER_EXAMPLES_DIR,
        min_valid_ratio=_WORKER_MIN_VALID_RATIO,
    )

def run_build(
    *,
    input_dir: Path,
    output_dir: Path,
    patch_size: int,
    step_size: int,
    expected_weeks: int | None = None,
    start_date: str | None = None,
    date_step_days: int = 7,
    workers: int = 0,
    gdal_cache_mb: int = 64,
    weeks_limit: int | None = None,
    max_patches: int | None = None,
    seed: int = 42,
    skip_existing: bool = False,
    min_valid_ratio: float = 0.05,
) -> None:
    index_csv = output_dir / "index.csv"
    examples_dir = output_dir / "examples"

    if skip_existing and index_csv.exists():
        print(f"Skipping: {index_csv} already exists")
        return

    if patch_size <= 0:
        raise ValueError("--patch-size must be > 0")
    
    workers = _resolve_workers(int(workers))

    if int(gdal_cache_mb) <= 0:
        raise ValueError("--gdal-cache-mb must be > 0")
    os.environ["GDAL_CACHEMAX"] = str(gdal_cache_mb)

    tifs = _find_geotiffs(input_dir)
    if not tifs:
        raise RuntimeError(f"No matching GeoTIFFs found in {input_dir}")

    if int(date_step_days) <= 0:
        raise ValueError("--date-step-days must be > 0")

    start_date_arg: date | None = None
    if start_date:
        try:
            start_date_arg = date.fromisoformat(str(start_date))
        except ValueError as e:
            raise ValueError("--start-date must be YYYY-MM-DD") from e

    dated_items: list[tuple[date, Path]] = []
    indexed_items: list[tuple[int, Path]] = []
    year_values: list[int] = []
    for p, d, idx, year in tifs:
        if d is not None:
            dated_items.append((d, p))
        if idx is not None:
            indexed_items.append((int(idx), p))
        if year is not None:
            year_values.append(int(year))

    padded_paths: list[Path | None]
    timeline_dates: list[date] = []
    timeline_mode = "index"
    step_days = int(date_step_days)

    if dated_items:
        timeline_mode = "date"
        min_d = min(d for d, _ in dated_items)
        max_d = max(d for d, _ in dated_items)
        inferred_expected = ((max_d - min_d).days // step_days) + 1
        expected_len = (
            int(expected_weeks)
            if expected_weeks is not None
            else int(inferred_expected)
        )
        if expected_len <= 0:
            raise ValueError("expected weeks must be > 0")

        padded_vals, timeline_dates, _mask = fill_missing_dates(
            dated_items, expected_len=expected_len, step_days=step_days
        )
        padded_paths = [p if isinstance(p, Path) else None for p in padded_vals]
    elif indexed_items:
        timeline_mode = "derived-date"
        anchor = start_date_arg
        if anchor is None and year_values:
            anchor = date(min(year_values), 1, 1)

        if anchor is not None:
            derived_items = [
                (anchor + timedelta(days=(int(idx) - 1) * step_days), p)
                for idx, p in indexed_items
            ]
            max_idx = max(int(idx) for idx, _ in indexed_items)
            inferred_expected = int(max_idx)
            expected_len = (
                int(expected_weeks)
                if expected_weeks is not None
                else int(inferred_expected)
            )
            if expected_len <= 0:
                raise ValueError("expected weeks must be > 0")

            padded_vals, timeline_dates, _mask = fill_missing_dates(
                derived_items, expected_len=expected_len, step_days=step_days
            )
            padded_paths = [p if isinstance(p, Path) else None for p in padded_vals]
        else:
            min_week = min(k for k, _ in indexed_items)
            max_week = max(k for k, _ in indexed_items)
            inferred_expected = abs(int(min_week)) if min_week < 0 else int(max_week)
            expected_len = (
                int(expected_weeks)
                if expected_weeks is not None
                else int(inferred_expected)
            )
            if expected_len <= 0:
                raise ValueError("expected weeks must be > 0")

            if min_week < 0:
                padded_vals, _mask = fill_missing_weeks(
                    indexed_items, expected_len=expected_len
                )
                padded_paths = [p if isinstance(p, Path) else None for p in padded_vals]
            else:
                by_week = {int(k): v for k, v in indexed_items}
                padded_paths = [by_week.get(i) for i in range(1, expected_len + 1)]
    else:
        raise RuntimeError(f"No parseable temporal keys found in {input_dir}")

    if weeks_limit is not None:
        if weeks_limit <= 0:
            raise ValueError("--weeks-limit must be > 0")
        padded_paths = padded_paths[: int(weeks_limit)]
        timeline_dates = timeline_dates[: int(weeks_limit)]

    expected_len = len(padded_paths)
    present = sum(1 for p in padded_paths if p is not None)
    missing = expected_len - present
    print(
        f"Timeline: mode={timeline_mode} expected={expected_len} present={present} missing={missing}"
    )
    if timeline_dates:
        missing_dates = [
            d.isoformat() for d, p in zip(timeline_dates, padded_paths) if p is None
        ]
        if missing_dates:
            shown = ", ".join(missing_dates[:8])
            if len(missing_dates) > 8:
                shown += f", ... (+{len(missing_dates) - 8} more)"
            print(f"Missing dates: {shown}")

    srcs: list[Any | None] = []
    for p in padded_paths:
        if p is None:
            srcs.append(None)
        else:
            srcs.append(rasterio.open(p))
    try:
        first = next((s for s in srcs if s is not None), None)
        if first is None:
            raise RuntimeError("All weeks are missing; nothing to build")
        h = first.height
        w = first.width
        band_count = first.count
        for s in srcs:
            if s is None:
                continue
            if s.height != h or s.width != w or s.count != band_count:
                raise RuntimeError("GeoTIFFs must have same width/height/band-count")

        if band_count < 2:
            raise RuntimeError(f"Expected >=2 bands, got {band_count}")
        feature_bands = list(range(1, band_count))
        risk_band = band_count

        step = int(step_size)
        rows = list(range(0, h - patch_size + 1, step))
        cols = list(range(0, w - patch_size + 1, step))
        if not rows or not cols:
            raise RuntimeError("Patch/grid is empty: check patch-size vs raster size")

        coords = [(r, c) for r in rows for c in cols]
        if max_patches is not None:
            if max_patches <= 0:
                raise ValueError("--max-patches must be > 0")
            if max_patches < len(coords):
                rng = np.random.default_rng(int(seed))
                idx = rng.choice(len(coords), size=int(max_patches), replace=False)
                coords = [coords[int(i)] for i in idx]
        print(f"Patch locations: {len(coords)}")
        print(f"Patch workers: {workers}")
        print(f"GDAL cache per process: {gdal_cache_mb} MiB")

        output_dir.mkdir(parents=True, exist_ok=True)
        examples_dir.mkdir(parents=True, exist_ok=True)

        index_rows: list[dict[str, str]] = []

        if workers == 1:
            for row, col in tqdm(
                coords, desc="Building patches", unit="patch", mininterval=1.0
            ):
                npz_rel = _build_patch_and_save(
                    row=int(row),
                    col=int(col),
                    patch_size=int(patch_size),
                    srcs=srcs,
                    feature_bands=feature_bands,
                    risk_band=risk_band,
                    examples_dir=examples_dir,
                    min_valid_ratio=float(min_valid_ratio),
                )
                if npz_rel is not None:
                    index_rows.append({"npz_path": npz_rel})
        else:
            src_paths = [str(p) if p is not None else None for p in padded_paths]
            chunk_size = max(1, len(coords) // max(1, workers * 8))
            with mp.Pool(
                processes=workers,
                initializer=_init_patch_worker,
                initargs=(
                    src_paths,
                    feature_bands,
                    risk_band,
                    int(patch_size),
                    str(examples_dir),
                    int(gdal_cache_mb),
                    float(min_valid_ratio),
                ),
            ) as pool:
                iterator = pool.imap_unordered(
                    _build_patch_worker, coords, chunksize=chunk_size
                )
                for npz_rel in tqdm(
                    iterator,
                    total=len(coords),
                    desc="Building patches",
                    unit="patch",
                    mininterval=1.0,
                ):
                    if npz_rel is not None:
                        index_rows.append({"npz_path": npz_rel})

        index_rows.sort(key=lambda r: r["npz_path"])

        with index_csv.open("w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=["npz_path"])
            wtr.writeheader()
            wtr.writerows(index_rows)

        print(f"Wrote {index_csv} with {len(index_rows)} examples")
    finally:
        _close_srcs(srcs)
