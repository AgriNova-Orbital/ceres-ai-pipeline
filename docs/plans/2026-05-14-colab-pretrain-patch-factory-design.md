# Colab Pre-Train Patch Factory Design

**Status:** Design draft

**Goal:** Define the pre-train data staging flow from Earth Engine raw GeoTIFF exports to sharded patch datasets that can be validated and loaded for model training.

**Scope:** This design covers raw data staging, Colab patch generation, sharded NPZ layout, validation gates, and the repo loader needed before training. It does not cover full production training orchestration or model promotion implementation.

## Summary

The pre-train flow prepares model-ready patch datasets before any heavy training starts. Earth Engine exports weekly wheat feature GeoTIFFs to Google Drive. Colab reads those raw split GeoTIFFs directly, validates their schema, cuts deterministic grid patches, and writes sharded NPZ datasets back to Drive. The repo then adds a sharded dataset loader so training code can consume the staged outputs by split.

High-level flow:

```text
Earth Engine export
  -> Google Drive raw GeoTIFF folder
  -> Colab Patch Factory
  -> Sharded NPZ staged dataset
  -> Dataset validation
  -> Repo sharded loader
  -> Training / evaluation
```

## Raw Data Layer

The raw input is the Earth Engine split GeoTIFF output. The current Drive folder is:

```text
MyDrive/wheat_data_v2.0-beta/
```

Expected filename format:

```text
fr_wheat_feat_YYYYWww-rowOffset-colOffset.tif
```

Each GeoTIFF must contain 11 bands in this order:

```text
ndvi
ndmi
nbr
s1_vv
s1_vh
s1_vh_vv
rain_mm
temp_c_mean
temp_c_max
lst_c
risk
```

Required raster metadata:

```text
dtype: float32
nodata: -32768
label band: risk
feature bands: first 10 bands
```

Raw tiles should not be merged before patch generation. Earth Engine already splits the AOI into manageable files. Merging would create much larger rasters, increase Colab and Drive I/O risk, and is not needed for the first version. Patches do not cross tile boundaries.

Edge tiles may be narrower than the normal Earth Engine split size. The patch factory should accept partial edge tiles and ignore incomplete edge pixels that cannot form a full patch.

## Colab Patch Factory

The first implementation is notebook-only and lives at:

```text
notebooks/colab_patch_factory_smoke.py
```

The Colab script performs these steps:

1. Mount Google Drive.
2. Install missing runtime dependencies such as `rasterio` and `tqdm`.
3. Scan the raw GeoTIFF folder.
4. Parse `week_key`, `row_offset`, and `col_offset` from filenames.
5. Validate band count, band order, dtype, nodata, and CRS.
6. Build a shared tile-based split manifest.
7. Generate `64x64` patch shards.
8. Generate `128x128` patch shards.
9. Write `index.csv`, `manifest.json`, `raw_inventory.csv`, and `split_manifest.json`.
10. Smoke-load one shard per patch size and print shape and label summaries.

Smoke run configuration:

```python
RAW_DIR = DRIVE_ROOT / "wheat_data_v2.0-beta"
WEEK_START = "2025W36"
WEEK_END = "2025W38"
OUTPUT_ROOT = DRIVE_ROOT / "Ceres" / "staged" / "2025w36_w38_grid_v1_smoke"
```

Full run configuration:

```python
RAW_DIR = DRIVE_ROOT / "wheat_data_v2.0-beta"
WEEK_START = "2025W36"
WEEK_END = "2025W52"
OUTPUT_ROOT = DRIVE_ROOT / "Ceres" / "staged" / "2025w36_w52_grid_v1"
```

The patch factory is CPU, RAM, and Drive I/O heavy. It does not meaningfully benefit from T4 GPU or TPU. Use GPU later for model training.

## Patch Generation

Generate both patch sizes:

```text
64x64
128x128
```

Patch generation rules:

```text
deterministic grid tiling
no random sampling
no raw merge
no cross-tile patches
ignore incomplete edge pixels
```

Each sample contains:

```text
X = (10, H, W)
y = scalar
valid_mask = (H, W)
```

Definitions:

```text
X = bands 1-10
y = mean(risk valid pixels)
valid_mask = (ndvi != -32768) AND (risk != -32768)
```

Keep a patch only when:

```text
valid_mask.mean() >= 0.80
```

`X` keeps the raw nodata sentinel `-32768`. Do not replace nodata with `0` or `NaN` during staging. Normalization and training should use `valid_mask` to avoid treating nodata as valid signal.

## Output Layout

Smoke output layout:

