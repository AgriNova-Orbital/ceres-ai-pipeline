# %% [markdown]
# # Ceres Colab Patch Factory Smoke
#
# Notebook-style Python for Google Colab.
#
# Purpose:
# - Read Earth Engine split GeoTIFFs from Google Drive.
# - Generate deterministic grid patches for 64x64 and 128x128.
# - Write sharded NPZ datasets back to Google Drive.
# - Keep raw GeoTIFFs split; do not merge before patching.

# %%
from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

rasterio: Any | None = None
Window: Any | None = None
tqdm: Any | None = None


def ensure_imports() -> None:
    """Install Colab dependencies if they are missing."""
    global Window, rasterio, tqdm

    missing: list[str] = []
    try:
        import rasterio as rasterio_module  # noqa: F401
    except ModuleNotFoundError:
        missing.append("rasterio")

    try:
        import tqdm as tqdm_module  # noqa: F401
    except ModuleNotFoundError:
        missing.append("tqdm")

    if missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", *missing]
        )

    import rasterio as rasterio_module
    from rasterio.windows import Window as window_cls
    from tqdm.auto import tqdm as tqdm_fn

    rasterio = rasterio_module
    Window = window_cls
    tqdm = tqdm_fn


def mount_drive() -> None:
    try:
        from google.colab import drive  # type: ignore

        drive.mount("/content/drive")
    except ModuleNotFoundError:
        print("Not running in Colab; skipping drive.mount().")


# %% [markdown]
# ## Mount Google Drive

# %% [markdown]
# ## Config
#
# If your Earth Engine export folder is not directly under `MyDrive`, adjust `RAW_DIR`.

# %%
DRIVE_ROOT = Path("/content/drive/MyDrive")

# Common Earth Engine Drive export location from the current workflow.
RAW_DIR = DRIVE_ROOT / "wheat_data_v2.0-beta"

# Smoke output. Full run should use: Ceres/staged/2025w36_w52_grid_v1
OUTPUT_ROOT = DRIVE_ROOT / "Ceres" / "staged" / "2025w36_w38_grid_v1_smoke"

WEEK_START = "2025W36"
WEEK_END = "2025W38"

PATCH_SIZES = (64, 128)
STRIPE_HEIGHT = 256
VALID_RATIO_MIN = 0.80
NODATA = -32768.0
SKIP_EXISTING = True

FEATURE_BANDS = (
    "ndvi",
    "ndmi",
    "nbr",
    "s1_vv",
    "s1_vh",
    "s1_vh_vv",
    "rain_mm",
    "temp_c_mean",
    "temp_c_max",
    "lst_c",
)
LABEL_BAND = "risk"
FINAL_BANDS = FEATURE_BANDS + (LABEL_BAND,)

# %% [markdown]
# ## Helpers

