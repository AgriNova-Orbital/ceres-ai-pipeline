# Wheat Risk Pipeline Documentation 🌾

This document details the scripts and modules used for the Wheat Risk analysis pipeline, focusing on Drive download ingest, dataset creation, management, and model training.

## 1. Drive Download & Canonical GeoTIFF Ingest
**Script**: `scripts/download_drive_folder.py`

### Goal
Download weekly GeoTIFF exports from Google Drive and normalize them into the canonical raw raster contract used by downstream dataset tools.

### Features
- **Drive Download**: Downloads matching `.tif` / `.tiff` files with a progress bar.
- **Shared Ingest Helper**: `--merge` runs `modules.merge_geotiffs.ingest_downloaded_geotiffs()`.
- **Accepted Inputs**:
  - canonical weekly rasters: `fr_wheat_feat_YYYYWww.tif`
  - Earth Engine tile exports: `fr_wheat_feat_YYYYWww-<x>-<y>.tif`
  - legacy `_data_` forms that still encode a week key
- **Canonical Output**: Normalizes valid weekly inputs to `fr_wheat_feat_YYYYWww.tif`.
- **Tile Archival**: After a successful multi-tile merge, original source tiles are moved into `_tiles/<week>/`.
- **Structured Summary**: Reports `merged_weeks`, `single_tile_weeks_normalized`, `failed_weeks`, `warnings`, and `unknown_files`.

### Validation Rules
- Hard-fail on unreadable rasters, wrong canonical filename, band count other than 11, non-`float32` data, `nodata != -32768`, zero width/height, or missing CRS.
- Warn when band descriptions are missing, partially missing, or present in an unexpected order.
- Multi-tile merges write into a temporary path first and only rename into place after validation succeeds.

### Usage
```bash
uv run scripts/download_drive_folder.py \
  --folder "YOUR_DRIVE_FOLDER_ID" \
  --save ./data/raw/france_2025_weekly \
  --merge
```

### Expected Results
- `./data/raw/france_2025_weekly/fr_wheat_feat_YYYYWww.tif` for each validated week
- `./data/raw/france_2025_weekly/_tiles/<week>/...` for archived source tiles after successful merges
- an ingest summary printed to stdout

### Notes
- Single-tile weekly exports can still be normalized without GDAL.
- Multi-tile merges require GDAL; when GDAL is unavailable the ingest summary reports failures/warnings instead of silently pretending the merge succeeded.
- Downstream dataset builders intentionally ignore tile-suffixed weekly exports. Normalize them first before training.

---

## 2. Dataset Generation
**Script**: `scripts/build_npz_dataset_from_geotiffs.py`

### Goal
Converts a directory of canonical weekly GeoTIFF images into a machine-learning-ready dataset of temporal sequences. It extracts patches from the images and saves them as `.npz` files.

### features
- **Downloads Inputs**: Can optionally download GeoTIFFs directly from Google Drive.
- **Temporal Alignment**: Aligns weekly images into a time-series (T, C, H, W).
- **Patch Extraction**: Cuts large GeoTIFFs into smaller patches (e.g., 32x32 pixels) for training.
- **Handling Missing Data**: Pads missing weeks with placeholder values so the time dimension remains consistent.

### Input Contract
- Preferred raw input names: `fr_wheat_feat_YYYYWww.tif`
- Supported compatibility names: existing `fr_wheat_feat_YYYY_data_...` forms already used elsewhere in the repo
- Not accepted as direct dataset inputs: Earth Engine tile-suffixed weekly exports like `fr_wheat_feat_2025W01-0000009984-0000000000.tif`

If your Drive folder contains split weekly exports, normalize them first with `scripts/download_drive_folder.py --merge` (or the WebUI downloader job) before running dataset build.

### Usage
```bash
# Basic usage with local files
uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir ./data/raw_tiffs \
  --output-dir ./data/dataset_output \
  --patch-size 32 \
  --expected-weeks 20

# Download from Google Drive and build
uv run scripts/build_npz_dataset_from_geotiffs.py \
  --drive-folder-id "YOUR_DRIVE_FOLDER_ID" \
  --input-dir ./data/raw_tiffs \
  --output-dir ./data/dataset_output \
  --drive-credentials-json client_secret.json
```

Use the direct `--drive-folder-id` path when the Drive folder already contains canonical weekly rasters or legacy `_data_` inputs. For split Earth Engine tiles, run the dedicated downloader ingest step first.

### Expected Results
The `--output-dir` will contain:
- `index.csv`: A manifest file listing all generated samples.
  ```csv
  npz_path
  examples/patch_r00000_c00000.npz
  examples/patch_r00000_c00032.npz
  ...
  ```
- `examples/`: A subdirectory containing individual `.npz` files.
  - Each `.npz` file contains:
    - `X`: Shape `(Time, Channels, Height, Width)` - The feature data.
    - `y`: Shape `(Time,)` - The risk labels.

