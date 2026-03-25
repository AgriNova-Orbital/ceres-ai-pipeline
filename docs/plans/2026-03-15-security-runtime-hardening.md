# Security and Runtime Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the current session/token exposure bugs, fix the queue-to-worker contract mismatches, restrict file preview access, and add a repeatable Chrome smoke-test path for the WebUI.

**Architecture:** Keep browser sessions minimal by storing OAuth tokens server-side in SQLite and keeping only `user_id` and user profile data in the Flask session. Normalize all queued job payloads so the WebUI only sends worker-safe fields and worker tasks convert only concrete filesystem paths. Lock down preview endpoints to a small repo-root allowlist and add a Selenium smoke harness that can run when Chrome and ChromeDriver are available.

**Tech Stack:** Python 3.12, Flask, SQLite, Redis/RQ, pytest, gunicorn, Selenium

---

Baseline note for execution: in a clean worktree, `uv run --dev pytest -q` is already red on queue-related tests in `tests/test_webui_enqueues_jobs.py` and `tests/test_wheat_risk_webui.py`. Treat those failures as part of this plan rather than unrelated regressions.

### Task 1: Persist OAuth Tokens Server-Side

**Files:**
- Modify: `modules/persistence/sqlite_store.py`
- Modify: `tests/test_sqlite_store.py`

**Step 1: Write the failing test**

```python
def test_sqlite_store_persists_user_oauth_token(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )

    token = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "scope": "openid email profile",
    }

    store.save_user_oauth_token(user_id=user["id"], token=token)
    assert store.get_user_oauth_token(user["id"]) == token
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_sqlite_store.py::test_sqlite_store_persists_user_oauth_token -q`
Expected: FAIL with `AttributeError` because the new token persistence methods do not exist yet.

**Step 3: Write minimal implementation**

