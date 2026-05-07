# Commercial Readiness Pilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Ceres AI Pipeline from internal beta toward a controlled pilot standard by closing the highest-risk security, deployment, and verification gaps without overbuilding full SaaS infrastructure.

**Architecture:** Keep the current single-node Docker Compose architecture, but make release mode fail-closed and operator-safe. Add explicit authorization helpers, sandbox user-controlled paths/scripts to approved roots/actions, and add CI/E2E gates that match the current product shape.

**Tech Stack:** Flask, Clerk JWT, SQLite, Redis/RQ, Docker Compose, Next.js 15, GitHub Actions, pytest, Node test runner, Playwright.

---

## Scope For Controlled Pilot

This plan targets a small set of trusted pilot users, not public multi-tenant SaaS. It intentionally avoids Kubernetes, full billing, multi-region infrastructure, and KMS-backed token encryption in this batch.

Pilot readiness definition:

- Release profile refuses weak/missing secrets and missing Clerk auth configuration.
- Admin APIs require an explicit admin role/claim.
- Admin role checks trust `public_metadata`, `private_metadata`, or `roles`; they do not trust `unsafe_metadata`.
- Legacy `/api/auth/*` routes fail closed when `APP_REQUIRE_CLERK_AUTH=true` but Clerk issuer configuration is missing.
- Authenticated users cannot execute arbitrary scripts or point jobs at arbitrary absolute paths.
- Docker context cannot accidentally include local secrets/cache files.
- CI runs the same core checks used during local verification.
- A browser smoke test covers the public route and protected redirect behavior.
- Playwright output directories are ignored.
- Missing-Clerk frontend fallback is only CI/non-production smoke behavior, not production auth.
- Future release hardening should require a frontend Clerk publishable key if not already enforced.

---

### Task 1: Release Mode Fails Closed

**Files:**
- Modify: `docker-compose.yml`
- Modify: `apps/wheat_risk_webui.py`
- Modify: `modules/clerk_auth.py`
- Test: `tests/test_deployment_env_wiring.py`
- Test: `tests/test_clerk_backend_auth.py`

**Step 1: Write failing Compose tests**

Add assertions to `tests/test_deployment_env_wiring.py`:

```python
def test_release_profile_requires_real_secrets_and_clerk() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    release_web = _service_block(compose, "web-release")

    assert "WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY:?" in release_web
    assert "CLERK_JWT_ISSUER=${CLERK_JWT_ISSUER:?" in release_web
    assert "CLERK_JWT_AUDIENCE=${CLERK_JWT_AUDIENCE:?" in release_web
    assert "APP_REQUIRE_CLERK_AUTH=true" in release_web
```

**Step 2: Write failing app-level tests**

Add to `tests/test_clerk_backend_auth.py`:

```python
def test_production_requires_webui_secret_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("WEBUI_SECRET_KEY", raising=False)

    from apps.wheat_risk_webui import create_app

    with pytest.raises(RuntimeError, match="WEBUI_SECRET_KEY"):
        create_app(repo_root=tmp_path)


def test_require_clerk_auth_requires_issuer(monkeypatch):
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", "true")
    monkeypatch.delenv("CLERK_JWT_ISSUER", raising=False)

    from modules import clerk_auth

    assert clerk_auth.is_clerk_auth_required() is True
    assert clerk_auth.is_clerk_auth_enabled() is False
```

**Step 3: Run tests to verify they fail**

Run:

```bash
uv run --dev python -m pytest tests/test_deployment_env_wiring.py tests/test_clerk_backend_auth.py -q
```

Expected: new tests fail because release profile has fallback secrets and `is_clerk_auth_required()` does not exist.

**Step 4: Implement minimal config hardening**

Update `modules/clerk_auth.py`:

```python
def is_clerk_auth_required() -> bool:
    return os.environ.get("APP_REQUIRE_CLERK_AUTH", "").strip().lower() in {"1", "true", "yes"}
```

Update `apps/wheat_risk_webui.py` near app creation:

```python
    secret_key = os.environ.get("WEBUI_SECRET_KEY", "").strip()
    if os.environ.get("FLASK_ENV") == "production" and not secret_key:
        raise RuntimeError("WEBUI_SECRET_KEY is required in production")
    if not secret_key:
        secret_key = os.urandom(32).hex()
```

In `_require_clerk_api_auth()` change the disabled behavior:

```python
        if not clerk_auth.is_clerk_auth_enabled():
            if clerk_auth.is_clerk_auth_required():
                return jsonify(error="Authentication is not configured"), 503
            return None
```

Update `docker-compose.yml` release web environment:

