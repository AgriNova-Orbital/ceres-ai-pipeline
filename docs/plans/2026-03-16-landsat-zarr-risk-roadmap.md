# Landsat Zarr Risk Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the pipeline from the old weekly GeoTIFF + leaked risk-label workflow to a leakage-safe, Landsat-aware, Zarr-backed training pipeline while keeping the long-term product objective aligned with wheat risk modeling.

**Architecture:** Treat the new Earth Engine export format as the new source-of-truth contract: one GeoTIFF stores 4 weekly slices x 8 bands, with noData=-32768 and optical data already fused across Sentinel-2 and Landsat-8/9. First, lock the export schema and build a parser that reconstructs a continuous weekly tensor timeline. Second, use leakage-free NDVI forecasting as an interim validation task while the true risk target is redefined. Third, freeze the tensor schema and migrate storage, training, evaluation, and WebUI preview paths to Zarr.

**Tech Stack:** Google Earth Engine, GeoTIFF, rasterio, numpy, zarr, PyTorch, Flask, RQ, pytest.

---

### Task 1: Freeze the New Export Contract

**Files:**
- Create: `docs/datasets/france_wheat_chunk_schema.md`
- Create: `scripts/inspect_chunked_geotiff.py`
- Create: `scripts/verify_chunk_band_layout.py`
- Modify: `README.md`

**Step 1: Document the export contract**

Write down the exact meaning of the new Earth Engine output:

- one file per year/chunk, e.g. `France_Wheat_Y2021_C01.tif`
- 13 chunks per year
- each file stores 4 weeks x 8 bands = 32 bands
- weekly band order: `Blue, Green, Red, NIR, SWIR1, SWIR2, VV, VH`
- optical bands are fused from Sentinel-2 + Landsat-8/9
- noData is `-32768`
- optical values are scaled approximately to `0..10000`, SAR to `x100`

**Step 2: Add inspection scripts**

Create scripts that print:

- raster size, CRS, dtype, nodata
- per-band descriptions (if preserved)
- finite ratio / nodata ratio / min / max / mean
- a quick warning if the file does not have exactly 32 bands

**Step 3: Update README language**

Keep the public objective as wheat risk modeling, but add a note that:

- the old risk label had leakage
- NDVI forecasting is now used as an interim leakage-free validation task
- the long-term objective remains risk modeling

**Definition of done:** A new contributor can inspect one downloaded file and understand its band layout, scale, nodata policy, and temporal meaning without reverse-engineering the Earth Engine script.

### Task 2: Build a Chunked GeoTIFF Ingestion Layer

**Files:**
- Modify: `modules/services/dataset_service.py`
- Modify: `scripts/build_npz_dataset_from_geotiffs.py`
- Create: `tests/services/test_dataset_service_chunked.py`
- Modify: `tests/services/test_dataset_service.py`

**Step 1: Replace old assumptions**

Remove these implicit assumptions from the current builder:

- one file equals one week
- last band is the supervised risk target
- time is derived only from filename patterns like `fr_wheat_feat_YYYYWww`

**Step 2: Add chunk parsing**

Teach the builder to read files like `France_Wheat_Y2021_C01.tif` and reconstruct:

- year
- chunk index
- within-chunk week offset `W1..W4`
- absolute weekly order across 2021-2025

Recommended default:

- keep the current 4-week chunk export format
- solve temporal reconstruction in Python ingestion rather than changing the exporter again immediately

**Step 3: Decode per-week tensors**

For each chunk file:

- reshape 32 bands into `(4, 8, H, W)`
- convert `-32768` to invalid mask
- cast to `float32`
- restore physical scales if needed
- append a mask channel so the model sees valid vs imputed pixels explicitly

**Step 4: Preserve temporal metadata**

Persist per-sample metadata needed later by Zarr and training:

- `year`
- `chunk`
- `week_offset`
- `global_week_index`
- optional `date_start`

**Definition of done:** The builder can reconstruct a continuous weekly tensor timeline from the new exported files and produce non-empty training samples with explicit masks.

### Task 3: Launch a Leakage-Free Interim Task (NDVI Forecasting)

**Files:**
- Create: `modules/services/ndvi_forecast_service.py`
- Create: `scripts/build_ndvi_forecast_dataset.py`
- Create: `scripts/train_ndvi_forecast.py`
- Create: `modules/wheat_risk/ndvi_dataset.py`
- Create: `modules/wheat_risk/ndvi_model.py`
- Create: `tests/test_ndvi_forecast_dataset.py`
- Create: `tests/test_train_ndvi_forecast.py`
- Modify: `scripts/run_staged_training_matrix.py`
- Modify: `modules/services/training_matrix_service.py`

**Step 1: Define the interim supervised target**

Use a strictly causal target:

- inputs: previous `W` weeks of fused optical + SAR + mask channels
- target: next week's NDVI, derived from `NIR` and `Red`

Do not export or train on any same-timestep target that is directly derived from the current inputs.

**Step 2: Build the NDVI dataset**