---

## 3. Index Management
**Script**: `scripts/rebuild_index.py`

### Goal
A utility script to regenerate the `index.csv` file for a dataset. This is useful if you manually move `.npz` files or if the index becomes corrupted.

### Usage
```bash
# Point it to the directory containing 'examples/'
uv run scripts/rebuild_index.py ./data/dataset_output
```

### Expected Results
- Scans `data/wheat_risk/stage1/examples/*.npz` (or the modified path).
- Re-creates `data/wheat_risk/stage1/index.csv` listing all found files.

---

## 4. Model Training
**Script**: `scripts/train_wheat_risk_lstm.py`

### Goal
Trains a CNN + LSTM (ConvLSTM) neural network on the dataset generated by step 1. It learns to predict wheat risk over time based on the input features.

### Usage
```bash
uv run scripts/train_wheat_risk_lstm.py \
  --index-csv ./data/dataset_output/index.csv \
  --root-dir ./data/dataset_output \
  --epochs 10 \
  --batch-size 16 \
  --device cpu  # or 'cuda' for GPU
```

### Expected Results
- Prints training progress (loss per epoch) to the console.
- **Note**: Currently, the script does not save checkpoints automatically (demonstration/baseline version). You would likely want to add model saving logic for production use.

---

## 5. Date Inventory & Missing-Date Report
**Script**: `scripts/inventory_wheat_dates.py`

### Goal
Build a 7-day cadence inventory from raw GeoTIFF filenames and report timeline completeness before training.

### Usage
```bash
uv run scripts/inventory_wheat_dates.py \
  --input-dir /path/to/raw_tiffs \
  --output-dir ./reports \
  --start-date 2025-01-01 \
  --cadence-days 7
```

### Expected Results
- `reports/data_inventory.json`
  - `earliest_date`, `latest_date`, `total_days`
  - `expected_nodes`, `observed_nodes`, `missing_count`, `missing_rate`
- `reports/missing_dates.csv`
  - columns: `date`, `position`, `reason`

---

## 6. 2D Staged Training Matrix (Nested Loop)
**Script**: `scripts/run_staged_training_matrix.py`

### Goal
Generate and execute a strict nested-loop plan:
- Outer loop: image granularity levels
- Inner loop: sample-size steps

### Usage
```bash
# Dry-run (recommended first): print exact execution order
uv run scripts/run_staged_training_matrix.py \
  --dry-run \
  --levels 1,2,4 \
  --steps 100,500,2000 \
  --base-patch 64

# Plan artifacts mode (creates per-cell directories and summary CSV)
uv run scripts/run_staged_training_matrix.py \
  --run \
  --levels 1,2,4 \
  --steps 100,500,2000 \
  --base-patch 64

# Execute training per matrix cell (nested loop order)
uv run scripts/run_staged_training_matrix.py \
  --run \
  --execute-train \
  --levels 1,2,4 \
  --steps 100,500,2000 \
  --base-patch 64 \
  --index-csv ./data/wheat_risk/stage1/index.csv \
  --root-dir ./data/wheat_risk/stage1 \
  --device cuda

# Execute training with per-level datasets (recommended for true granularity sweep)
uv run scripts/run_staged_training_matrix.py \
  --run \
  --execute-train \
  --levels 1,2,4 \
  --steps 100,500,2000 \
  --base-patch 64 \
  --index-csv-template ./data/wheat_risk/staged/L{level}/index.csv \
  --root-dir-template ./data/wheat_risk/staged/L{level} \
  --device cuda
```

### Expected Results
- Nested order:
  - `L1-S100 -> L1-S500 -> L1-S2000 -> L2-S100 -> ... -> L4-S2000`
- Artifacts in `runs/staged/`:
  - `runs/staged/Lx/Sy/config.json`
  - `runs/staged/Lx/Sy/train_subset.csv`
  - `runs/staged/Lx/Sy/train.log`
  - `runs/staged/Lx/Sy/model.pt`
  - `runs/staged/summary.csv`

---

## 7. Internal Utilities
**Module**: `modules/wheat_risk/data_cache.py`

### Goal
A helper module for managing cached datasets. It is not meant to be run directly but is used by other tools to ensure data is available.

### Features
- **Automatic Downloading**: Fetches datasets from URLs.
- **Archive Extraction**: extract `.tar` and `.tar.zst` archives safely.
- **Concurrency Safety**: Uses file locks to prevent race conditions when multiple processes try to download/extract data simultaneously (e.g., in a Ray cluster).

### Usage (Python)
```python
from modules.wheat_risk.data_cache import ensure_dataset_cached
from pathlib import Path

# Ensures data exists at cache_root/my_dataset
dataset_path = ensure_dataset_cached(
    data_url="https://example.com/data.tar.zst",
    dataset_name="my_dataset",
    cache_root=Path("./.cache")
)
```