Add a new SQLite table and helper methods in `modules/persistence/sqlite_store.py`.

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS user_oauth_tokens (
        user_id TEXT PRIMARY KEY,
        token_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """
)

def save_user_oauth_token(self, *, user_id: str, token: dict[str, Any]) -> None:
    payload = json.dumps(token, sort_keys=True)
    ...

def get_user_oauth_token(self, user_id: str) -> dict[str, Any] | None:
    ...

def delete_user_oauth_token(self, user_id: str) -> None:
    ...
```

Use JSON text storage, preserve the original token payload, and keep method names exact so later tasks can call them directly.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_sqlite_store.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add modules/persistence/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: persist oauth tokens in sqlite"
```

### Task 2: Harden Session Secret and Remove Client-Side Token Storage

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `docker-compose.yml`
- Modify: `start_local_dev.sh`
- Create: `tests/test_start_local_dev_script.py`
- Modify: `tests/test_multi_user_oauth.py`
- Modify: `tests/test_webui_locking.py`
- Modify: `tests/test_webui_enqueues_jobs.py`
- Modify: `tests/test_wheat_risk_webui.py`

**Step 1: Write the failing tests**

Add two assertions:

```python
def test_create_app_uses_secret_key_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("WEBUI_SECRET_KEY", "test-secret")
    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    assert app.config["SECRET_KEY"] == "test-secret"


def test_auth_callback_stores_token_server_side_not_in_session(client, monkeypatch):
    ...
    client.get("/auth/callback", follow_redirects=False)
    with client.session_transaction() as sess:
        assert sess["user_id"]
        assert "google_token" not in sess
```

Update the helper login setup in WebUI tests so it saves OAuth tokens through `app.config["SQLITE_STORE"].save_user_oauth_token(...)` instead of writing `sess["google_token"]` directly.

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_multi_user_oauth.py tests/test_sqlite_store.py::test_create_app_bootstraps_sqlite_store_from_app_db_path -q`
Expected: FAIL because `create_app()` still hardcodes the development secret and `/auth/callback` still writes `google_token` into the browser session.

**Step 3: Write minimal implementation**

In `apps/wheat_risk_webui.py`:

```python
secret_key = os.environ.get("WEBUI_SECRET_KEY")
if not secret_key:
    raise RuntimeError("WEBUI_SECRET_KEY is required")
app.config["SECRET_KEY"] = secret_key
```

Change `/auth/callback` to persist the token with SQLite and keep only safe session fields:

```python
token = get_oauth_client(oauth).authorize_access_token()
...
local_user = sqlite_store.get_or_create_user(...)
sqlite_store.save_user_oauth_token(user_id=local_user["id"], token=token)
session["user_id"] = local_user["id"]
session["user"] = user
```

Update `docker-compose.yml` and `start_local_dev.sh` so the WebUI always exports `WEBUI_SECRET_KEY` before starting Flask or gunicorn. Keep the value outside source control for real deployments, but seed a deterministic test/local-dev value inside the script so local startup remains easy.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_multi_user_oauth.py tests/test_webui_locking.py tests/test_webui_enqueues_jobs.py tests/test_wheat_risk_webui.py tests/test_start_local_dev_script.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py docker-compose.yml start_local_dev.sh tests/test_start_local_dev_script.py tests/test_multi_user_oauth.py tests/test_webui_locking.py tests/test_webui_enqueues_jobs.py tests/test_wheat_risk_webui.py
git commit -m "fix: keep oauth tokens out of browser sessions"
```

### Task 3: Fix Downloader Queue Payloads and Worker Contracts

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `modules/jobs/tasks.py`
- Modify: `tests/test_webui_enqueues_jobs.py`
- Modify: `tests/test_wheat_risk_webui.py`
- Modify: `tests/test_job_worker.py`

**Step 1: Write the failing tests**

Add worker-level and route-level coverage:

```python
def test_task_run_inventory_uses_start_date_str(tmp_path: Path):
    from modules.jobs.tasks import task_run_inventory
    result = task_run_inventory(
        {
            "input_dir": str(tmp_path),
            "output_dir": str(tmp_path),
            "start_date_str": "2025-01-01",
            "cadence_days": 7,
        }
    )
    assert isinstance(result, dict)


def test_downloader_preview_enqueue_uses_user_backed_worker_task(...):
    ...
    client.post("/run/downloader", data={"action": "preview_export"})
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_script_for_user"
    assert "oauth_token" not in kwargs["args"][0]
```

Update the existing inventory enqueue tests to expect `start_date_str`, not `start_date`.

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py tests/test_wheat_risk_webui.py tests/test_job_worker.py -q`
Expected: FAIL because the route still enqueues raw token data and `task_run_inventory()` still receives the wrong keyword shape.

**Step 3: Write minimal implementation**

Create a dedicated worker task in `modules/jobs/tasks.py` that resolves OAuth tokens server-side when needed.

```python
def task_run_script_for_user(kwargs: dict[str, Any]) -> dict[str, Any]:
    user_id = kwargs.pop("user_id", None)
    env_overrides = dict(kwargs.pop("env_overrides", {}))
    if user_id:
        store = SQLiteStore(Path(os.environ["APP_DB_PATH"]))
        token = store.get_user_oauth_token(user_id)
        if token:
            env_overrides["GOOGLE_OAUTH_TOKEN_JSON"] = json.dumps(token)
    return run_script(env_overrides=env_overrides, **kwargs)
```

In `apps/wheat_risk_webui.py`:

- enqueue preview-export jobs via `modules.jobs.tasks.task_run_script_for_user`
- pass `user_id`, `cmd`, and `cwd`
- remove `oauth_token` from all queue payloads
- rename the inventory field to `start_date_str`

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py tests/test_wheat_risk_webui.py tests/test_job_worker.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py modules/jobs/tasks.py tests/test_webui_enqueues_jobs.py tests/test_wheat_risk_webui.py tests/test_job_worker.py
git commit -m "fix: align downloader jobs with worker contracts"
```

### Task 4: Fix Training and Evaluation Job Payload Normalization

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `modules/jobs/tasks.py`
- Modify: `tests/test_webui_enqueues_jobs.py`
- Modify: `tests/test_job_worker.py`

**Step 1: Write the failing tests**

Add one route-level test and one worker-level test:

```python
def test_train_execute_enqueues_complete_matrix_kwargs(...):
    ...
    client.post("/run/train", data={"action": "execute_train"})
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["train_script"] == "scripts/train_wheat_risk_lstm.py"
    assert job_kwargs["index_csv_template"] == "./data/wheat_risk/staged/L{level}/index.csv"
    assert job_kwargs["root_dir_template"] == "./data/wheat_risk/staged/L{level}"
    assert job_kwargs["epochs"] == 10


def test_task_run_matrix_leaves_templates_as_strings(monkeypatch):
    seen = {}

    def fake_run_matrix(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(
        "modules.services.training_matrix_service.run_matrix",
        fake_run_matrix,
    )
    ...
    assert seen["index_csv_template"] == "./data/wheat_risk/staged/L{level}/index.csv"
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py tests/test_job_worker.py -q`
Expected: FAIL because the route still points to `scripts/train_staged_model.py` and does not send the full required keyword set.

**Step 3: Write minimal implementation**

In `apps/wheat_risk_webui.py`, always enqueue a complete `run_matrix()` payload:

```python
job_kwargs = {
    "levels": [int(x) for x in level_list],
    "steps": steps_list,
    "base_patch": 64,
    "dry_run": action == "dry_run",
    "execute_train": action != "dry_run",
    "runs_dir": "runs",
    "index_csv": None,
    "index_csv_template": "./data/wheat_risk/staged/L{level}/index.csv",
    "root_dir": None,
    "root_dir_template": "./data/wheat_risk/staged/L{level}",
    "train_script": "scripts/train_wheat_risk_lstm.py",
    "epochs": 10,
    "batch_size": 8,
    "lr": 1e-3,
    "embed_dim": 64,
    "hidden_dim": 128,
    "num_workers": 0,
    "device": "cuda",
    "seed_base": 42,
}
```

In `modules/jobs/tasks.py`, convert only concrete path fields (`runs_dir`, `train_script`, `index_csv`, `root_dir`) and leave template strings untouched.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_webui_enqueues_jobs.py tests/test_job_worker.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py modules/jobs/tasks.py tests/test_webui_enqueues_jobs.py tests/test_job_worker.py
git commit -m "fix: normalize training job payloads"
```

### Task 5: Restrict Preview Endpoints to Repo-Controlled Paths

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `tests/test_wheat_risk_webui.py`

**Step 1: Write the failing tests**

Add explicit allowlist coverage:

```python
def test_patch_preview_rejects_paths_outside_repo_allowlist(tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    outside = Path("/tmp/outside-preview.npz")
    np.savez_compressed(outside, X=np.zeros((1, 3, 4, 4), dtype=np.float32))

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client)

    resp = client.get(f"/api/preview/patch?path={outside}&t=0")
    assert resp.status_code == 403
```

Also add a happy-path test proving `data/raw/...` or `data/wheat_risk/...` still returns `200`.

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_wheat_risk_webui.py -q`
Expected: FAIL because preview endpoints currently accept any readable `.tif` or `.npz` path.

**Step 3: Write minimal implementation**

Add a shared path guard in `apps/wheat_risk_webui.py`.

```python
def _resolve_allowed_preview_path(repo_root: Path, raw_path: str) -> Path:
    allowed_roots = [
        (repo_root / "data").resolve(),
        (repo_root / "reports").resolve(),
        (repo_root / "runs").resolve(),
    ]
    path = Path(raw_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    if not any(path == root or root in path.parents for root in allowed_roots):
        raise PermissionError(raw_path)
    return path
```

Use this helper from both `/api/preview/raw` and `/api/preview/patch`, returning `403` on `PermissionError`.

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_wheat_risk_webui.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py tests/test_wheat_risk_webui.py
git commit -m "fix: limit preview endpoints to repo data"
```

### Task 6: Add Chrome Smoke-Test Support

**Files:**
- Modify: `pyproject.toml`
- Create: `modules/testing/browser_env.py`
- Create: `tests/test_browser_env.py`
- Create: `tests/e2e/test_webui_chrome_smoke.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Create a deterministic helper test first:

```python
def test_resolve_chrome_binaries_prefers_env(monkeypatch):
    from modules.testing.browser_env import resolve_chrome_binaries

    monkeypatch.setenv("CHROME_BIN", "/usr/bin/google-chrome")
    monkeypatch.setenv("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    assert resolve_chrome_binaries() == {
        "chrome": "/usr/bin/google-chrome",
        "chromedriver": "/usr/bin/chromedriver",
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_browser_env.py -q`
Expected: FAIL with `ModuleNotFoundError` because the helper does not exist yet.

**Step 3: Write minimal implementation**

Add `selenium` to the dev dependency group in `pyproject.toml`, then implement `resolve_chrome_binaries()` in `modules/testing/browser_env.py`. Use that helper from `tests/e2e/test_webui_chrome_smoke.py` to:

- skip with a clear message if Chrome or ChromeDriver is unavailable
- start the app with gunicorn on a test port
- open `/setup` in headless Chrome
- assert the page title contains `Ceres AI Pipeline Setup`
- assert the initial wizard content is visible

**Step 4: Run tests to verify they pass**

Run: `uv run --dev pytest tests/test_browser_env.py -q`
Expected: PASS.

When Chrome is installed, also run:

Run: `uv run --dev pytest tests/e2e/test_webui_chrome_smoke.py -q`
Expected: PASS in environments with both `google-chrome` (or `chromium`) and `chromedriver`; SKIP otherwise with an actionable message.

**Step 5: Commit**

```bash
git add pyproject.toml modules/testing/browser_env.py tests/test_browser_env.py tests/e2e/test_webui_chrome_smoke.py README.md
git commit -m "test: add chrome smoke coverage for webui"
```

### Task 7: Final Verification

**Files:**
- No source changes expected

**Step 1: Run the full Python test suite**

Run: `uv run --dev pytest -q`
Expected: PASS.

**Step 2: Run the browser smoke test if binaries are installed**

Run: `uv run --dev pytest tests/e2e/test_webui_chrome_smoke.py -q`
Expected: PASS or a single explicit SKIP message if Chrome is unavailable.

**Step 3: Run a live HTTP smoke test**

Run: `APP_DB_PATH=/tmp/actinspace_smoke_app.db WEBUI_SECRET_KEY=test-secret uv run gunicorn --bind 127.0.0.1:5065 --workers 1 'apps.wheat_risk_webui:create_app()'`
Expected: gunicorn starts cleanly.

In another shell:

Run: `curl -I -s http://127.0.0.1:5065/`
Expected: `302 FOUND` with `Location: /setup` on a fresh database.

**Step 4: Request code review**

Use `superpowers:requesting-code-review` before merge or PR creation.
