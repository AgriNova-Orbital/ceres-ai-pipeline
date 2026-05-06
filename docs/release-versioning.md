# Release Versioning

`VERSION` is the single product version source for Ceres.

## Version Format

Use SemVer with optional prerelease channel:

- `X.Y.Z-alpha.N` for alpha builds.
- `X.Y.Z-beta.N` for beta builds.
- `X.Y.Z` for release builds.

Examples:

- `0.2.1-alpha.1`
- `0.2.1-beta.1`
- `0.2.1`

## Channel Rules

- alpha: internal or first-pass validation builds. Expect breakage.
- beta: candidate builds after alpha validation. Avoid breaking changes unless necessary.
- release: stable build intended for normal operation.

Python metadata uses PEP 440 derived from the product version:

- `0.2.1-alpha.1` becomes `0.2.1a1` in `pyproject.toml` and `uv.lock`.
- `0.2.1-beta.1` becomes `0.2.1b1` in `pyproject.toml` and `uv.lock`.
- `0.2.1` remains `0.2.1`.

Frontend, Docker, and Sentry release metadata use the product SemVer string exactly.

## Commands

Use `scripts/bump_version.py` instead of editing version files by hand.

```bash
uv run --dev python scripts/bump_version.py alpha
uv run --dev python scripts/bump_version.py beta
uv run --dev python scripts/bump_version.py release
uv run --dev python scripts/bump_version.py patch
uv run --dev python scripts/bump_version.py minor
uv run --dev python scripts/bump_version.py major
uv run --dev python scripts/bump_version.py 0.3.0-beta.1
```

The script updates:

- `VERSION`
- `pyproject.toml`
- `uv.lock`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.env.example`
- `Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`

## Promotion Flow

Default flow for a patch release:

1. `alpha`: `0.2.0` -> `0.2.1-alpha.1`.
2. Additional alpha builds: `0.2.1-alpha.1` -> `0.2.1-alpha.2`.
3. `beta`: `0.2.1-alpha.2` -> `0.2.1-beta.1`.
4. Additional beta builds: `0.2.1-beta.1` -> `0.2.1-beta.2`.
5. `release`: `0.2.1-beta.2` -> `0.2.1`.

For larger prerelease trains, set the first prerelease explicitly, for example:

```bash
uv run --dev python scripts/bump_version.py 0.3.0-alpha.1
```
