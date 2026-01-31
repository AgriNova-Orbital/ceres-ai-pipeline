# GEE Wheat Rust Risk Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a GEE-backed, weekly multi-sensor pipeline that generates (1) patch tensors for PyTorch CNN+LSTM seq2seq training and (2) weekly risk rasters exported to Google Drive for a France wheat belt AOI.

**Architecture:** Use Google Earth Engine as the single source of truth for all imagery and environmental inputs. Compute weekly aligned multi-source feature stacks (optical + SAR + meteo + LST) on cropland-only pixels, generate a weak-label risk map per week, then (a) sample patch tensors and labels for training and (b) export weekly risk rasters.

**Tech Stack:** Google Earth Engine (earthengine-api), Python 3.14, uv, PyTorch (stage-1), NumPy, (optional) zarr/npz for tensors, pytest.

---

## Fixed Inputs (Agreed)

- **AOI bbox:** `[-1.5, 47.0, 6.5, 50.9]` (France, wide wheat belt)
- **Date range:** `2025-01-01` to `2025-12-31`
- **Time grain:** weekly
- **Cropland mask:** required (prefer `ESA/WorldCover`)
- **Weak label:** Mix A: `risk = sigmoid(w1*gaussian_pheno + w2*r0_env + w3*remote_stress)`
- **Training:** Patch-level CNN + LSTM, **seq2seq** outputs
- **Exports:** Weekly risk rasters exported as GeoTIFF to **Google Drive**
- **Stage presets:**
  - Stage 1: 100m, 32x32
  - Stage 2: 50m, 64x64
  - Stage 3: 10m, 96x96

---

# Task 1: Add configuration schema and presets

**Files:**
- Create: `modules/wheat_risk/config.py`
- Test: `tests/test_wheat_risk_config.py`

**Step 1: Write the failing test**

Create `tests/test_wheat_risk_config.py`:

```python
from modules.wheat_risk.config import PipelineConfig, StagePreset


def test_stage_presets_exist_and_have_expected_values():
    s1 = StagePreset.stage1()
    assert s1.scale_m == 100
    assert s1.patch_size_px == 32

    s2 = StagePreset.stage2()
    assert s2.scale_m == 50
    assert s2.patch_size_px == 64

    s3 = StagePreset.stage3()
    assert s3.scale_m == 10
    assert s3.patch_size_px == 96


def test_pipeline_config_defaults():
    cfg = PipelineConfig.default_france_2025(StagePreset.stage1())
    assert cfg.start_date == "2025-01-01"
    assert cfg.end_date == "2025-12-31"
    assert cfg.bbox == [-1.5, 47.0, 6.5, 50.9]
    assert cfg.time_grain == "weekly"
```

**Step 2: Run test to verify it fails**

Run: `uv run -m pytest -q`

Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `modules/wheat_risk/config.py` with:

- `StagePreset` dataclass with classmethods `stage1/stage2/stage3`
- `PipelineConfig` dataclass with `bbox, start_date, end_date, time_grain, stage, sample_count, seed, drive_folder, max_cloud, use_dynamicworld`
- `default_france_2025(stage)` classmethod

**Step 4: Run test to verify it passes**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_config.py modules/wheat_risk/config.py
git commit -m "feat: add wheat risk pipeline config presets"
```

---

# Task 2: Implement GEE dataset selectors (collections + band mapping)

**Files:**
- Create: `modules/wheat_risk/collections.py`
- Test: `tests/test_wheat_risk_collections.py`

**Step 1: Write the failing test**

Create `tests/test_wheat_risk_collections.py`:

```python
from modules.wheat_risk.collections import CollectionIds


def test_collection_ids_are_defined():
    assert "COPERNICUS/S2_SR_HARMONIZED" in CollectionIds.SENTINEL2_SR
    assert "COPERNICUS/S1_GRD" in CollectionIds.SENTINEL1_GRD
    assert "ESA/WorldCover" in CollectionIds.WORLDCOVER
```

**Step 2: Run test to verify it fails**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Write minimal implementation**

Create `modules/wheat_risk/collections.py` defining:

- `CollectionIds` (simple constants)
- `OpticalBandMap` for S2 and Landsat (only what we need)
- Helper stubs for `get_s2_sr()`, `get_landsat_l2()`, `get_s1_grd()`, `get_era5_land_hourly()`, `get_chirps_daily()`, `get_modis_lst_8day()`

Keep functions importable without initializing EE (do not call `ee.Initialize()` at import time).

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_collections.py modules/wheat_risk/collections.py
git commit -m "feat: add GEE collection ids and band maps"
```

---

# Task 3: Cropland mask builder

**Files:**
- Create: `modules/wheat_risk/masks.py`
- Test: `tests/test_wheat_risk_masks.py`

**Step 1: Write failing unit test (pure python)**

We cannot unit-test EE objects without EE runtime, so test our parameter validation and that the public API exists.

Create `tests/test_wheat_risk_masks.py`:

```python
from modules.wheat_risk.config import PipelineConfig, StagePreset
from modules.wheat_risk.masks import validate_bbox


def test_validate_bbox_accepts_4_floats():
    validate_bbox([-1.5, 47.0, 6.5, 50.9])


def test_validate_bbox_rejects_bad_values():
    try:
        validate_bbox([0, 0, 1])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
```

