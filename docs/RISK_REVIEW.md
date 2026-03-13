# Current Risk Review

This document summarizes the main technical and operational risks in the current state of Ceres AI Pipeline.

## 1. OAuth / Auth Risks

### Risk: OAuth client secret exposure
- **Status:** High
- **Why it matters:** If the client secret is leaked, an attacker can impersonate the app in OAuth flows.
- **Current mitigation:** `client_secret_*.json` is ignored by git.
- **Next action:** Rotate any secret that has ever been pasted into chat/logs. Move secrets to a dedicated secret store for shared deployments.

### Risk: Redirect URI mismatch
- **Status:** Medium
- **Why it matters:** Google login fails with `invalid_request` if callback URIs drift.
- **Current mitigation:** app now reads redirect URI from config/client secret and supports explicit override.
- **Next action:** keep a single canonical callback URI per environment and document it.

## 2. Queue / Worker Risks

### Risk: No real Redis in local test mode
- **Status:** Medium
- **Why it matters:** `fakeredis` is useful for local testing but is not a substitute for real multi-process queue durability.
- **Current mitigation:** local test mode exists; production guidance recommends real Redis.
- **Next action:** validate full background execution path against real Redis before team deployment.

### Risk: Lock semantics are coarse
- **Status:** Medium
- **Why it matters:** Current lock keys prevent duplicate tasks, but the scope may still be too broad or too narrow depending on datasets and parameters.
- **Current mitigation:** downloader/build/train/eval routes use Redis locks.
- **Next action:** review lock key design against real operational use (per dataset, per level, per date range, etc.).

## 3. Data Risks

### Risk: Raw data path confusion
- **Status:** Medium
- **Why it matters:** Wrong input paths can silently build the wrong dataset.
- **Current mitigation:** scanned dropdowns plus manual override in the WebUI.
- **Next action:** display dataset metadata summary (date range, file count) next to the selected path before running jobs.

### Risk: Large storage growth
- **Status:** High
- **Why it matters:** `data/`, `runs/`, and exported artifacts can grow quickly and impact system stability.
- **Current mitigation:** git ignores large artifact directories.
- **Next action:** define retention and cleanup rules; consider archive or object storage strategy.

## 4. Model / Training Risks

### Risk: Environment-specific GPU behavior
- **Status:** Medium
- **Why it matters:** PyTorch/CUDA combinations may differ between machines and break reproducibility.
- **Current mitigation:** project pins a CUDA-compatible torch stack.
- **Next action:** document supported GPU/driver matrix and keep a reproducible environment export.

### Risk: Evaluation quality still operator-dependent
- **Status:** Medium
- **Why it matters:** Human judgment is still required to interpret whether the selected best checkpoint is truly operationally acceptable.
- **Current mitigation:** evaluation scripts and best-model outputs are automated.
- **Next action:** add richer comparative charts and deployment thresholds to the UI.

## 5. Deployment Risks

### Risk: Container config is outdated
- **Status:** High
- **Why it matters:** existing `Dockerfile` / `docker-compose.yml` may not reflect the current multi-process WebUI + worker + OAuth architecture.
- **Current mitigation:** none beyond awareness.
- **Next action:** refresh deployment manifests before using containers in staging or production.

### Risk: Single-node assumptions
- **Status:** Medium
- **Why it matters:** current process manager and local paths assume a single-host runtime.
- **Current mitigation:** queue + services architecture is modular enough to evolve.
- **Next action:** define whether deployment target is single-node, LAN server, or cloud.

## 6. UX Risks

### Risk: Users may not understand when jobs are truly executing
- **Status:** Medium
- **Why it matters:** queue visibility exists, but users may confuse “enqueued” with “completed”.
- **Current mitigation:** job history and `/api/jobs` are exposed.
- **Next action:** improve status labels, timestamps, and progress hints in the UI.

### Risk: First-load behavior confusion
- **Status:** Low to Medium
- **Why it matters:** immediate redirects or background connection failures can feel like the UI is frozen.
- **Current mitigation:** landing page for logged-out users is in place.
- **Next action:** add health indicators for Redis, worker, and OAuth config on the landing page.

## 7. Recommended Priority Order

1. **High:** rotate secrets, refresh container/deployment config, validate with real Redis.
2. **High:** define artifact retention / storage limits.
3. **Medium:** improve path metadata and queue visibility in the UI.
4. **Medium:** document deployment environment assumptions and GPU compatibility.
5. **Low/Medium:** polish UX around login, health checks, and status messaging.
