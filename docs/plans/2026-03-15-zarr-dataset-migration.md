# Zarr Dataset Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the dataset building and loading pipeline to write and read from a single Zarr store (or HDF5-like structure using `zarr`) instead of thousands of individual `.npz` files. This allows for a single file download, solves UI visibility issues, and prepares the platform for multi-year scaling.

**Architecture:** 
1. Introduce `zarr` to the dependencies.
2. Update `dataset_service.py` to initialize a Zarr group at the output directory. It will pre-allocate arrays `X` with shape `(N, T, C, H, W)` and `y` with shape `(N, T)`, chunked along the sample dimension `N`.
3. The parallel workers will extract patches and write them directly to their assigned indices in the Zarr arrays.
4. Update `dataset.py` (the PyTorch `Dataset`) to read directly from the Zarr arrays instead of reading an `index.csv` and loading individual `.npz` files.
5. Update the WebUI preview endpoints to read from the Zarr store.

**Tech Stack:** Python 3.12, Zarr, PyTorch, NumPy.

---

### Task 1: Add Zarr Dependency

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_zarr_dependency.py`

**Step 1: Write the failing test**

```python
# tests/test_zarr_dependency.py
def test_zarr_is_importable():
    import zarr
    assert zarr.__version__
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_zarr_dependency.py -q`
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

Add `zarr>=2.17.0` to `dependencies` in `pyproject.toml`.

**Step 4: Run test to verify it passes**

Run: `uv sync --dev --extra ml --extra distributed`
Run: `uv run --dev pytest tests/test_zarr_dependency.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/test_zarr_dependency.py
git commit -m "feat(deps): add zarr for unified dataset storage"
```

### Task 2: Refactor Dataset Build Service to Write Zarr

**Files:**
- Modify: `modules/services/dataset_service.py`
- Modify: `tests/services/test_dataset_service.py`

**Step 1: Write the failing test**

```python
# tests/services/test_dataset_service.py (update existing test)
def test_dataset_service_creates_zarr_store(tmp_path):
    # ... existing setup ...
    result = run_build(...)
    
    import zarr
    store = zarr.open(str(output_dir / "dataset.zarr"), mode='r')
    assert "X" in store
    assert "y" in store
    assert store["X"].shape[0] > 0
    assert store["y"].shape[0] == store["X"].shape[0]
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/services/test_dataset_service.py -q`
Expected: FAIL (currently writes `index.csv` and `.npz` files).

**Step 3: Write minimal implementation**

In `dataset_service.py` (`run_build`):
- Instead of creating an `examples` dir and writing `index.csv`, create a `zarr.open_group(..., mode='w')`.
- Calculate total number of valid patches (this is tricky because we filter NaNs. We might need a two-pass approach or append to the Zarr arrays). 
- *Design choice for simplicity*: Let the master process orchestrate. Since workers currently return valid patches, the master process can create the Zarr arrays with `shape=(0, T, C, H, W)` and `chunks=(100, T, C, H, W)` and `append()` the results from the workers.
- The worker `_build_patch_worker` currently returns a path. It needs to return the actual `X` and `y` numpy arrays (or None if invalid).
- In the master loop:
  ```python
  import zarr
  z_group = zarr.open_group(str(output_dir / "dataset.zarr"), mode='w')
  # Initialize empty arrays with chunks
  z_X = z_group.empty('X', shape=(0, T, C, patch_size, patch_size), chunks=(100, T, C, patch_size, patch_size), dtype='float32')
  z_y = z_group.empty('y', shape=(0, T), chunks=(100, T), dtype='float32')
  
  # ... inside worker loop result collection ...
  if result is not None:
      X_patch, y_patch = result
      z_X.append(np.expand_dims(X_patch, 0))
      z_y.append(np.expand_dims(y_patch, 0))
  ```

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/services/test_dataset_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/services/dataset_service.py tests/services/test_dataset_service.py
git commit -m "refactor(data): switch dataset builder to write Zarr store instead of individual NPZ files"
```

