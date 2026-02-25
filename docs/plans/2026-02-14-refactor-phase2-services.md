# Project Refactoring Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the core business logic from the remaining operational scripts into reusable modules under `modules/services/`, enabling the WebUI job runner to call these services directly instead of spawning subprocesses, and improving testability.

**Architecture:** We will create a `modules/services/` layer. Scripts like `build_npz_dataset_from_geotiffs.py`, `run_staged_training_matrix.py`, and `eval_staged_training_matrix.py` will have their logic moved into `dataset_service.py`, `training_matrix_service.py`, and `evaluation_service.py` respectively. The scripts will become thin CLI wrappers around these services. Finally, the WebUI RQ worker tasks will be updated to call these services instead of running shell commands.

**Tech Stack:** Python 3.12, pytest.

---

### Task 1: Refactor Dataset Build Service

**Files:**
- Create: `modules/services/dataset_service.py`
- Modify: `scripts/build_npz_dataset_from_geotiffs.py`
- Modify: `tests/test_build_npz_workers.py` (and related build tests to use service)
- Create: `tests/services/test_dataset_service.py`

**Step 1: Write the failing test**

```python
# tests/services/test_dataset_service.py
import pytest
from pathlib import Path

def test_dataset_service_has_run_build_function():
    from modules.services.dataset_service import run_build
    assert callable(run_build)
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/services/test_dataset_service.py -q`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

**Step 3: Write minimal implementation**

Move the core logic from `main()` in `scripts/build_npz_dataset_from_geotiffs.py` to `run_build()` in `modules/services/dataset_service.py`. Keep the arg parsing in the script. Update the script to call `run_build()`.
Ensure the helper functions (`_build_patch_worker`, `_init_patch_worker`, etc.) are also moved or appropriately scoped so the service can use them.
*(Note: This involves copying a significant block of code. Ensure imports in both files are correct).*

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_build_npz_missing_weeks.py tests/test_build_npz_workers.py tests/test_build_npz_dates.py tests/services/test_dataset_service.py -q`
Expected: PASS. All original functionality must remain intact.

**Step 5: Commit**

```bash
git add modules/services/dataset_service.py scripts/build_npz_dataset_from_geotiffs.py tests/
git commit -m "refactor: extract dataset build logic to dataset_service"
```

### Task 2: Refactor Staged Matrix Runner Service

**Files:**
- Create: `modules/services/training_matrix_service.py`
- Modify: `scripts/run_staged_training_matrix.py`
- Modify: `tests/test_run_staged_training_matrix_cli.py`
- Create: `tests/services/test_training_matrix_service.py`

**Step 1: Write the failing test**

```python
# tests/services/test_training_matrix_service.py
def test_training_matrix_service_has_run_matrix_function():
    from modules.services.training_matrix_service import run_matrix
    assert callable(run_matrix)
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/services/test_training_matrix_service.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Move the core execution loop from `main()` in `scripts/run_staged_training_matrix.py` into `run_matrix(...)` in `modules/services/training_matrix_service.py`.
The CLI script should parse arguments and then pass them as kwargs to `run_matrix()`.
Update tests if they were importing internal functions from the script.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_run_staged_training_matrix_cli.py tests/test_staged_training_plan.py tests/services/test_training_matrix_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/services/training_matrix_service.py scripts/run_staged_training_matrix.py tests/
git commit -m "refactor: extract training matrix execution to service"
```

### Task 3: Refactor Evaluation Service

**Files:**
- Create: `modules/services/evaluation_service.py`
- Modify: `scripts/eval_staged_training_matrix.py`
- Create: `tests/services/test_evaluation_service.py`

**Step 1: Write the failing test**

```python
# tests/services/test_evaluation_service.py
def test_evaluation_service_has_run_evaluation_function():
    from modules.services.evaluation_service import run_evaluation
    assert callable(run_evaluation)
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/services/test_evaluation_service.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Move `_evaluate_checkpoint` and the main evaluation loop from `scripts/eval_staged_training_matrix.py` to `modules/services/evaluation_service.py` as `run_evaluation()`.
The CLI script parses arguments and calls the service.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/services/test_evaluation_service.py -q` (and any related existing tests).
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/services/evaluation_service.py scripts/eval_staged_training_matrix.py tests/
git commit -m "refactor: extract evaluation logic to service"
```

### Task 4: Integrate Services into WebUI Job Tasks

**Files:**
- Modify: `modules/jobs/tasks.py`
- Modify: `apps/wheat_risk_webui.py`

**Step 1: Write the failing test**

*(No new test file, we will update the existing `tasks.py` and rely on its successful execution for integration testing).*
Modify `tests/test_webui_enqueues_jobs.py` to assert that it queues the new specific task functions instead of `run_script`.

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

In `modules/jobs/tasks.py`, add new task functions that call the services directly:
- `task_build_dataset(kwargs...)` -> calls `dataset_service.run_build`
- `task_run_matrix(kwargs...)` -> calls `training_matrix_service.run_matrix`
- `task_run_eval(kwargs...)` -> calls `evaluation_service.run_evaluation`
- `task_run_inventory(kwargs...)` -> calls `inventory_service.run_inventory`

Update `apps/wheat_risk_webui.py`'s route handlers to enqueue these specific tasks with Python kwargs, rather than constructing a list of strings for `subprocess.run`.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/jobs/tasks.py apps/wheat_risk_webui.py tests/test_webui_enqueues_jobs.py
git commit -m "feat: integrate webui job queue with core services"
```

### Task 5: WebUI UX Enhancements (MVP Multi-User Queue)

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `apps/templates/wheat_risk_webui.html`

**Step 1: Write the failing test**

*(This is primarily a UI/state change, testing via unit tests is complex. We will verify manually via the UI, but we can add a basic test for the queue status endpoint).*

```python
# tests/test_webui_enqueues_jobs.py (append)
def test_job_status_endpoint_returns_json(monkeypatch):
    from apps.wheat_risk_webui import create_app
    app = create_app()
    client = app.test_client()
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json, list)
```

**Step 2: Run test to verify it fails/passes**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py -q`

**Step 3: Write minimal implementation**

1.  In `wheat_risk_webui.py`, enhance the `/api/jobs` endpoint to query the actual RQ queue for job status (queued, started, finished, failed) instead of relying solely on the mock `app.config["JOB_HISTORY"]`.
2.  In `wheat_risk_webui.html`, update the "Run History" table to dynamically fetch from `/api/jobs` using JavaScript `fetch` on an interval (e.g., every 5 seconds) to show real-time queue status to all connected users.
3.  Add basic UI locks (disable "Run" buttons) if a job of the same type is currently 'started' or 'queued'.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest -q` to ensure no regressions.
Manual verification required for UI updates.

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py apps/templates/wheat_risk_webui.html
git commit -m "feat: enhance webui with real-time rq job status polling"
```