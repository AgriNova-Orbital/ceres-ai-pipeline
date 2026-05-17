# Pilot Readiness

This document defines the minimum standard for a controlled pilot deployment of Ceres AI Pipeline.

## Controlled Pilot Requirements

- Release Compose fails without required secrets:
  - `WEBUI_SECRET_KEY`
  - `CLERK_JWT_ISSUER`
  - `CLERK_JWT_AUDIENCE`
- Backend auth runs with `APP_REQUIRE_CLERK_AUTH=true`.
- Legacy `/api/auth/*` routes fail closed if Clerk auth is required but issuer configuration is missing.
- Admin APIs require a trusted Clerk admin claim; `unsafe_metadata` is not trusted for admin access.
- User-supplied paths stay inside the application workspace.
- Training uses the approved pilot script only.
- Redis is not publicly reachable outside the deployment host/network.
- CI checks pass on the release PR.
- Browser smoke tests cover the public route and signed-out protected-route behavior.
- Playwright output directories remain ignored by git.
- One real pipeline run is recorded: downloader, dataset build, training, and evaluation.

## Frontend Auth Boundary

The missing-Clerk frontend fallback exists to support CI and non-production smoke behavior. It must not be used or treated as production authentication.

Before release promotion, require a frontend Clerk publishable key unless that gate is already enforced elsewhere.

## Not Yet Production SaaS

- No billing.
- No self-serve tenant provisioning.
- No public multi-tenant isolation guarantees.
- No KMS-backed token encryption.
- No automated backup restore validation.
- No multi-region failover.
- No public SLA.