**Step 2: Run tests to see failure**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `modules/wheat_risk/masks.py`:

- `validate_bbox(bbox)`
- `build_aoi(bbox)` returns `ee.Geometry.Rectangle`
- `cropland_mask_worldcover(aoi)` using `ESA/WorldCover/v200` and class 40
- Optional: `cropland_mask_dynamicworld(aoi, start_date, end_date)` (mode of labels == crops)
- `get_cropland_mask(cfg)` chooses which mask(s) based on config flags

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_masks.py modules/wheat_risk/masks.py
git commit -m "feat: add cropland mask helpers"
```

---

# Task 4: Weekly time bin utilities

**Files:**
- Create: `modules/wheat_risk/timebins.py`
- Test: `tests/test_wheat_risk_timebins.py`

**Step 1: Write failing test**

Create `tests/test_wheat_risk_timebins.py`:

```python
from modules.wheat_risk.timebins import week_bins


def test_week_bins_2025_has_reasonable_count():
    bins = week_bins("2025-01-01", "2025-12-31")
    assert 50 <= len(bins) <= 54
    assert bins[0][0] <= bins[0][1]
```

**Step 2: Run test to verify it fails**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `modules/wheat_risk/timebins.py`:

- `week_bins(start_date, end_date) -> list[tuple[str,str]]` producing contiguous 7-day bins
- Keep as pure python (no EE dependency) for testability

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_timebins.py modules/wheat_risk/timebins.py
git commit -m "feat: add weekly time bin utilities"
```

---

# Task 5: Weak-label risk components (gaussian_pheno + r0_env + remote_stress)

**Files:**
- Create: `modules/wheat_risk/labels.py`
- Test: `tests/test_wheat_risk_labels.py`

**Step 1: Write failing test (pure python)**

Create `tests/test_wheat_risk_labels.py`:

```python
import math
from modules.wheat_risk.labels import sigmoid, gaussian


def test_sigmoid_bounds():
    assert 0.0 < sigmoid(-10) < 0.01
    assert 0.99 < sigmoid(10) < 1.0


def test_gaussian_peaks_at_mean():
    m = 5.0
    assert gaussian(m, a=0.0, b=1.0, m=m, s=2.0) == 1.0
```

**Step 2: Run tests (fail)**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `modules/wheat_risk/labels.py`:

- Pure python math helpers: `sigmoid(x)`, `gaussian(t, a,b,m,s)`
- EE-facing builders:
  - `gaussian_pheno_weekly(week_index, total_weeks, cfg)` returns scalar prior (as python float or ee.Number)
  - `r0_env_weekly(aoi, start, end, cfg)` returns `ee.Image` with band `r0_env`
  - `remote_stress_weekly(aoi, start, end, cfg, cropland_mask)` returns `ee.Image` with band `remote_stress`
  - `risk_weekly(...)` returns `ee.Image` band `risk`

Keep parameters minimal, with sensible defaults (document inline):

- `w1,w2,w3 = 1.0, 1.0, 1.0`
- Gaussian: peak around mid-season weeks (e.g., week 28-34) with configurable `m,s`

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_labels.py modules/wheat_risk/labels.py
git commit -m "feat: add weak-label risk math and EE builders"
```

---

# Task 6: Weekly multi-source feature stack builder

**Files:**
- Create: `modules/wheat_risk/features.py`
- Test: `tests/test_wheat_risk_features.py`

**Step 1: Write failing test (API surface)**

Create `tests/test_wheat_risk_features.py`:

```python
from modules.wheat_risk.features import FeatureSchema


def test_feature_schema_has_minimum_expected_features():
    schema = FeatureSchema.default()
    for name in ["ndvi", "ndmi", "s1_vv", "s1_vh"]:
        assert name in schema.feature_names
```

**Step 2: Run tests (fail)**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `modules/wheat_risk/features.py`:

- `FeatureSchema` (list of band names)
- `build_weekly_features(aoi, start, end, cfg, cropland_mask) -> ee.Image` with bands:
  - optical indices (from S2+Landsat composited): NDVI, NDMI, NBR
  - SAR: VV, VH, VH/VV
  - meteo: weekly rain sum, temp mean/max, (optionally) humidity proxy
  - LST: weekly mean

Mask all output bands by cropland mask.

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_features.py modules/wheat_risk/features.py
git commit -m "feat: add weekly feature stack builder"
```

---

# Task 7: Patch dataset exporter for PyTorch

**Files:**
- Create: `modules/wheat_risk/export_patches.py`
- Create: `scripts/export_wheat_patches.py`
- Test: `tests/test_wheat_risk_export_shapes.py`

**Step 1: Write failing test (shape conventions)**

Create `tests/test_wheat_risk_export_shapes.py`:

```python
from modules.wheat_risk.config import StagePreset
from modules.wheat_risk.export_patches import patch_tensor_shape


def test_patch_tensor_shape_pytorch_order():
    stage = StagePreset.stage1()
    # T unknown here; ensure H/W follow preset and channel-first
    shape = patch_tensor_shape(time_steps=52, channels=10, stage=stage)
    assert shape == (52, 10, 32, 32)
```