Each sample should contain:

- `X`: `(T, C, H, W)`
- `y`: scalar or short horizon NDVI target
- `mask`: validity mask or mask channel embedded in `X`
- metadata for auditability

**Step 3: Add the NDVI trainer**

Create a dedicated regression training path with:

- `NdviForecastDataset`
- `CnnLstmRegressor`
- MSE / MAE metrics
- optional baseline metrics such as persistence forecast comparison

**Step 4: Update the staged matrix runner**

Switch matrix execution so it can call `scripts/train_ndvi_forecast.py` and stop emitting classification-only arguments.

**Definition of done:** The pipeline can train end-to-end on a leakage-free surrogate task, producing stable samples, checkpoints, and metrics from the new export format.

### Task 4: Freeze the Unified Tensor Schema and Migrate to Zarr

**Files:**
- Modify: `modules/services/dataset_service.py`
- Modify: `modules/services/ndvi_forecast_service.py`
- Modify: `modules/wheat_risk/dataset.py`
- Modify: `scripts/train_ndvi_forecast.py`
- Modify: `modules/services/training_matrix_service.py`
- Modify: `modules/services/evaluation_service.py`
- Modify: `apps/wheat_risk_webui.py`
- Modify: `apps/templates/wheat_risk_webui.html`
- Create: `tests/test_zarr_dataset_loader.py`

**Step 1: Lock a stable schema before migrating**

Recommended Zarr arrays:

- `X`: `(N, T, C, H, W)`
- `y_ndvi`: `(N,)` or `(N, horizon)`
- `mask`: `(N, T, 1, H, W)` if not embedded only in `X`
- `meta/year`, `meta/chunk`, `meta/week_offset`, `meta/global_week_index`

**Step 2: Migrate builders and loaders**

Refactor the builders to write `dataset.zarr` instead of many `.npz` files. Update PyTorch dataset loading to read Zarr lazily and safely with DataLoader workers.

**Step 3: Update matrix and preview paths**

Change matrix execution, evaluation, and WebUI previews to read Zarr. Replace any code path that still assumes `index.csv` plus `examples/*.npz` as the only dataset representation.

**Definition of done:** Training, evaluation, matrix execution, and preview all work against a shared Zarr-backed dataset contract.

### Task 5: Reintroduce the Real Risk Task Safely

**Files:**
- Create: `docs/plans/2026-03-16-risk-target-redefinition-design.md`
- Modify: `README.md`
- Modify: `docs/WHEAT_RISK_PIPELINE.md`
- Modify: `docs/USER_GUIDE.md`

**Step 1: Keep the external objective stable**

Public/project language should remain:

- final objective: wheat risk modeling
- interim task: NDVI forecasting used to validate data and model plumbing after leakage was discovered

**Step 2: Design a non-leaking risk target**

Only move back to a risk task after one of these exists:

- an external disease/event label
- a delayed or future-horizon proxy target
- a weak label that is not a direct same-timestep transform of the input channels

**Step 3: Publish the rationale clearly**

Document:

- why the old label was invalid
- why NDVI forecasting is technically defensible as an interim task
- what must be true before the project claims a valid risk-prediction benchmark again

**Definition of done:** The project can explain, without contradiction, why the current implementation may train on NDVI forecasting while the long-term product objective remains wheat risk prediction.

### Task 6: Parallel Platform Stabilization

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `modules/jobs/tasks.py`
- Modify: `modules/jobs/worker.py`
- Modify: `docker-compose.yml`
- Modify: `tests/test_webui_enqueues_jobs.py`
- Modify: `tests/test_fakeredis_mode.py`

**Step 1: Keep queue fixes independent**

The Redis/WebUI/FakeRedis fixes can continue in parallel because they are orthogonal to the Landsat/Zarr/NDVI data path.

**Step 2: Expose task mode clearly**

Make job metadata explicit about which pipeline is running:

- `task_type=ndvi_forecast_build`
- `task_type=ndvi_forecast_train`
- later `task_type=risk_train`

**Definition of done:** Platform stabilization does not block data-path evolution, and operators can tell whether a job is running the surrogate NDVI task or a future risk task.

## Recommended Delivery Order

1. Freeze export contract and inspect real files.
2. Upgrade ingestion for chunked GeoTIFFs.
3. Stand up NDVI forecasting as the leakage-free interim benchmark.
4. Migrate the now-stable tensor contract to Zarr.
5. Redefine and reintroduce the real risk target.
6. Keep queue/WebUI fixes moving in parallel.

## Report-Friendly Positioning

- The long-term product objective remains wheat risk modeling.
- A data audit revealed that the earlier risk label was not a valid supervised target because it was directly derivable from the same-timestep inputs.
- Therefore, the roadmap introduces NDVI forecasting as an interim leakage-free validation task while the data contract, Landsat integration, and storage layer are upgraded.
- Once the new data stack is stable and a non-leaking risk target is defined, the pipeline returns to a true risk-modeling objective.
