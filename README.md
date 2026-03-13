# Ceres AI Pipeline

**A machine learning pipeline for wheat rust risk prediction by AgriNova-Orbital**

This project demonstrates a Python-based pipeline for predicting wheat rust risk using Sentinel-2 time-series data and a CNN-LSTM model.

## 🌟 Features

- **Data Downloader**: Fetch Sentinel-2 data via Earth Engine (STAC/Drive)
- **Dataset Builder**: Parallel patch extraction and weekly cadence interpolation
- **Staged Training Matrix**: Nested-loop execution for experimenting with image granularity and sample sizes
- **Evaluation & Model Selection**: Automated threshold tuning for recall-first risk detection
- **WebUI Control Panel**: A Flask-based interface to orchestrate the pipeline and preview images

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- `uv` (Python package manager)
- (Optional) Redis server for the background job queue

### Installation

1. Clone the repository:
```bash
git clone https://github.com/AgriNova-Orbital/ceres-ai-pipeline.git
cd ceres-ai-pipeline
```

2. Sync dependencies:
```bash
uv sync --dev --extra ml --extra distributed
```

### Launch the WebUI

Launch the main application, which runs both the WebUI and the background job runner.

**Note:** This requires a Redis server to be running for task queue management.

```bash
uv run scripts/main.py
```

Then open:
```text
http://127.0.0.1:5055
```

Prototype includes:
- Data Downloader actions (preview export / run export / refresh inventory)
- Data and patch image preview endpoints (`/api/preview/raw`, `/api/preview/patch`)
- Dataset build controls (single level / all levels)
- Training matrix dry-run and execute actions
- Evaluation trigger and run history panel

For a full step-by-step manual, see:

- `docs/USER_GUIDE.md`

Deployment and operations references:

- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/RISK_REVIEW.md`

## 🛠️ Operational CLI Usage

For detailed documentation on the pipeline scripts (dataset creation, training, etc.), see [docs/WHEAT_RISK_PIPELINE.md](docs/WHEAT_RISK_PIPELINE.md).

### Expanding Source Time Range

If you later expand the source data date range (for example from 2025-only to multi-year), use this sequence:

1. Export weekly risk rasters for the new window (dry-run first, then run).
2. Ingest/download the new GeoTIFFs to raw storage.
3. Run date inventory to verify 7-day completeness and check missing dates.
4. Rebuild staged datasets (L1/L2/L4) from the expanded raw set.
5. Re-run staged matrix training and evaluation.
6. Promote the new best checkpoint and threshold.

Example commands:

```bash
# 1) Export planning and execution for expanded dates
uv run scripts/export_weekly_risk_rasters.py \
  --stage 1 \
  --start-date 2024-01-01 \
  --end-date 2026-12-31 \
  --limit 8 \
  --dry-run

# run for real (requires Drive folder)
uv run scripts/export_weekly_risk_rasters.py \
  --stage 1 \
  --start-date 2024-01-01 \
  --end-date 2026-12-31 \
  --drive-folder EarthEngine \
  --run

# 2) Inventory completeness on raw tiffs
uv run scripts/inventory_wheat_dates.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir reports \
  --start-date 2025-01-01 \
  --cadence-days 7

# 3) Rebuild staged datasets
uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L1 \
  --patch-size 64 --step-size 64 --expected-weeks 46 --max-patches 12000

uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L2 \
  --patch-size 32 --step-size 32 --expected-weeks 46 --max-patches 12000

uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L4 \
  --patch-size 16 --step-size 16 --expected-weeks 46 --max-patches 12000

# 4) Re-train matrix and re-evaluate
uv run scripts/run_staged_training_matrix.py \
  --run --execute-train \
  --levels 1,2,4 --steps 100,500,2000 --base-patch 64 \
  --index-csv-template ./data/wheat_risk/staged/L{level}/index.csv \
  --root-dir-template ./data/wheat_risk/staged/L{level} --device cuda

uv run scripts/eval_staged_training_matrix.py \
  --summary-csv runs/staged_final/summary.csv \
  --index-csv-template ./data/wheat_risk/staged/L{level}/index.csv \
  --root-dir-template ./data/wheat_risk/staged/L{level}
```

WebUI planning reference:
`docs/plans/2026-02-13-wheat-risk-webui-planning.md`

### Experimental STAC ML Pipeline

```bash
# Experimental Sentinel-2 STAC quicklook (local test)
uv run experiments/sentinel2_stac_ml_pipeline.py --no-show
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