**Step 2: Run tests (fail)**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `modules/wheat_risk/export_patches.py`:

- `patch_tensor_shape(time_steps, channels, stage) -> tuple[int,int,int,int]`
- EE-side sampling function stubs:
  - `sample_patch_grid(aoi, cfg) -> ee.FeatureCollection` (centers on cropland)
  - `export_patch_tensors_to_drive(...)` (initially export per-week images + centers; stage 1 can be small N)

Create `scripts/export_wheat_patches.py`:

- CLI args: `--stage {1,2,3}`, `--samples N`, `--drive-folder`, `--dry-run`
- Initializes EE using existing `modules/gee_api.initialize_ee`

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_export_shapes.py modules/wheat_risk/export_patches.py scripts/export_wheat_patches.py
git commit -m "feat: add patch export scaffolding for PyTorch"
```

---

# Task 8: Weekly risk raster export to Drive

**Files:**
- Create: `scripts/export_weekly_risk_rasters.py`
- Modify: `modules/gee_api.py` (add a small helper if needed)
- Test: `tests/test_wheat_risk_scripts_exist.py`

**Step 1: Write failing test**

Create `tests/test_wheat_risk_scripts_exist.py`:

```python
import importlib


def test_export_scripts_importable():
    importlib.import_module("scripts.export_weekly_risk_rasters")
```

**Step 2: Run tests (fail)**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement**

Create `scripts/export_weekly_risk_rasters.py`:

- Build AOI and cropland mask
- Iterate weekly bins and create `risk_weekly` image
- Export each week as GeoTIFF to Drive using `ee.batch.Export.image.toDrive`
- Use `cfg.stage.scale_m` and `cfg.drive_folder`
- Name exports deterministically: `fr_wheat_risk_YYYYWww`

Avoid exporting more than a small number by default (e.g., `--limit 4`) to keep initial runs safe.

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_scripts_exist.py scripts/export_weekly_risk_rasters.py
git commit -m "feat: add weekly risk raster Drive exporter"
```

---

# Task 9: PyTorch CNN+LSTM training baseline (seq2seq)

**Files:**
- Add: `scripts/train_wheat_risk_lstm.py`
- Create: `modules/wheat_risk/model.py`
- Create: `modules/wheat_risk/dataset.py`
- Test: `tests/test_wheat_risk_model_shapes.py`

**Step 1: Write failing test (forward pass shape)**

Create `tests/test_wheat_risk_model_shapes.py`:

```python
import torch
from modules.wheat_risk.model import CnnLstmRisk


def test_model_forward_seq2seq_shape():
    model = CnnLstmRisk(in_channels=10, embed_dim=64, hidden_dim=128)
    x = torch.randn(2, 52, 10, 32, 32)  # (B,T,C,H,W)
    y = model(x)
    assert y.shape == (2, 52)
```

**Step 2: Run tests (fail)**

Run: `uv run -m pytest -q`

Expected: FAIL

**Step 3: Implement minimal model**

Create `modules/wheat_risk/model.py`:

- Small CNN encoder (2-3 conv blocks) producing `embed_dim`
- LSTM over time
- Linear head to 1 value per timestep
- Sigmoid output in forward (or return logits + loss uses BCEWithLogitsLoss; pick one and be consistent)

Create `modules/wheat_risk/dataset.py`:

- `NpzSequenceDataset(index_csv)` reading `X` and `y` arrays

Create `scripts/train_wheat_risk_lstm.py`:

- Args: `--data-index`, `--epochs`, `--batch-size`, `--lr`
- Train loop + simple metrics (MSE + correlation) as sanity checks

**Step 4: Run tests**

Run: `uv run -m pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_wheat_risk_model_shapes.py modules/wheat_risk/model.py modules/wheat_risk/dataset.py scripts/train_wheat_risk_lstm.py
git commit -m "feat: add PyTorch CNN+LSTM seq2seq training baseline"
```

---

# Task 10: Wire into repo entrypoints and minimal docs

**Files:**
- Modify: `README.md` (add new section)
- Create: `modules/wheat_risk/__init__.py`

**Steps:**

1. Add `modules/wheat_risk/__init__.py` exporting the public API surface.
2. Add README section with commands:
   - `uv sync --dev`
   - `uv run scripts/export_weekly_risk_rasters.py --limit 4`
   - `uv run scripts/export_wheat_patches.py --samples 50 --dry-run`
   - `uv run scripts/train_wheat_risk_lstm.py --data-index ...`

**Commit:**

```bash
git add modules/wheat_risk/__init__.py README.md
git commit -m "docs: add wheat rust risk pipeline usage"
```

---

# Notes / Constraints

- GEE exports can be slow and quota-limited; all exporters should default to small limits.
- Do not call `ee.Initialize()` at import time; only in scripts.
- Keep unit tests EE-free; only pure-python logic and API surface tests.
- Stage 1 should work with minimal compute; stage 2/3 can be configured but not required to run by default.
