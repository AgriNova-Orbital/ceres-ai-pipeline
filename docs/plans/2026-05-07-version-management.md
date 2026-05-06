# Version Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one product version source and keep Python, frontend, Docker, and Sentry release metadata in sync.

**Architecture:** Use root `VERSION` as the source of truth. A small stdlib-only Python tool updates `pyproject.toml`, `frontend/package.json`, `frontend/package-lock.json`, `.env.example`, Dockerfiles, and `docker-compose.yml` so release metadata is not hand-edited in multiple places.

**Tech Stack:** Python 3.12 stdlib, TOML text replacement, JSON, Docker Compose, pytest, npm/Next.js.

---

### Task 1: Version Source And Sync Tests

**Files:**
- Create: `VERSION`
- Create: `tests/test_version_management.py`
- Modify: `pyproject.toml`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Step 1: Write failing tests**

Add tests that require `VERSION` to exist, use SemVer, and match `pyproject.toml`, `frontend/package.json`, and `frontend/package-lock.json`.

**Step 2: Run failing test**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: FAIL because `VERSION` does not exist.

**Step 3: Add minimal version source**

Create `VERSION` with `0.2.0`, and update package metadata to `0.2.0`.

**Step 4: Verify**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: PASS.

**Step 5: Commit**

Run: `git add VERSION pyproject.toml frontend/package.json frontend/package-lock.json tests/test_version_management.py && git commit -m "feat(release): add product version source"`

### Task 2: Version Bump Tool

**Files:**
- Create: `scripts/bump_version.py`
- Modify: `tests/test_version_management.py`

**Step 1: Write failing tests**

Add tests for `parse_version`, `bump_version`, and `replace_version_in_files` using temporary files.

**Step 2: Run failing test**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: FAIL because `scripts/bump_version.py` does not exist.

**Step 3: Implement minimal tool**

Add a stdlib CLI:
- `python scripts/bump_version.py patch|minor|major`
- `python scripts/bump_version.py 0.3.0`
- Updates all version-bearing files.

**Step 4: Verify**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: PASS.

**Step 5: Commit**

Run: `git add scripts/bump_version.py tests/test_version_management.py && git commit -m "feat(release): add version bump tool"`

### Task 3: Docker And Sentry Release Wiring

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `Dockerfile`
- Modify: `frontend/Dockerfile`
- Modify: `tests/test_version_management.py`

**Step 1: Write failing tests**

Add tests requiring Compose and Docker metadata defaults to use the current version, including `APP_VERSION`, `SENTRY_RELEASE`, and `NEXT_PUBLIC_SENTRY_RELEASE` defaults.

**Step 2: Run failing test**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: FAIL because release defaults still use `local`.

**Step 3: Wire defaults**

Set defaults to `0.2.0`, add image labels/args where useful, and document `APP_VERSION=0.2.0` in `.env.example`.

**Step 4: Verify**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`
Run: `docker compose --profile dev --profile beta --profile release config --quiet`

Expected: PASS.

**Step 5: Commit**

Run: `git add docker-compose.yml .env.example Dockerfile frontend/Dockerfile tests/test_version_management.py && git commit -m "feat(release): wire version into runtime metadata"`

### Task 4: Alpha/Beta/Release Rules

**Files:**
- Create: `docs/release-versioning.md`
- Modify: `scripts/bump_version.py`
- Modify: `tests/test_version_management.py`

**Step 1: Write failing tests**

Add tests requiring prerelease SemVer support for `X.Y.Z-alpha.N`, `X.Y.Z-beta.N`, and stable `X.Y.Z`; Python PEP 440 conversion; and documented release rules.

**Step 2: Run failing tests**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: FAIL because prerelease versions and rules docs are not supported yet.

**Step 3: Implement stage handling**

Update `scripts/bump_version.py` so `alpha`, `beta`, and `release` targets promote versions through the release lifecycle and convert Python package metadata to PEP 440.

**Step 4: Document rules**

Create `docs/release-versioning.md` with the alpha, beta, and release rules plus bump commands.

**Step 5: Verify**

Run: `uv run --dev python -m pytest tests/test_version_management.py -q`

Expected: PASS.

**Step 6: Commit**

Run: `git add docs/release-versioning.md docs/plans/2026-05-07-version-management.md scripts/bump_version.py tests/test_version_management.py && git commit -m "feat(release): support alpha beta release channels"`

### Task 5: Final Verification

**Files:**
- No edits unless verification reveals a defect.

**Step 1: Run tests**

Run: `uv run --dev python -m pytest -q`
Expected: PASS.

**Step 2: Run frontend tests**

Run: `node --test frontend/*.test.js frontend/lib/*.test.js`
Expected: PASS.

**Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS.

**Step 4: Run compose validation**

Run: `docker compose --profile dev --profile beta --profile release config --quiet`
Expected: PASS.
