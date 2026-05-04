# Observability Setup

This project supports optional Sentry and New Relic wiring across the Python API, RQ worker, and Next.js frontend.

## Sentry

Python services initialize Sentry only when `SENTRY_DSN` is set.

Next.js browser instrumentation initializes only when `NEXT_PUBLIC_SENTRY_DSN` is set. Server-side Next.js instrumentation can also use `SENTRY_DSN`.

```bash
SENTRY_DSN=https://example@sentry.io/project-id
NEXT_PUBLIC_SENTRY_DSN=https://example@sentry.io/project-id
SENTRY_ENVIRONMENT=dev
SENTRY_RELEASE=local
SENTRY_TRACES_SAMPLE_RATE=0
SENTRY_PROFILES_SAMPLE_RATE=0
SENTRY_SEND_DEFAULT_PII=false
```

For source map upload during frontend builds, set these in CI or the build environment:

```bash
SENTRY_AUTH_TOKEN=sntrys_xxx
SENTRY_ORG=your-org
SENTRY_PROJECT=your-project
```

## New Relic

Python web and worker containers use a lightweight wrapper. They run normally unless both `NEW_RELIC_LICENSE_KEY` and `NEW_RELIC_APP_NAME` are present.

```bash
NEW_RELIC_LICENSE_KEY=your-license-key
NEW_RELIC_APP_NAME="Ceres API Dev"
NEW_RELIC_WORKER_APP_NAME="Ceres Worker Dev"
NEW_RELIC_LOG=stdout
NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true
```

New Relic is intentionally not wired into the Next.js Node server in this first pass. Sentry covers frontend/browser errors; New Relic focuses on Flask and RQ APM.

## Clerk

Clerk should be a separate auth-replacement change. Clerk will own app identity, while Google Drive/Earth Engine OAuth tokens should remain backend-managed and tied to the Clerk user ID.
