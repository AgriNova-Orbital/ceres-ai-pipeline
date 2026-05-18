# Lab Deployment Runbook

This runbook covers the first lab deployment chain for Ceres. GitHub remains the source code control plane, GHCR stores immutable images, and the lab VM deploys `ceres-staging` and `ceres-pilot` through the Portainer API.

## Environments

- `ceres-staging` is internal-only. Use it for image validation, Compose validation, smoke checks, and model artifact validation before any public change.
- `ceres-pilot` is the public pilot stack. cloudflared may route to the pilot frontend and required backend API endpoints only.
- Do not keep a permanent public dev stack. Development should use a disposable devcontainer or local Compose profile over SSH.

## Build And Publish

The GitHub workflow builds the API and frontend containers on pushes to `main` and publishes them to GHCR with immutable commit tags:

- `ghcr.io/agrinova-orbital/ceres-api:sha-<shortsha>`
- `ghcr.io/agrinova-orbital/ceres-frontend:sha-<shortsha>`

Do not deploy `latest`. Every Portainer deployment must use explicit image tags from the merge commit or a separately approved version tag.

Set the repository variable `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` before building pilot frontend images. The value is public, but Next.js needs it at image build time for Clerk-enabled routes.

## GitHub Runner

The initial workflow can run on GitHub-hosted Linux runners. When the lab GitHub self-hosted runner is configured, restrict it to outbound GitHub access, avoid mounting the Docker socket into untrusted jobs, and give it only the repository permissions needed to build and push GHCR images.

## Portainer Deployment

Use `scripts/deploy_portainer_stack.py` from the lab VM. Keep `deploy/lab/portainer.env` and `deploy/lab/stack.env` private on the VM. The script reads Portainer credentials from `--env-file` and stack runtime values from `--stack-env-file`.

1. Confirm the target image tags exist in GHCR.
2. Update `ceres-staging` through the Portainer API with the API and frontend tags.
3. Run staging smoke checks against the internal frontend and `/healthz` API endpoint.
4. Get manual approval before changing `ceres-pilot`.
5. Deploy the same image tags to `ceres-pilot`.
6. Smoke check cloudflared public endpoints.

For pilot deployment, require an explicit approval step in the release checklist. The deploy script also requires `--approve-pilot` for the pilot target.

## Rollback

Rollback means redeploying the previous known-good image tag through Portainer. Do not rebuild from an old branch during an incident unless the known-good image is unavailable.

1. Identify the previous known-good image tag from the deployment log or GHCR package history.
2. Redeploy `ceres-staging` with that tag and run smoke checks.
3. Redeploy `ceres-pilot` with the same previous known-good image tag after manual approval.
4. Record the failed tag, rollback tag, operator, and timestamp in the incident note.

## Storage Operations

The lab project data root should reserve raw data as the highest-retention asset. Use this cleanup order when disk pressure rises:

- At more than 80% project disk usage, stop new raw ingestion and clean rebuildable staged data and temporary `runs/` first.
- At more than 90% project disk usage, stop non-essential worker jobs and allow only cleanup or metadata export operations.
- Do not delete promoted model artifacts unless they have an external backup or an explicitly approved replacement.

## Public Exposure Boundary

Keep Redis, Portainer, GitHub self-hosted runner internals, debug services, and the Docker API private behind SSH or the lab network. cloudflared should expose only the pilot frontend and the backend API endpoints required by the frontend.

If a smoke check needs internal access, run it from the lab VM or over SSH rather than exposing private services.