```text
MyDrive/Ceres/staged/2025w36_w38_grid_v1_smoke/
+-- raw_inventory.csv
+-- split_manifest.json
+-- p64/
|   +-- manifest.json
|   +-- index.csv
|   +-- shards/
+-- p128/
    +-- manifest.json
    +-- index.csv
    +-- shards/
```

Full output layout:

```text
MyDrive/Ceres/staged/2025w36_w52_grid_v1/
+-- raw_inventory.csv
+-- split_manifest.json
+-- p64/
|   +-- manifest.json
|   +-- index.csv
|   +-- shards/
+-- p128/
    +-- manifest.json
    +-- index.csv
    +-- shards/
```

Each shard stores a batch of patches, not a single patch:

```text
X:          (N, 10, H, W), float32
y:          (N,), float32
valid_mask: (N, H, W), bool
week_key:   (N,)
tile_key:   (N,)
tile_id:    (N,)
split:      (N,)
row:        (N,)
col:        (N,)
```

`index.csv` is shard-level. Required columns:

```csv
shard_path,patch_size,num_samples,week_key,tile_key,tile_id,split,row_start,row_end,col_offset
```

## Split Strategy

Use tile-based split to reduce spatial leakage. Split assignment is based on sorted tile offsets, not individual patches.

Default rule for four tiles:

```text
tile 0,1 -> train
tile 2   -> val
tile 3+  -> test
```

The `p64` and `p128` datasets must share the same `split_manifest.json`. This keeps comparisons between patch sizes fair and avoids split-driven metric differences.

## Recovery Strategy

Patch generation must be resumable because Colab sessions can disconnect.

Rules:

```text
SKIP_EXISTING=True
write shard to local temp path first
move completed shard to final Drive path
skip valid existing shards on rerun
rebuild index and manifest by scanning final shards
```

This avoids relying on in-memory counters and prevents half-written shards from being treated as valid output.

## Validation Gate

After patch generation, validate the staged dataset before training.

Required checks:

```text
p64/manifest.json exists
p128/manifest.json exists
p64/index.csv has rows
p128/index.csv has rows
total_shards > 0
total_samples > 0
split_counts includes train and validation data
week_counts includes expected smoke or full range weeks
smoke load prints X/y/valid_mask shapes
y min/mean/max are finite
valid_mask mean is reasonable
```

Do not start full training until the smoke dataset passes these checks. Do not start full-range patch generation until the smoke run is healthy.

## Repo Integration

The repo needs a new sharded dataset loader after the Colab smoke output is validated.

Proposed loader:

```text
WheatRiskShardedNpzDataset
```

Responsibilities:

```text
read shard-level index.csv
support split="train" | "val" | "test"
map global sample index to shard path and local offset
load X/y for one sample
optionally load valid_mask
use small LRU cache for recently opened shards
```

First version return value:

```python
x, y
```

Future mask-aware version:

```python
x, y, valid_mask
```

The loader should have tests for:

```text
index parsing
total length calculation
global-to-local index mapping
split filtering
missing shard error
invalid shard schema error
optional mask return
```

## Training Flow After Pre-Train

Once the sharded loader exists, training can consume staged datasets directly:

```text
Colab or lab VM
  -> load p64/index.csv or p128/index.csv
  -> train split for optimization
  -> val split for model selection
  -> test split for final evaluation
  -> write checkpoint and metrics
  -> lab VM pulls artifacts
  -> validate and promote model
```

Recommended first training order:

```text
p64 smoke train
p128 smoke train
p64 full train
p128 full train
compare validation and test metrics
```

Training artifacts should be written under:

```text
MyDrive/Ceres/artifacts/colab/<run_id>/
├── model.pt
├── metrics.json
├── summary.csv
├── train_config.json
├── dataset_manifest.json
└── logs/
```

The lab VM pulls artifacts back into:

```text
artifacts/colab/<run_id>/
```

Only validated artifacts should be promoted for pilot use. Model promotion remains separate from application deployment.

## Current Next Steps

1. Run `notebooks/colab_patch_factory_smoke.py` in Colab with `WEEK_START="2025W36"` and `WEEK_END="2025W38"`.
2. Confirm `p64` and `p128` each produce `index.csv`, `manifest.json`, and at least one shard.
3. Review `total_samples`, `split_counts`, `week_counts`, and label summaries.
4. If smoke output is healthy, run the full `2025W36-W52` patch factory.
5. Add `WheatRiskShardedNpzDataset` with tests.
6. Run small training smoke against staged `p64` and `p128` datasets.