# %%
RAW_NAME_RE = re.compile(
    r"^fr_wheat_feat_(?P<year>\d{4})W(?P<week>\d{2})"
    r"(?:-(?P<row>\d+)-(?P<col>\d+))?\.tif(?:f)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RawTile:
    path: Path
    week_key: str
    year: int
    week: int
    row_offset: int
    col_offset: int
    tile_key: str
    tile_id: int
    split: str
    width: int
    height: int
    count: int
    crs: str
    nodata: float | None
    dtypes: tuple[str, ...]
    descriptions: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_week_key(week_key: str) -> tuple[int, int]:
    m = re.match(r"^(\d{4})W(\d{2})$", week_key, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid week key: {week_key}")
    return int(m.group(1)), int(m.group(2))


def in_week_range(week_key: str, start: str, end: str) -> bool:
    wk = parse_week_key(week_key)
    return parse_week_key(start) <= wk <= parse_week_key(end)


def parse_raw_name(path: Path) -> tuple[str, int, int, int, int, str] | None:
    m = RAW_NAME_RE.match(path.name)
    if not m:
        return None

    year = int(m.group("year"))
    week = int(m.group("week"))
    row_offset = int(m.group("row") or 0)
    col_offset = int(m.group("col") or 0)
    week_key = f"{year}W{week:02d}"
    tile_key = f"r{row_offset:010d}_c{col_offset:010d}"
    return week_key, year, week, row_offset, col_offset, tile_key


def normalize_descriptions(descriptions: Iterable[str | None]) -> tuple[str, ...]:
    return tuple((d or "").strip() for d in descriptions)


def validate_dimensions_for_patching(
    *,
    filename: str,
    width: int,
    height: int,
    patch_sizes: Iterable[int],
    stripe_height: int,
) -> None:
    for patch_size in patch_sizes:
        if width < patch_size or height < patch_size:
            raise RuntimeError(
                f"{filename}: dimensions {width}x{height} must be "
                f">= patch_size={patch_size}"
            )
    if stripe_height <= 0:
        raise RuntimeError(f"STRIPE_HEIGHT must be > 0, got {stripe_height}")


def validate_raster(path: Path) -> dict[str, object]:
    with rasterio.open(path) as ds:
        descriptions = normalize_descriptions(ds.descriptions)

        if ds.count != len(FINAL_BANDS):
            raise RuntimeError(
                f"{path.name}: expected {len(FINAL_BANDS)} bands, got {ds.count}"
            )
        if descriptions != FINAL_BANDS:
            raise RuntimeError(
                f"{path.name}: unexpected band descriptions {descriptions}; "
                f"expected {FINAL_BANDS}"
            )
        if any(str(dtype).lower() != "float32" for dtype in ds.dtypes):
            raise RuntimeError(f"{path.name}: all bands must be float32, got {ds.dtypes}")
        if ds.nodata is None or not math.isclose(float(ds.nodata), NODATA):
            raise RuntimeError(f"{path.name}: expected nodata={NODATA}, got {ds.nodata}")
        if ds.crs is None:
            raise RuntimeError(f"{path.name}: CRS is required")
        validate_dimensions_for_patching(
            filename=path.name,
            width=int(ds.width),
            height=int(ds.height),
            patch_sizes=PATCH_SIZES,
            stripe_height=STRIPE_HEIGHT,
        )

        return {
            "width": int(ds.width),
            "height": int(ds.height),
            "count": int(ds.count),
            "crs": str(ds.crs),
            "nodata": float(ds.nodata),
            "dtypes": tuple(str(d) for d in ds.dtypes),
            "descriptions": descriptions,
        }


def build_tile_splits(tile_keys: list[str]) -> dict[str, str]:
    """Assign stable tile-based splits from sorted tile keys."""
    n = len(tile_keys)
    if n == 0:
        raise RuntimeError("No tiles found")
    if n == 1:
        return {tile_keys[0]: "train"}
    if n == 2:
        return {tile_keys[0]: "train", tile_keys[1]: "val"}
    if n == 3:
        return {tile_keys[0]: "train", tile_keys[1]: "val", tile_keys[2]: "test"}

    train_count = max(1, int(n * 0.70))
    val_count = max(1, int(n * 0.15))
    if train_count + val_count >= n:
        train_count = max(1, n - 2)
        val_count = 1

    out: dict[str, str] = {}
    for i, key in enumerate(tile_keys):
        if i < train_count:
            out[key] = "train"
        elif i < train_count + val_count:
            out[key] = "val"
        else:
            out[key] = "test"
    return out


def scan_raw_tiles(raw_dir: Path) -> list[RawTile]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"RAW_DIR does not exist: {raw_dir}")

    candidates = sorted(
        p for p in raw_dir.rglob("*.tif*") if p.is_file() and parse_raw_name(p) is not None
    )
    parsed = [(p, parse_raw_name(p)) for p in candidates]
    parsed = [item for item in parsed if item[1] is not None]
    parsed = [
        (p, info)
        for p, info in parsed
        if in_week_range(info[0], WEEK_START, WEEK_END)
    ]

    if not parsed:
        raise RuntimeError(
            f"No raw GeoTIFFs found in {raw_dir} for {WEEK_START}..{WEEK_END}"
        )

    tile_keys = sorted({info[5] for _p, info in parsed})
    tile_id_by_key = {key: i for i, key in enumerate(tile_keys)}
    split_by_key = build_tile_splits(tile_keys)

    tiles: list[RawTile] = []
    for path, info in tqdm(parsed, desc="Validating raw GeoTIFFs", unit="file"):
        week_key, year, week, row_offset, col_offset, tile_key = info
        meta = validate_raster(path)
        tiles.append(
            RawTile(
                path=path,
                week_key=week_key,
                year=year,
                week=week,
                row_offset=row_offset,
                col_offset=col_offset,
                tile_key=tile_key,
                tile_id=tile_id_by_key[tile_key],
                split=split_by_key[tile_key],
                width=int(meta["width"]),
                height=int(meta["height"]),
                count=int(meta["count"]),
                crs=str(meta["crs"]),
                nodata=float(meta["nodata"]),
                dtypes=tuple(meta["dtypes"]),
                descriptions=tuple(meta["descriptions"]),
            )
        )

    tiles.sort(key=lambda t: (parse_week_key(t.week_key), t.row_offset, t.col_offset, t.path.name))
    return tiles


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_inventory(output_root: Path, tiles: list[RawTile]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "raw_inventory.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "path",
                "filename",
                "week_key",
                "tile_key",
                "tile_id",
                "split",
                "row_offset",
                "col_offset",
                "width",
                "height",
                "count",
                "crs",
                "nodata",
            ],
        )
        writer.writeheader()
        for tile in tiles:
            writer.writerow(
                {
                    "path": str(tile.path),
                    "filename": tile.path.name,
                    "week_key": tile.week_key,
                    "tile_key": tile.tile_key,
                    "tile_id": tile.tile_id,
                    "split": tile.split,
                    "row_offset": tile.row_offset,
                    "col_offset": tile.col_offset,
                    "width": tile.width,
                    "height": tile.height,
                    "count": tile.count,
                    "crs": tile.crs,
                    "nodata": tile.nodata,
                }
            )
    print("Wrote", path)


