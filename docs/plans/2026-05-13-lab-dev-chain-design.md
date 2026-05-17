# Lab Development Chain Design

**Status:** Design draft

**Goal:** Move the active development, CI validation, deployment control plane, and primary project data storage into the lab while keeping GitHub, GHCR, Clerk, Sentry, Google APIs, and cloudflared as external services.

**Primary decision:** Use the lab Docker VM as the first-stage control and data node. Do not introduce Swarm, Kubernetes, a private registry, or distributed training orchestration in this phase.

## Context

The lab has a PVE-backed Docker VM with roughly 6T total storage and 128G RAM. About 4.5T will be allocated to this project. The VM does not have a GPU, so it should not be treated as the main heavy training node.

The project will use Google Colab for relay-style model training. The lab VM remains the source of truth for raw data, staged data, app runtime state, deployment, and promoted artifacts. Colab produces candidate training artifacts that are pulled back into the lab, validated, and promoted separately from application releases.

## Architecture

The first phase has four roles:

- **Lab Docker VM:** runs Portainer, Ceres Docker Compose stacks, GitHub self-hosted runner, Redis, API, frontend, worker, and local storage volumes.
- **GitHub and GHCR:** remain the source code and container image control plane. CI builds immutable image tags and pushes them to GHCR.
- **Portainer API:** is the deployment API for the Docker standalone environment. It should update/redeploy stacks, not replace CI.
- **cloudflared:** exposes only the pilot frontend and backend API. Development tools, Redis, Portainer, runner internals, and debug services stay private behind SSH or lab network access.

The recommended flow is GitHub PR validation, image build on merge, GHCR push, Portainer stack update, smoke check, and controlled promote to the public pilot stack.

## Environments

Use two deployable environments:

- **`ceres-staging`:** internal only. Used for image validation, Compose validation, smoke tests, small data checks, and artifact validation. It can be on-demand rather than permanently exposed.
- **`ceres-pilot`:** the public pilot service. cloudflared routes only to the frontend and backend API for this stack.

Do not maintain a permanent `dev` deployment. Development should use devcontainer or Compose dev profile over SSH on the lab VM and should be disposable.

## Deployment Flow

Pull requests should run tests and builds but should not deploy. The expected gates are Python tests, frontend unit tests, Next build, Playwright smoke tests, and Docker Compose config validation.

On merge to `main`, the lab runner should build API and frontend images and push immutable tags to GHCR, for example:

- `ghcr.io/agrinova-orbital/ceres-api:sha-<shortsha>`
- `ghcr.io/agrinova-orbital/ceres-frontend:sha-<shortsha>`
- optional SemVer tags such as `0.2.0-beta.N` or `0.2.0`

Portainer should deploy by explicit image tag. Avoid deploying from `latest`. Rollback should be implemented by redeploying the previous known-good image tag.

Promotion path:

1. Build and push immutable GHCR images.
2. Update `ceres-staging` through Portainer API.
3. Run staging smoke checks.
4. Manually approve promotion.
5. Update `ceres-pilot` through Portainer API using the same image tags.
6. Smoke check cloudflared public endpoints.

## Storage Layout

Allocate the 4.5T project space with raw data as the primary asset:

| Path | Budget | Purpose |
| --- | ---: | --- |
| `data/raw/` | 2.6T | Original GeoTIFF, Earth Engine, and Drive downloads. Highest retention priority. |
| `data/wheat_risk/staged/` | 900G | NPZ and staged datasets. Rebuildable from raw data. |
| `artifacts/colab/` | 450G | Colab checkpoints, metrics, configs, and manifests. |
| `runs/` | 250G | Local dry-runs, matrix metadata, and temporary experiment outputs. |
| `reports/`, `logs/`, `state/` | 100G | Runtime state, SQLite DB, reports, and logs. |
| `backups/` | 150G | SQLite, settings, manifests, promoted model metadata, and selected small reports. |
| Docker/cache/tmp buffer | 50G | Images, build cache, temp files, and emergency workspace. |

Operational thresholds:

- At more than 80% project disk usage, stop new raw ingestion and clean `data/wheat_risk/staged/` and `runs/` first.
- At more than 90% project disk usage, stop non-essential worker jobs and allow only cleanup/export metadata operations.
- Do not delete promoted model artifacts unless they have an external backup or explicit replacement.

## Colab Relay Training

Colab training is out-of-band from app deployment. It should not directly mutate pilot runtime state.

Initial relay path should use Google Drive as the handoff mechanism because the project already has Google OAuth and Drive integration. A Colab run should output a run folder containing:

- checkpoint files
- summary CSV
- eval metrics
- training config
- dataset manifest hash or version
- code/image version reference when available

The lab VM should pull Colab outputs into `artifacts/colab/<run_id>/`. Staging validates the artifact format, loads checkpoints, runs eval where practical, and records the result. Only validated artifacts should be promoted for pilot use.

Model artifact promotion should be separate from application image promotion. An app release can deploy without changing the active model, and a model promotion can happen without rebuilding the app image if the runtime reads a model pointer or configured artifact path.

## Security Boundaries

Keep secrets out of git and images. Runtime secrets should come from the VM, Portainer stack environment, GitHub Actions secrets, or runner-local configuration.

Public ingress should expose only:

- pilot frontend
- pilot backend API health/application endpoints required by the frontend

Do not expose:

- Redis
- Portainer
- GitHub runner internals
- dev frontend/backend
- debug endpoints
- Docker API or socket

The GitHub self-hosted runner should be outbound-only to GitHub. Portainer API credentials should be scoped and rotated. GHCR deploy tags should be immutable and traceable to commits.

## Out Of Scope For Phase 1

- Kubernetes
- Docker Swarm
- private lab registry
- direct Colab upload API
- GPU scheduling
- distributed training orchestration
- permanent three-environment dev/staging/prod setup
- full SaaS multi-tenant filesystem isolation

These can be revisited after the pilot deployment chain and artifact relay are stable.

## First Implementation Tasks

1. Add lab deployment documentation and runbook.
2. Add GHCR image build workflow for API and frontend.
3. Add a Portainer API deployment script for `ceres-staging` and `ceres-pilot`.
4. Add stack env templates without secrets.
5. Configure the lab GitHub self-hosted runner.
6. Add smoke checks for cloudflared public endpoints.
7. Add Colab artifact folder convention and manifest schema.
8. Add cleanup runbook for staged data, runs, and Colab artifacts.
