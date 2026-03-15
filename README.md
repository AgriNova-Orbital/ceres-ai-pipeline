# Ceres AI Pipeline

**A machine learning pipeline for NDVI forecasting and wheat rust risk analysis by AgriNova-Orbital**

This project demonstrates a Python-based pipeline for predicting next-week NDVI (Normalized Difference Vegetation Index) from Sentinel-2 time-series data using a CNN-LSTM regression model.

> **⚠️ Target Leakage Notice:** Statistical analysis confirmed that the original risk labels
> (band 11) in the France 2025 GeoTIFF dataset equal `1 − NDVI` (band 1) to within float32
> machine epsilon — training on them teaches only the trivial identity, not genuine predictive
> signal. As of PR #4 and PR #6, the pipeline has fully transitioned to **NDVI time-series
> forecasting** (MSE regression) as the primary training task. The deprecated
> `train_wheat_risk_lstm.py` script is retained for reference only; use
> `train_ndvi_forecast.py` and `build_ndvi_forecast_dataset.py` for all new training.

## 🌟 Features

- **Data Downloader**: Fetch Sentinel-2 data via Earth Engine (STAC/Drive)
- **Dataset Builder**: Parallel patch extraction and NDVI forecasting window construction (`build_ndvi_forecast_dataset.py`)
- **Staged Training Matrix**: Nested-loop execution for experimenting with image granularity and sample sizes (NDVI regression, MSE loss)
- **Evaluation & Model Selection**: MSE-based model comparison across matrix cells
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

#### Local process mode

Launch the main application, which runs both the WebUI and the background job runner.

**Note:** This requires a Redis server to be running for task queue management.

```bash
uv run scripts/main.py
```

Then open:
```text
http://127.0.0.1:5055
```

#### Container mode (recommended next deployment target)

The current deployment branch introduces a split stack:
- `web`
- `worker`
- `redis`

With persistent SQLite state mounted at `/app/state/app.db`.

Start it with:

```bash
docker compose up --build
```

The `worker` service is the only container that should receive GPU access.

On first launch, the app should enter **Initialization** before login:
- set OAuth client secret path
- set redirect base URL
- save settings into SQLite

After initialization, users can sign in with Google.

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

## 🗺️ Roadmap & Future Work

The following items are planned to expand coverage, robustness, and operational capability.

### Data Source Expansion
- **Single-file GEE exports**: Refactor GEE export pipeline to output single multi-band temporal stacks instead of many individual files, reducing IO/Drive limits.
- **Timestamp-based NPZ building**: Update `build_npz_dataset_from_geotiffs.py` to parse explicit time metadata embedded inside single multi-band TIFFs instead of relying on file names/indices.
- **Landsat integration**: Ingest Landsat-8/9 Surface Reflectance (SR) via GEE STAC alongside Sentinel-2 for higher revisit rate and sensor fusion.
- **Multi-sensor fusion strategy**: Define harmonized band mapping (Sentinel-2 vs Landsat) and normalization to a common grid.
- **Multi-year history (4-5 years)**: Expand the weekly raster archive from 1-year to 4-5 years of continuous coverage to improve temporal robustness.
- **Weather / climate features**: Integrate auxiliary meteorological variables (temperature, rainfall, humidity, soil moisture) from public climate datasets.

### Model & Training
- **Model lightweighting**: Evaluate teacher-student distillation, quantization-aware training (QAT), or architecture pruning to reduce footprint while preserving recall.
- **Spatiotemporal backbone**: Experiment with ConvLSTM / Temporal CNN / TimeSformer to improve sequence consistency.
- **Self-supervised pretraining**: Explore SSL pretraining on large unlabelled spatiotemporal patches to improve label efficiency.
- **Threshold calibration**: Automated threshold sweeps across regions/cultivars to produce reproducible operational thresholds.

### Platform & Deployment
- **Multi-user OAuth (Done)**: Completed as of this release.
- **Monitoring**: Add structured logging and basic dashboards for queue length, job latency, and resource usage.
- **Object storage cache**: Optional S3/MinIO cache for staged datasets to speed up re-train cycles.
- **Container images**: Publish versioned images for `web`, `worker`, and `redis`.

### 🛠️ Operational CLI Usage

For detailed documentation on the pipeline scripts (dataset creation, training, etc.), see [docs/WHEAT_RISK_PIPELINE.md](docs/WHEAT_RISK_PIPELINE.md).

### Expanding Source Time Range

If you later expand the source data date range (for example from 2025-only to multi-year), use this sequence:

1. Export weekly rasters for the new window (dry-run first, then run).
2. Ingest/download the new GeoTIFFs to raw storage.
3. Run date inventory to verify 7-day completeness and check missing dates.
4. Rebuild per-level NDVI forecasting datasets (L1/L2/L4) from the expanded raw set.
5. Re-run staged matrix training (NDVI regression, MSE loss) and evaluation.
6. Promote the new best checkpoint.

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

# 3) Rebuild per-level NDVI forecasting datasets
#    (replaces the old build_npz_dataset_from_geotiffs.py approach)
uv run scripts/build_ndvi_forecast_dataset.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/ndvi_forecast/L1 \
  --window-size 4 --patch-size 64 --step-size 32

uv run scripts/build_ndvi_forecast_dataset.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/ndvi_forecast/L2 \
  --window-size 4 --patch-size 32 --step-size 16

uv run scripts/build_ndvi_forecast_dataset.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/ndvi_forecast/L4 \
  --window-size 4 --patch-size 16 --step-size 8

# 4) Re-train NDVI regression matrix and re-evaluate
uv run scripts/run_staged_training_matrix.py \
  --run --execute-train \
  --levels 1,2,4 --steps 100,500,2000 --base-patch 64 \
  --index-csv-template ./data/ndvi_forecast/L{level}/index.csv \
  --runs-dir runs/ndvi_staged --device cuda

uv run scripts/eval_staged_training_matrix.py \
  --summary-csv runs/ndvi_staged/summary.csv \
  --index-csv-template ./data/ndvi_forecast/L{level}/index.csv
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
