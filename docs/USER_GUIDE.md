# Ceres AI Pipeline User Guide

This guide explains how to run Ceres AI Pipeline as an end user: start the WebUI, sign in with Google, build datasets, run training, evaluate models, and troubleshoot common issues. The project is maintained by **AgriNova-Orbital**.

## 1. What This Project Does

The project is an end-to-end pipeline for wheat rust risk modeling.

Main capabilities:
- download or refresh source data metadata
- inventory weekly date completeness
- build staged datasets from GeoTIFFs
- run staged training experiments
- evaluate checkpoints and choose the best model
- preview raw rasters and patch samples in the WebUI

The system has two main interfaces:
- **WebUI** for interactive operation
- **CLI scripts** for direct execution and debugging

## 2. Project Layout

- `apps/` - Flask WebUI and static/template assets
- `scripts/` - CLI entrypoints and orchestration scripts
- `modules/` - reusable logic, service layer, models, jobs
- `data/` - raw and staged datasets (ignored by git)
- `runs/` - training/evaluation outputs (ignored by git)
- `docs/` - plans and documentation

## 3. Environment Setup

From the repository root:

```bash
uv sync --dev --extra ml --extra distributed
```

This installs:
- Flask / Gunicorn
- RQ / Redis client
- PyTorch with the configured CUDA profile
- test dependencies

## 4. Starting the WebUI

### Option A: Normal stack (requires local Redis)

```bash
uv run scripts/main.py
```

This starts:
- Gunicorn WebUI on port `5055`
- background RQ worker

### Option B: OAuth test mode without local Redis

Use this for local testing if you do not want to install Redis.

```bash
./start_services_oauth.sh /absolute/path/to/client_secret_xxx.json
```

This mode uses `fakeredis` for local queue/lock testing.

Then open:

```text
http://127.0.0.1:5055
```

## 5. Google OAuth Setup

### Required Google configuration

Your OAuth client must include at least this redirect URI:

```text
http://127.0.0.1:5055/auth/callback
```

You may also add:

```text
http://localhost:5055/auth/callback
```

Do **not** use `0.0.0.0` as an OAuth redirect URI.

### How the app finds your OAuth credentials

The WebUI resolves Google OAuth client config in this order:

1. `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`
2. `GOOGLE_OAUTH_CLIENT_SECRET_FILE`
3. auto-discovery of `client_secret_*.json` in the project root

If you place your client secret file at the repository root, the app can find it automatically.

Ignored by git:
- `client_secret_*.json`
- `oauth_token*.json`

## 6. WebUI Login Flow

When logged out:
- `/` shows a landing page
- you see a **Login with Google** link
- protected routes redirect to `/login`

When logged in:
- the full dashboard is available
- the user OAuth token is stored in session
- background jobs receive the token payload where supported

## 7. Using the WebUI

### 7.1 Data Downloader

Purpose:
- preview or start weekly raster export planning
- refresh inventory information

Main fields:
- `Action`
- `Stage`
- `Start Date`
- `End Date`
- `Limit`
- `EE Project`
- `Drive Folder`
- `Raw Dir` (scanned dropdown)
- `Custom Raw Dir` (manual override)

Behavior:
- if `Custom Raw Dir` is filled, it overrides the dropdown value

### 7.2 Image Preview

There are two preview panels:

1. **Raw GeoTIFF Quicklook**
2. **Patch NPZ Quicklook**

Each preview supports both:
- scanned file dropdown
- manual custom path input

Behavior:
- custom path has higher priority than the scanned dropdown

Scanned sources:
- raw preview: `data/raw/**/*.tif*`
- patch preview: `data/wheat_risk/**/*.npz`, `runs/**/*.npz`

### 7.3 Dataset Build

Purpose:
- build staged datasets for `L1`, `L2`, and `L4`

Important fields:
- `Action` (`build_level`, `build_all`)
- `Level`
- `Raw Dir`
- `Custom Raw Dir`
- `Max Patches`

