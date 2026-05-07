from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_runs_required_verification_gates() -> None:
    assert WORKFLOW.exists()

    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow

    assert "  backend:" in workflow
    assert "uses: actions/checkout@v4" in workflow
    assert "uses: astral-sh/setup-uv@v5" in workflow
    assert "run: uv sync --dev" in workflow
    assert "run: uv run --dev python -m pytest -q" in workflow

    assert "  frontend:" in workflow
    assert "uses: actions/setup-node@v4" in workflow
    assert "node-version: 20" in workflow
    assert "cache: npm" in workflow
    assert "cache-dependency-path: frontend/package-lock.json" in workflow
    assert "working-directory: frontend" in workflow
    assert "run: npm ci" in workflow
    assert "run: node --test *.test.js lib/*.test.js" in workflow
    assert "run: npm run build" in workflow
    assert "run: npx playwright install --with-deps chromium" in workflow
    assert "run: npm run e2e" in workflow

    assert "  compose:" in workflow
    assert "WEBUI_SECRET_KEY=test-secret" in workflow
    assert "CLERK_JWT_ISSUER=https://clerk.test" in workflow
    assert "CLERK_JWT_AUDIENCE=ceres-test" in workflow
    assert (
        "docker compose --profile dev --profile beta --profile release config --quiet"
        in workflow
    )