```yaml
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY:?WEBUI_SECRET_KEY is required for release}
      - APP_REQUIRE_CLERK_AUTH=true
      - CLERK_JWT_ISSUER=${CLERK_JWT_ISSUER:?CLERK_JWT_ISSUER is required for release}
      - CLERK_JWKS_URL=${CLERK_JWKS_URL:-}
      - CLERK_JWT_AUDIENCE=${CLERK_JWT_AUDIENCE:?CLERK_JWT_AUDIENCE is required for release}
```

Apply equivalent `APP_REQUIRE_CLERK_AUTH=true` and required Clerk vars to `worker-release` only if worker code depends on user token verification. Otherwise leave worker without Clerk checks to avoid unused config requirements.

**Step 5: Run tests to verify pass**

Run:

```bash
uv run --dev python -m pytest tests/test_deployment_env_wiring.py tests/test_clerk_backend_auth.py -q
```

Expected: pass.

**Step 6: Verify Compose remains valid with supplied release env**

Run:

```bash
WEBUI_SECRET_KEY=test-secret CLERK_JWT_ISSUER=https://clerk.test CLERK_JWT_AUDIENCE=ceres-test docker compose --profile release config --quiet
```

Expected: exit 0.

---

### Task 2: Admin APIs Require Admin Role

**Files:**
- Modify: `modules/clerk_auth.py`
- Modify: `apps/wheat_risk_webui.py`
- Test: `tests/test_clerk_backend_auth.py`
- Test: `frontend/proxy.ts` only if frontend needs a UX redirect later; not required for this backend gate.

**Implementation decision:** Admin role checks use `is_admin_claims()` and do not trust `unsafe_metadata`. Accepted sources are trusted Clerk claims such as `public_metadata`, `private_metadata`, or `roles`.

**Step 1: Write failing authorization tests**

Add to `tests/test_clerk_backend_auth.py`:

```python
def test_api_admin_requires_admin_claim(monkeypatch, tmp_path: Path):
    _enable_clerk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "user_123", "public_metadata": {"role": "member"}},
    )

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/api/admin/system", headers={"Authorization": "Bearer token-123"})

    assert resp.status_code == 403
    assert resp.get_json()["error"] == "Admin role required"


def test_api_admin_accepts_admin_claim(monkeypatch, tmp_path: Path):
    _enable_clerk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "admin_123", "public_metadata": {"role": "admin"}},
    )

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/api/admin/system", headers={"Authorization": "Bearer token-123"})

    assert resp.status_code == 200
```

**Step 2: Run tests to verify fail**

Run:

```bash
uv run --dev python -m pytest tests/test_clerk_backend_auth.py::test_api_admin_requires_admin_claim tests/test_clerk_backend_auth.py::test_api_admin_accepts_admin_claim -q
```

Expected: first test fails because admin APIs currently accept any valid Clerk user.

**Step 3: Implement role helper**

Add to `modules/clerk_auth.py`:

```python
def has_admin_role(claims: dict[str, object]) -> bool:
    for key in ("public_metadata", "private_metadata"):
        value = claims.get(key)
        if isinstance(value, dict) and value.get("role") == "admin":
            return True
    roles = claims.get("roles")
    return isinstance(roles, list) and "admin" in roles
```

**Step 4: Enforce admin role only for admin endpoints**

In `apps/wheat_risk_webui.py`, after successful Clerk verification:

```python
        if request.endpoint and request.endpoint.startswith("api_admin."):
            if not clerk_auth.has_admin_role(user):
                return jsonify(error="Admin role required"), 403
```

Do not require admin role for job/data/OAuth endpoints in this task.

Add regression coverage that `unsafe_metadata.role == "admin"` does not grant
admin access, and that `/api/auth/*` legacy password endpoints return
`503 {"error": "Authentication is not configured"}` when
`APP_REQUIRE_CLERK_AUTH=true` but Clerk issuer configuration is missing.

**Step 5: Run tests**

Run:

```bash
uv run --dev python -m pytest tests/test_clerk_backend_auth.py -q
```

Expected: pass.

---

### Task 3: Sandbox User-Controlled Paths And Scripts

**Files:**
- Modify: `apps/api_runs.py`
- Test: `tests/test_api_runs.py`

**Step 1: Write failing tests for absolute paths**

Add to `tests/test_api_runs.py`:

```python
def test_run_build_rejects_absolute_raw_dir(client):
    resp = client.post("/api/run/build", json={"raw_dir": "/etc", "action": "dry_run"})

    assert resp.status_code == 400
    assert "raw_dir" in resp.get_json()["error"]
```

Use the existing client fixture style in the file. If there is no direct fixture for authenticated API mode, follow the existing helper pattern used by current API run tests.

**Step 2: Write failing tests for custom train scripts**

Add:

```python
def test_run_train_rejects_custom_train_script(client):
    resp = client.post(
        "/api/run/train",
        json={"action": "run_matrix", "train_script": "scripts/anything_else.py"},
    )

    assert resp.status_code == 400
    assert "train_script" in resp.get_json()["error"]
```