def write_split_manifest(output_root: Path, tiles: list[RawTile]) -> None:
    by_tile: dict[str, RawTile] = {}
    for tile in tiles:
        by_tile.setdefault(tile.tile_key, tile)

    manifest = {
        "schema_version": "tile-split-v1",
        "created_at": utc_now(),
        "split_strategy": "tile_based_offsets",
        "week_start": WEEK_START,
        "week_end": WEEK_END,
        "tile_split": {k: by_tile[k].split for k in sorted(by_tile)},
        "tiles": [
            {
                "tile_key": by_tile[k].tile_key,
                "tile_id": by_tile[k].tile_id,
                "split": by_tile[k].split,
                "row_offset": by_tile[k].row_offset,
                "col_offset": by_tile[k].col_offset,
            }
            for k in sorted(by_tile)
        ],
    }
    write_json(output_root / "split_manifest.json", manifest)
    print("Wrote", output_root / "split_manifest.json")


# %% [markdown]
# ## Shard Generation

# %%
def shard_name_for(tile: RawTile, row_start: int, row_end_exclusive: int, patch_size: int) -> str:
    return (
        f"{tile.week_key}_{tile.tile_key}_"
        f"y{row_start:06d}_y{row_end_exclusive - 1:06d}_p{patch_size}.npz"
    )


