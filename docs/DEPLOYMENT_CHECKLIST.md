# Deployment Checklist

Use this checklist before deploying Ceres AI Pipeline to a shared environment.

## 1. Environment Readiness

- [ ] Confirm target host has Python 3.11+ or container runtime available.
- [ ] Confirm `uv sync --dev --extra ml --extra distributed` completes successfully.
- [ ] Confirm NVIDIA driver / CUDA compatibility if GPU training is required.
- [ ] Confirm disk capacity for `data/`, `runs/`, `reports/`, and temporary exports.
- [ ] Confirm outbound network access to Google OAuth, Earth Engine, and Drive APIs.

## 2. Secrets and Auth

- [ ] Create/rotate Google OAuth client credentials.
- [ ] Register redirect URIs:
  - [ ] `http://127.0.0.1:5055/auth/callback` (local)
  - [ ] production/staging callback URI if using a real host
- [ ] Store OAuth client secret outside git.
- [ ] Verify `client_secret_*.json` and token files remain ignored by git.
- [ ] Set `GOOGLE_OAUTH_CLIENT_SECRET_FILE` or place `client_secret_*.json` at repo root.
- [ ] If deploying publicly, set a strong non-dev `SECRET_KEY`.

## 3. Queue / Background Jobs

- [ ] Use a real Redis instance for deployment (do not use `fakeredis` in shared environments).
- [ ] Confirm RQ worker starts and can import `modules.jobs.tasks`.
- [ ] Confirm job locking works for:
  - [ ] downloader actions
  - [ ] dataset build actions
  - [ ] training actions
  - [ ] evaluation actions
- [ ] Confirm `/api/jobs` returns valid JSON with active queue status.

## 4. WebUI Validation

- [ ] Open `/` and verify landing page renders when logged out.
- [ ] Click `Login with Google` and verify callback succeeds.
- [ ] Confirm authenticated dashboard loads.
- [ ] Confirm scanned dropdowns populate for:
  - [ ] raw dataset directories
  - [ ] raw GeoTIFF preview files
  - [ ] patch NPZ preview files
- [ ] Confirm custom path inputs override scanned selections.

## 5. Pipeline Validation

- [ ] Run downloader preview from WebUI.
- [ ] Run inventory refresh from WebUI.
- [ ] Build at least one dataset level (`L1`) from WebUI.
- [ ] Preview one raw raster and one NPZ patch from WebUI.
- [ ] Execute one dry-run training matrix job.
- [ ] Execute one real training job and confirm artifacts appear in `runs/`.
- [ ] Run evaluation and confirm `best_model.json` / metrics output.

## 6. CLI Validation

- [ ] `uv run scripts/inventory_wheat_dates.py ...`
- [ ] `uv run scripts/build_npz_dataset_from_geotiffs.py ...`
- [ ] `uv run scripts/run_staged_training_matrix.py --dry-run ...`
- [ ] `uv run scripts/eval_staged_training_matrix.py ...`
- [ ] `uv run --dev pytest -q`

## 7. Deployment Packaging

- [ ] Decide runtime mode:
  - [ ] native process supervisor
  - [ ] containerized deployment
- [ ] If containerized, update `Dockerfile` and `docker-compose.yml` to match current architecture.
- [ ] Ensure WebUI process and worker process are both supervised.
- [ ] Ensure Redis is part of the deployment or provided externally.

## 8. Operations

- [ ] Set log retention policy for Gunicorn, worker, and pipeline jobs.
- [ ] Define backup policy for:
  - [ ] raw data manifests
  - [ ] staged datasets metadata
  - [ ] trained model checkpoints
  - [ ] evaluation outputs
- [ ] Document who can rotate OAuth secrets.
- [ ] Document rollback procedure if deployment fails.

## 9. Go/No-Go Gate

Deployment is ready only if all of the following are true:

- [ ] Full test suite passes.
- [ ] OAuth login works end-to-end.
- [ ] Queue status endpoint works end-to-end.
- [ ] One full pipeline run succeeds from the UI.
- [ ] No secrets are tracked in git.
- [ ] Operational owner is identified.