**Step 3: Run tests to verify fail**

Run:

```bash
uv run --dev python -m pytest tests/test_api_runs.py -q
```

Expected: new tests fail because absolute paths and custom scripts are currently accepted.

**Step 4: Implement safe path helper**

Replace `_normalize_path()` in `apps/api_runs.py` with a root-scoped helper:

```python
    def _normalize_path(root: Path, path_like: str | None, default: str, *, field: str) -> str:
        raw = (path_like or default).strip()
        p = Path(raw)
        if p.is_absolute():
            raise ValueError(f"{field} must be a relative path")
        resolved = (root / raw).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError as e:
            raise ValueError(f"{field} must stay inside the application workspace") from e
        return str(resolved)
```

Wrap callers with 400 handling:

```python
        try:
            raw_dir = _normalize_path(root, data.get("raw_dir"), "data/raw/france_2025_weekly", field="raw_dir")
        except ValueError as e:
            return jsonify(error=str(e)), 400
```

Apply to downloader refresh and build raw dirs.

**Step 5: Lock training script to default**

Add helper:

```python
    def _default_train_script(root: Path) -> Path:
        return root / "scripts" / "train_wheat_risk_lstm.py"
```

In train payloads, reject supplied `train_script` if it differs:

```python
        if data.get("train_script") not in (None, "", "scripts/train_wheat_risk_lstm.py"):
            return jsonify(error="train_script is fixed for pilot deployments"), 400
```

Then set:

```python
"train_script": _default_train_script(root),
```

**Step 6: Run tests**

Run:

```bash
uv run --dev python -m pytest tests/test_api_runs.py -q
```

Expected: pass.

---

### Task 4: Docker Context And Local Secret Hygiene

**Files:**
- Modify: `.dockerignore`
- Modify: `tests/test_deployment_env_wiring.py`
- Optional docs: `docs/DEPLOYMENT_CHECKLIST.md`

**Step 1: Write failing test**

Add to `tests/test_deployment_env_wiring.py`:

```python
def test_dockerignore_excludes_local_secret_and_cache_artifacts() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for token in [".cache/", ".env*", "client_secret_*.json", "oauth_token*.json"]:
        assert token in dockerignore
```

**Step 2: Run test to verify fail**

Run:

```bash
uv run --dev python -m pytest tests/test_deployment_env_wiring.py::test_dockerignore_excludes_local_secret_and_cache_artifacts -q
```

Expected: fail because `.cache/`, `.env*`, and OAuth secret globs are not all excluded.

**Step 3: Update `.dockerignore`**

Add:

```text
.env*
.cache/
client_secret_*.json
oauth_token*.json
```

Keep existing explicit entries; duplication is acceptable but prefer replacing `.env`/`.env.bak` with `.env*`.

**Step 4: Run tests**

Run:

```bash
uv run --dev python -m pytest tests/test_deployment_env_wiring.py -q
```

Expected: pass.

---

### Task 5: GitHub Actions CI Gate

**Files:**
- Create: `.github/workflows/ci.yml`
- Test: no unit test; verify with local commands and workflow syntax review.

**Step 1: Create workflow**

Add `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Install dependencies
        run: uv sync --dev
      - name: Run Python tests
        run: uv run --dev python -m pytest -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Run unit tests
        run: node --test *.test.js lib/*.test.js
      - name: Build frontend
        run: npm run build

  compose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate Compose config
        run: |
          WEBUI_SECRET_KEY=test-secret \
          CLERK_JWT_ISSUER=https://clerk.test \
          CLERK_JWT_AUDIENCE=ceres-test \
          docker compose --profile dev --profile beta --profile release config --quiet
```

**Step 2: Local verification**

Run locally:

```bash
uv run --dev python -m pytest -q
node --test frontend/*.test.js frontend/lib/*.test.js
npm run build --prefix frontend
WEBUI_SECRET_KEY=test-secret CLERK_JWT_ISSUER=https://clerk.test CLERK_JWT_AUDIENCE=ceres-test docker compose --profile dev --profile beta --profile release config --quiet
```

Expected: all pass.

**Step 3: After PR merge, update branch protection**

After CI has run once on GitHub, set required checks on `main`:

```bash
gh api --method PATCH repos/AgriNova-Orbital/ceres-ai-pipeline/branches/main/protection/required_status_checks \
  -f strict=true \
  -f contexts[]=backend \
  -f contexts[]=frontend \
  -f contexts[]=compose
```

If GitHub reports context names differ, inspect actual check names with `gh pr checks <pr>` and use those names.

---

### Task 6: Browser Smoke Tests For Pilot Flow