def valid_final_shard(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with np.load(path, allow_pickle=False) as z:
            required = {"X", "y", "valid_mask"}
            return required.issubset(set(z.files)) and int(z["y"].shape[0]) > 0
    except Exception:
        return False


def save_npz_atomic(final_path: Path, arrays: dict[str, np.ndarray]) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(".tmp.npz")
    if tmp_path.exists():
        tmp_path.unlink()
    np.savez_compressed(tmp_path, **arrays)
    tmp_path.replace(final_path)


def build_shard(tile: RawTile, patch_size: int, row_start: int, row_end_exclusive: int) -> dict[str, np.ndarray] | None:
    stripe_height = row_end_exclusive - row_start
    if stripe_height < patch_size:
        return None

    with rasterio.open(tile.path) as ds:
        stripe = ds.read(
            indexes=list(range(1, len(FINAL_BANDS) + 1)),
            window=Window(0, row_start, ds.width, stripe_height),
        ).astype(np.float32, copy=False)

    xs: list[np.ndarray] = []
    ys: list[np.float32] = []
    masks: list[np.ndarray] = []
    rows: list[int] = []
    cols: list[int] = []

    ndvi_band = stripe[0]
    risk_band = stripe[-1]

    for local_row in range(0, stripe_height - patch_size + 1, patch_size):
        for col in range(0, tile.width - patch_size + 1, patch_size):
            row = row_start + local_row
            ndvi = ndvi_band[local_row : local_row + patch_size, col : col + patch_size]
            risk = risk_band[local_row : local_row + patch_size, col : col + patch_size]
            valid_mask = (
                np.isfinite(ndvi)
                & np.isfinite(risk)
                & (ndvi != NODATA)
                & (risk != NODATA)
            )

            valid_ratio = float(valid_mask.mean())
            if valid_ratio < VALID_RATIO_MIN:
                continue

            y = np.float32(risk[valid_mask].mean())
            x = stripe[: len(FEATURE_BANDS), local_row : local_row + patch_size, col : col + patch_size]

            xs.append(np.array(x, dtype=np.float32, copy=True))
            ys.append(y)
            masks.append(np.array(valid_mask, dtype=bool, copy=True))
            rows.append(row)
            cols.append(col)

    if not xs:
        return None

    n = len(xs)
    return {
        "X": np.stack(xs, axis=0).astype(np.float32, copy=False),
        "y": np.asarray(ys, dtype=np.float32),
        "valid_mask": np.stack(masks, axis=0).astype(bool, copy=False),
        "week_key": np.asarray([tile.week_key] * n),
        "tile_key": np.asarray([tile.tile_key] * n),
        "tile_id": np.full((n,), tile.tile_id, dtype=np.int16),
        "split": np.asarray([tile.split] * n),
        "row": np.asarray(rows, dtype=np.int32),
        "col": np.asarray(cols, dtype=np.int32),
        "stripe_row_start": np.asarray(row_start, dtype=np.int32),
        "stripe_row_end": np.asarray(row_end_exclusive - 1, dtype=np.int32),
        "row_offset": np.full((n,), tile.row_offset, dtype=np.int32),
        "col_offset": np.full((n,), tile.col_offset, dtype=np.int32),
        "patch_size": np.asarray(patch_size, dtype=np.int16),
        "nodata": np.asarray(NODATA, dtype=np.float32),
    }


def generate_shards_for_patch_size(tiles: list[RawTile], patch_size: int) -> None:
    dataset_dir = OUTPUT_ROOT / f"p{patch_size}"
    shards_dir = dataset_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)

    total_jobs = sum(math.ceil(tile.height / STRIPE_HEIGHT) for tile in tiles)
    kept_shards = 0
    kept_samples = 0
    skipped_existing = 0

    with tqdm(total=total_jobs, desc=f"Generating p{patch_size} shards", unit="stripe") as bar:
        for tile in tiles:
            for row_start in range(0, tile.height, STRIPE_HEIGHT):
                row_end = min(tile.height, row_start + STRIPE_HEIGHT)
                final_path = shards_dir / shard_name_for(tile, row_start, row_end, patch_size)

                if SKIP_EXISTING and valid_final_shard(final_path):
                    with np.load(final_path, allow_pickle=False) as z:
                        kept_samples += int(z["y"].shape[0])
                    kept_shards += 1
                    skipped_existing += 1
                    bar.update(1)
                    continue

                arrays = build_shard(tile, patch_size, row_start, row_end)
                if arrays is not None:
                    save_npz_atomic(final_path, arrays)
                    kept_shards += 1
                    kept_samples += int(arrays["y"].shape[0])
                bar.update(1)

    print(
        f"p{patch_size}: wrote/kept {kept_shards} shards, "
        f"{kept_samples} samples, skipped_existing={skipped_existing}"
    )


# %% [markdown]
# ## Index and Manifest

# %%
def read_shard_summary(dataset_dir: Path, shard_path: Path) -> dict[str, object]:
    with np.load(shard_path, allow_pickle=False) as z:
        y = z["y"]
        patch_size = int(np.asarray(z["patch_size"]).item())
        rel = shard_path.relative_to(dataset_dir).as_posix()
        return {
            "shard_path": rel,
            "patch_size": patch_size,
            "num_samples": int(y.shape[0]),
            "week_key": str(z["week_key"][0]),
            "tile_key": str(z["tile_key"][0]),
            "tile_id": int(z["tile_id"][0]),
            "split": str(z["split"][0]),
            "row_start": int(np.asarray(z["stripe_row_start"]).item()),
            "row_end": int(np.asarray(z["stripe_row_end"]).item()),
            "col_offset": int(z["col_offset"][0]),
        }