### Task 3: Refactor PyTorch Dataset to Read Zarr

**Files:**
- Modify: `modules/wheat_risk/dataset.py`
- Create: `tests/test_zarr_dataset_loader.py`

**Step 1: Write the failing test**

```python
# tests/test_zarr_dataset_loader.py
import pytest
from pathlib import Path
import numpy as np

def test_wheat_risk_zarr_dataset(tmp_path: Path):
    import zarr
    from modules.wheat_risk.dataset import WheatRiskZarrDataset
    
    z_path = tmp_path / "dataset.zarr"
    z = zarr.open_group(str(z_path), mode='w')
    z.array('X', data=np.random.rand(10, 5, 3, 16, 16).astype(np.float32))
    z.array('y', data=np.random.rand(10, 5).astype(np.float32))
    
    ds = WheatRiskZarrDataset(zarr_path=z_path)
    assert len(ds) == 10
    x, y = ds[0]
    assert x.shape == (5, 3, 16, 16)
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_zarr_dataset_loader.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Rewrite the Dataset class in `modules/wheat_risk/dataset.py`:

```python
import torch
from torch.utils.data import Dataset
import zarr
from pathlib import Path

class WheatRiskZarrDataset(Dataset):
    def __init__(self, zarr_path: Path | str):
        self.zarr_path = str(zarr_path)
        # Don't open the store in __init__ if using num_workers > 0 in DataLoader, 
        # open it lazily or per-worker to avoid pickle issues.
        self.store = None
        
        # Read length metadata quickly
        z = zarr.open(self.zarr_path, mode='r')
        self.length = z['X'].shape[0]

    def _init_store(self):
        if self.store is None:
            self.store = zarr.open(self.zarr_path, mode='r')

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        self._init_store()
        # Read a single slice
        X = self.store['X'][idx]
        y = self.store['y'][idx]
        return X, y
```
*(Also update `scripts/train_wheat_risk_lstm.py` and `modules/services/evaluation_service.py` to use `WheatRiskZarrDataset` and pass the `zarr_path` instead of `index_csv`)*.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_zarr_dataset_loader.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/wheat_risk/dataset.py scripts/train_wheat_risk_lstm.py modules/services/evaluation_service.py tests/
git commit -m "refactor(train): load training data from Zarr store"
```

### Task 4: Update Matrix Services & WebUI for Zarr

**Files:**
- Modify: `modules/services/training_matrix_service.py`
- Modify: `apps/wheat_risk_webui.py`
- Modify: `apps/templates/wheat_risk_webui.html`

**Step 1: Update Matrix Service logic**

Modify `training_matrix_service.py` to pass the path to `dataset.zarr` to the training script instead of `index.csv`.
If the training still requires a "subset" for smaller steps (Step A=100), we can't easily write a new Zarr store per step. Instead, we can pass an `indices` list or simply use `torch.utils.data.Subset` in the training script based on a generated random index list file. 
*Simplification:* The training script can accept a `--subset-size N` argument. The Dataset or DataLoader can limit itself to the first `N` elements (or random N with a seed).

**Step 2: Update WebUI Previews**

In `apps/wheat_risk_webui.py`, update `get_scanned_patch_npz_paths` to find `.zarr` directories instead.
Update `/api/preview/patch` to read from the Zarr store:
```python
    z = zarr.open(path, mode='r')
    x = z['X'][t] # get one patch
    # ... downsample and render
```
Update the UI template to say "Zarr Preview" instead of "NPZ Quicklook".

**Step 3: Run integration tests**

Ensure everything links up correctly.

**Step 4: Commit**

```bash
git add modules/services/training_matrix_service.py apps/wheat_risk_webui.py apps/templates/wheat_risk_webui.html
git commit -m "feat(webui): support zarr stores for previews and staged matrix"
```
