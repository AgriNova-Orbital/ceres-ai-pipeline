# Change Log — 2026-04-10 (UV + Docker Profiles)

## Scope

- Standardize project workflow around `uv`
- Split container runtime into `dev`, `beta`, `release`
- Update operational docs to match new deployment/testing commands

## Changed Files

- `Dockerfile`
  - Refactored to multi-stage targets: `dev`, `beta`, `release`
  - Uses `uv sync --frozen --no-install-project` for dependency layers
  - Separate runtime defaults for log level and Flask environment per target

- `docker-compose.yml`
  - Added profile-based stacks: `web-*`, `worker-*`, `frontend-*`
  - Kept shared `redis` service
  - Defined profile-specific ports:
    - dev: web `5055`, frontend `3002`
    - beta: web `5155`, frontend `3102`
    - release: web `5255`, frontend `3202`

- `Makefile`
  - Added `uv-sync` and `uv-test`
  - Added profile helpers: `dev-up/down/logs`, `beta-up/down/logs`, `release-up/down/logs`
  - Mapped `up/down/logs` defaults to `dev` profile

- `README.md`
  - Updated container section to profile-based startup commands
  - Added Makefile shortcuts and profile port map

- `docs/DEPLOYMENT_CHECKLIST.md`
  - Added profile runbook for `dev`, `beta`, `release`

- `docs/USER_GUIDE.md`
  - Added Compose profile startup option
  - Clarified `fakeredis` is only for OAuth local test script mode

- `docs/ARCHITECTURE_V1.md`
  - Updated Docker operation examples to profile-based commands

- `docs/SPRINT_W1_W2_PLAN.md`
  - Updated compose command examples to `--profile dev`

- `modules/ee_import.py`
- `modules/merge_geotiffs.py`
- `modules/services/dataset_service.py`
- `modules/wheat_risk/features.py`
- `modules/wheat_risk/labels.py`
- `modules/wheat_risk/masks.py`
- `modules/drive_oauth.py`
  - Updated install guidance strings to prefer `uv add` / `uv sync` phrasing

## Verification Performed

- `docker compose config`
- `docker compose --profile dev config`
- `docker compose --profile beta config`
- `docker compose --profile release config`
- `uv run --dev pytest tests/test_start_local_dev_script.py -q`
- `uv run --dev pytest tests/test_drive_oauth_import_error.py -q`
- `uv run --dev pytest tests/test_scripts_run_from_filesystem.py::test_export_weekly_risk_rasters_dry_run_runs_from_file_path -q`
- `uv run --dev pytest tests/test_ee_init_requires_project.py -q`