def rebuild_index_and_manifest(tiles: list[RawTile], patch_size: int) -> None:
    dataset_dir = OUTPUT_ROOT / f"p{patch_size}"
    shards = sorted((dataset_dir / "shards").glob("*.npz"))
    summaries = [read_shard_summary(dataset_dir, p) for p in shards]
    summaries = [s for s in summaries if int(s["num_samples"]) > 0]
    summaries.sort(key=lambda r: (r["week_key"], r["tile_id"], r["row_start"], r["shard_path"]))

    index_path = dataset_dir / "index.csv"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "shard_path",
        "patch_size",
        "num_samples",
        "week_key",
        "tile_key",
        "tile_id",
        "split",
        "row_start",
        "row_end",
        "col_offset",
    ]
    with index_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    split_counts: dict[str, int] = {}
    week_counts: dict[str, int] = {}
    for row in summaries:
        split = str(row["split"])
        week_key = str(row["week_key"])
        num_samples = int(row["num_samples"])
        split_counts[split] = split_counts.get(split, 0) + num_samples
        week_counts[week_key] = week_counts.get(week_key, 0) + num_samples

    manifest = {
        "schema_version": "ceres-sharded-npz-v1",
        "created_at": utc_now(),
        "raw_dir": str(RAW_DIR),
        "output_dir": str(dataset_dir),
        "week_start": WEEK_START,
        "week_end": WEEK_END,
        "patch_size": patch_size,
        "stripe_height": STRIPE_HEIGHT,
        "feature_bands": list(FEATURE_BANDS),
        "label_band": LABEL_BAND,
        "final_bands": list(FINAL_BANDS),
        "nodata": NODATA,
        "valid_ratio_min": VALID_RATIO_MIN,
        "valid_mask_definition": "(ndvi != nodata) AND (risk != nodata)",
        "raw_file_count": len(tiles),
        "total_shards": len(summaries),
        "total_samples": sum(int(r["num_samples"]) for r in summaries),
        "split_counts": split_counts,
        "week_counts": week_counts,
        "index_csv": "index.csv",
    }
    write_json(dataset_dir / "manifest.json", manifest)
    print("Wrote", index_path)
    print("Wrote", dataset_dir / "manifest.json")


def smoke_load(patch_size: int) -> None:
    dataset_dir = OUTPUT_ROOT / f"p{patch_size}"
    index_path = dataset_dir / "index.csv"
    with index_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows in {index_path}")

    first = rows[0]
    shard_path = dataset_dir / first["shard_path"]
    with np.load(shard_path, allow_pickle=False) as z:
        x = z["X"]
        y = z["y"]
        mask = z["valid_mask"]
        print(f"p{patch_size} smoke shard", shard_path.name)
        print("  X", x.shape, x.dtype)
        print("  y", y.shape, y.dtype, "min/mean/max", float(y.min()), float(y.mean()), float(y.max()))
        print("  valid_mask", mask.shape, mask.dtype, "mean", float(mask.mean()))
        print("  split", str(z["split"][0]), "week", str(z["week_key"][0]))


# %% [markdown]
# ## Run Smoke Patch Factory

# %%
def run_patch_factory() -> None:
    ensure_imports()
    mount_drive()

    print("RAW_DIR", RAW_DIR)
    print("OUTPUT_ROOT", OUTPUT_ROOT)

    tiles = scan_raw_tiles(RAW_DIR)
    print(f"Raw files selected: {len(tiles)}")
    print("Weeks:", sorted({tile.week_key for tile in tiles}))
    print(
        "Tiles:",
        [
            (tile.tile_id, tile.tile_key, tile.split)
            for tile in sorted(
                {t.tile_key: t for t in tiles}.values(), key=lambda x: x.tile_id
            )
        ],
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_inventory(OUTPUT_ROOT, tiles)
    write_split_manifest(OUTPUT_ROOT, tiles)

    for patch_size in PATCH_SIZES:
        generate_shards_for_patch_size(tiles, patch_size)
        rebuild_index_and_manifest(tiles, patch_size)
        smoke_load(patch_size)

    print("Patch factory complete:", OUTPUT_ROOT)


if __name__ == "__main__":
    run_patch_factory()