### 7.4 Training Matrix

Purpose:
- run the staged matrix for training experiments

Key fields:
- `Action`
- `Levels`
- `Steps`

Default workflow:
- dry-run first
- execute training after staged datasets exist

### 7.5 Evaluation

Purpose:
- evaluate staged checkpoints and identify the best model

The evaluation panel also renders a preview plot image.

### 7.6 Run History

The WebUI polls `/api/jobs` and shows queued/running/completed jobs.

If you see an error in the job table, it usually means:
- Redis is unavailable
- old processes are still running
- queue connection mode is inconsistent

## 8. Path Selection Rules

The WebUI now supports **scan + manual override**.

Current supported fields:
- Downloader raw directory
- Dataset Build raw directory
- Raw preview file path
- Patch preview file path

Rule:

```text
custom value > scanned dropdown value
```

This lets you:
- use fast defaults from the project tree
- still point to arbitrary external folders/files when needed

## 9. Data and Output Locations

Typical locations:

- raw input: `data/raw/<dataset_name>/`
- staged datasets: `data/wheat_risk/staged/L1`, `L2`, `L4`
- reports: `reports/`
- training/eval outputs: `runs/`

These are intentionally ignored by git.

## 10. End-to-End Recommended Workflow

### Workflow A: Local test without real Redis

```bash
./start_services_oauth.sh /absolute/path/to/client_secret_xxx.json
```

Then:
1. open `http://127.0.0.1:5055`
2. click **Login with Google**
3. choose a raw directory
4. try preview actions
5. inspect `/api/jobs` through the Run History table

### Workflow B: Real pipeline run

1. inventory source data
2. build staged datasets
3. run staged matrix
4. evaluate checkpoints
5. review best model output

Relevant scripts:

```bash
uv run scripts/inventory_wheat_dates.py ...
uv run scripts/build_npz_dataset_from_geotiffs.py ...
uv run scripts/run_staged_training_matrix.py ...
uv run scripts/eval_staged_training_matrix.py ...
```

## 11. OAuth + Google API Notes

Current support:
- user-level OAuth login works in WebUI
- the user token is passed into background jobs
- `export_weekly_risk_rasters.py` can initialize Earth Engine from the OAuth token environment blob

What this means:
- login success is not just UI-level
- downstream Google-related jobs can use the logged-in user’s credentials

## 12. Troubleshooting

### A. OAuth `invalid_request`

Usually caused by redirect URI mismatch.

Correct value:

```text
http://127.0.0.1:5055/auth/callback
```

### B. `Missing "jwks_uri" in metadata`

This is fixed by using Google OpenID discovery metadata.
If it reappears, verify the OAuth client config in the running branch is current.

### C. Homepage opens but feels stuck

If `127.0.0.1:5055` times out:
- verify you launched with `USE_FAKEREDIS=1` if no real Redis is installed
- kill stale Gunicorn processes
- restart the service cleanly

### D. `/api/jobs` shows UTF-8 decode errors

This was caused by using a text-decoding Redis connection for RQ job payloads.
The current implementation separates:
- text Redis for locks/UI state
- binary-safe Redis for queue payloads

### E. Image preview not working

Check:
- file exists
- file type is supported (`.tif`, `.tiff`, `.npz`)
- custom path is valid if provided

### F. OAuth client secret leaked

If a secret was exposed in chat/logs, rotate it immediately in Google Cloud Console.

## 13. Recommended Daily Commands

### Run full tests

```bash
uv run --dev pytest -q
```

### Start app in OAuth local test mode

```bash
./start_services_oauth.sh /absolute/path/to/client_secret_xxx.json
```

### Start app through the process manager

```bash
uv run scripts/main.py
```

## 14. Related Docs

- `README.md`
- `docs/WHEAT_RISK_PIPELINE.md`
- `docs/architecture_overview.md`
- `docs/plans/2026-02-13-wheat-risk-webui-planning.md`
- `docs/plans/2026-02-14-webui-user-oauth.md`
