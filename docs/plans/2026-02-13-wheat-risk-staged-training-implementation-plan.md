# Wheat Risk 2D Staged Training Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reproducible pipeline that inventories weekly-date completeness and executes nested-loop 2D staged training (image granularity outer loop, sample size inner loop).

**Architecture:** Add pure planning/inventory functions in `modules/wheat_risk/` and keep `scripts/` as thin orchestration CLIs. Build date inventory reports first, then run matrix cells in strict nested order and persist per-cell artifacts plus a global summary. Keep MVP dry-run-first so command generation and order are verifiable before expensive training.

**Tech Stack:** Python 3.12, argparse, csv/json, pathlib, pytest, existing `scripts/build_npz_dataset_from_geotiffs.py`, existing `scripts/train_wheat_risk_lstm.py`.

---

### Task 1: Data Inventory Core Functions

**Files:**
- Create: `modules/wheat_risk/data_inventory.py`
- Test: `tests/test_data_inventory.py`

**Step 1: Write the failing tests**

```python
def test_inventory_reports_missing_7day_nodes():
    observed = [date(2025, 1, 1), date(2025, 1, 15)]
    inv = compute_inventory(observed, cadence_days=7)
    assert inv.missing_dates == [date(2025, 1, 8)]
```

```python
def test_inventory_reports_range_and_total_days():
    observed = [date(2025, 1, 1), date(2025, 1, 22)]
    inv = compute_inventory(observed, cadence_days=7)
    assert inv.earliest_date.isoformat() == "2025-01-01"
    assert inv.latest_date.isoformat() == "2025-01-22"
    assert inv.total_days == 22
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_data_inventory.py -q`
Expected: FAIL with missing module/function errors.

**Step 3: Write minimal implementation**

Implement dataclass + function:

```python
@dataclass(frozen=True)
class InventoryResult:
    earliest_date: date
    latest_date: date
    total_days: int
    expected_nodes: int
    observed_nodes: int
    missing_dates: list[date]
```

```python
def compute_inventory(observed_dates: Sequence[date], cadence_days: int = 7) -> InventoryResult:
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_data_inventory.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/wheat_risk/data_inventory.py tests/test_data_inventory.py
git commit -m "feat: add weekly date inventory core"
```

### Task 2: Inventory CLI Report Generator

**Files:**
- Create: `scripts/inventory_wheat_dates.py`
- Test: `tests/test_inventory_wheat_dates_cli.py`

**Step 1: Write the failing test**

```python
def test_inventory_cli_writes_json_and_missing_csv(tmp_path: Path):
    ...
    assert (tmp_path / "data_inventory.json").exists()
    assert (tmp_path / "missing_dates.csv").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_inventory_wheat_dates_cli.py -q`
Expected: FAIL because script does not exist.

**Step 3: Write minimal implementation**

CLI should:
- scan GeoTIFF names with existing temporal parser
- resolve observed dates (explicit date > week code > index+anchor)
- call `compute_inventory`
- write `data_inventory.json` and `missing_dates.csv`

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_inventory_wheat_dates_cli.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/inventory_wheat_dates.py tests/test_inventory_wheat_dates_cli.py
git commit -m "feat: add inventory CLI with missing-date reports"
```

### Task 3: 2D Matrix Planning + Nested Order

**Files:**
- Create: `modules/wheat_risk/staged_training.py`
- Test: `tests/test_staged_training_plan.py`

**Step 1: Write the failing tests**

```python
def test_nested_loop_order_level_outer_step_inner():
    plan = build_matrix(levels=[1,2,4], steps=[100,500,2000])
    assert [(c.level, c.step) for c in plan] == [
        (1,100),(1,500),(1,2000),
        (2,100),(2,500),(2,2000),
        (4,100),(4,500),(4,2000),
    ]
```

```python
def test_patch_size_mapping_from_base_patch():
    assert map_patch_size(base_patch=64, level_split=4) == 16
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_staged_training_plan.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Add dataclass + helpers:

```python
@dataclass(frozen=True)
class MatrixCell:
    level: int
    step: int
    patch_size: int
```

```python
def build_matrix(levels: Sequence[int], steps: Sequence[int], base_patch: int = 64) -> list[MatrixCell]:
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_staged_training_plan.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/wheat_risk/staged_training.py tests/test_staged_training_plan.py
git commit -m "feat: add nested-loop staged training matrix planner"
```

### Task 4: Matrix Runner CLI (Dry-Run First)

**Files:**
- Create: `scripts/run_staged_training_matrix.py`
- Test: `tests/test_run_staged_training_matrix_cli.py`

**Step 1: Write the failing test**

```python
def test_runner_dry_run_prints_nested_order(tmp_path: Path):
    ...
    assert "L1-S100" in proc.stdout
    assert proc.stdout.index("L1-S2000") < proc.stdout.index("L2-S100")
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_run_staged_training_matrix_cli.py -q`
Expected: FAIL because script is missing.

**Step 3: Write minimal implementation**

CLI behavior:
- default dry-run
- generate matrix cells in nested order
- when `--run`, execute:
  - dataset build per level
  - subset creation per step
  - train command per cell
- write `runs/staged/summary.csv`

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_run_staged_training_matrix_cli.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/run_staged_training_matrix.py tests/test_run_staged_training_matrix_cli.py
git commit -m "feat: add staged training matrix runner CLI"
```

### Task 5: Pipeline Validation + Docs

**Files:**
- Modify: `docs/WHEAT_RISK_PIPELINE.md`

**Step 1: Write/adjust failing integration expectation**

Document commands and expected outputs for:
- inventory report generation
- matrix dry-run

**Step 2: Run validation commands**

Run:

```bash
uv run --dev pytest tests/test_data_inventory.py tests/test_inventory_wheat_dates_cli.py tests/test_staged_training_plan.py tests/test_run_staged_training_matrix_cli.py -q
uv run scripts/inventory_wheat_dates.py --input-dir data/raw/france_2025_weekly --cadence-days 7 --start-date 2025-01-01 --output-dir reports
uv run scripts/run_staged_training_matrix.py --dry-run
```

Expected: all tests pass and dry-run prints nested order.

**Step 3: Update docs**

Add usage snippets and artifact paths in `docs/WHEAT_RISK_PIPELINE.md`.

**Step 4: Commit**

```bash
git add docs/WHEAT_RISK_PIPELINE.md
git commit -m "docs: add inventory and staged matrix workflow"
```