**Files:**
- Create: `frontend/e2e/auth-smoke.spec.ts`
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`
- Modify: `.github/workflows/ci.yml`

**Implementation decision:** The missing-Clerk frontend fallback exists to support CI and non-production smoke behavior. It is not production authentication. Future release hardening should require a frontend Clerk publishable key if that gate is not already implemented.

**Implementation decision:** The smoke suite runs against `next dev` on an isolated local port after `npm run build` has already validated the production bundle. This keeps the smoke test minimal while still preserving a separate production build gate.

**Step 1: Add Playwright dependency and scripts**

Modify `frontend/package.json`:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "test": "node --test *.test.js lib/*.test.js",
  "e2e": "playwright test"
},
"devDependencies": {
  "@playwright/test": "^1.52.0",
  ...
}
```

Run `npm install` in `frontend/` to update `package-lock.json`.

**Step 2: Add Playwright config**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
});
```

**Step 3: Write smoke tests**

Create `frontend/e2e/auth-smoke.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("landing page is public", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Ceres/i })).toBeVisible();
});

test("protected dashboard redirects signed-out users", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/sign-in|login|clerk/i);
});
```

Adjust heading matcher after inspecting the landing page if needed.

**Step 4: Run E2E locally**

Run:

```bash
npm run build --prefix frontend
npm run e2e --prefix frontend
```

Expected: pass in desktop and mobile projects.

**Step 5: Add E2E job to CI**

In `.github/workflows/ci.yml`, add after frontend build:

```yaml
      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium
      - name: Run E2E smoke tests
        run: npm run e2e
```

Expected: CI frontend job covers unit, build, and smoke E2E.

**Implementation decision:** Playwright output (`frontend/test-results/`, `frontend/playwright-report/`) is ignored by git.

---

### Task 7: Pilot Documentation And Go/No-Go Checklist

**Files:**
- Modify: `docs/DEPLOYMENT_CHECKLIST.md`
- Create: `docs/PILOT_READINESS.md`
- Include: `docs/plans/2026-05-07-commercial-readiness-pilot.md`

**Step 1: Create pilot readiness doc**

Create `docs/PILOT_READINESS.md`:

```markdown
# Pilot Readiness

This document defines the minimum standard for a controlled pilot deployment.

## Required Before Pilot

- Clerk auth configured and `APP_REQUIRE_CLERK_AUTH=true`.
- At least one Clerk user has a trusted admin claim.
- Admin checks do not trust `unsafe_metadata`.
- Legacy `/api/auth/*` routes fail closed when Clerk auth is required but issuer configuration is missing.
- `WEBUI_SECRET_KEY` is a strong generated secret.
- Redis is not publicly reachable outside the deployment host/network.
- CI checks pass on the release PR.
- Playwright output is ignored by git.
- One real pipeline run has been recorded: downloader, dataset build, training, evaluation.

## Frontend Auth Boundary

- Missing-Clerk frontend fallback is for CI/non-production smoke behavior only.
- The fallback is not production authentication.
- Future release hardening should require a frontend Clerk publishable key if not already enforced.

## Not Yet Production SaaS

- No billing.
- No self-serve tenant provisioning.
- No KMS-backed token encryption.
- No automated backup restore validation.
- No public SLA.
```

**Step 2: Update deployment checklist**

Add a new section before Go/No-Go:

```markdown
## Pilot Hardening Gate

- [ ] Release Compose fails without required secrets.
- [ ] Admin APIs reject non-admin Clerk users.
- [ ] User-supplied paths are scoped to the workspace.
- [ ] Training script is fixed to the approved script.
- [ ] CI checks are required on `main`.
- [ ] Browser smoke tests pass on desktop and mobile.
```

**Step 3: Verify docs references**

Run:

```bash
uv run --dev python -m pytest tests/test_deployment_env_wiring.py -q
```

Expected: pass. No automated doc link checker exists yet.

---

## Final Verification Gate

Run from repository root:

```bash
uv run --dev python -m pytest -q
node --test frontend/*.test.js frontend/lib/*.test.js
npm run build --prefix frontend
npm run e2e --prefix frontend
WEBUI_SECRET_KEY=test-secret CLERK_JWT_ISSUER=https://clerk.test CLERK_JWT_AUDIENCE=ceres-test docker compose --profile dev --profile beta --profile release config --quiet
git status --short --branch
```

Expected:

- Python tests pass.
- Frontend unit tests pass.
- Frontend build passes.
- Playwright smoke tests pass.
- Compose config passes with required release env supplied.
- Working tree only contains intended changes.

---

## Commit Plan

Use small commits:

1. `fix(deploy): require release auth and secrets`
2. `fix(auth): require admin role for admin APIs`
3. `fix(api): sandbox pilot job inputs`
4. `fix(docker): exclude local secret artifacts`
5. `ci: add pilot readiness gates`
6. `test(frontend): add pilot smoke coverage`
7. `docs: define pilot readiness gate`

Do not squash locally. Let the PR preserve reviewable commits unless the maintainer chooses squash merge.
