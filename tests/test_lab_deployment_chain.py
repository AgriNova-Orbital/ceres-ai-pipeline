from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lab_deployment_runbook_documents_operational_gates() -> None:
    runbook = (ROOT / "docs" / "LAB_DEPLOYMENT_RUNBOOK.md").read_text(encoding="utf-8")

    for required in (
        "ceres-staging",
        "ceres-pilot",
        "GHCR",
        "Portainer API",
        "cloudflared",
        "manual approval",
        "rollback",
        "previous known-good image tag",
        "Do not deploy `latest`",
        "LOCAL_UID",
        "LOCAL_GID",
        "chown -R",
        "80%",
        "90%",
        "GitHub self-hosted runner",
    ):
        assert required in runbook

    assert "Redis" in runbook
    assert "Portainer" in runbook
    assert "Docker API" in runbook
    assert "private" in runbook.lower()


def test_ghcr_workflow_builds_immutable_api_and_frontend_images() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ghcr-build.yml").read_text(encoding="utf-8")

    for required in (
        "name: Build GHCR Images",
        "branches: [main]",
        "permissions:",
        "contents: read",
        "packages: write",
        "docker/login-action@v3",
        "registry: ghcr.io",
        "docker/build-push-action@v6",
        "SHORT_SHA=${GITHUB_SHA::12}",
        "ghcr.io/agrinova-orbital/ceres-api:sha-${{ env.SHORT_SHA }}",
        "ghcr.io/agrinova-orbital/ceres-frontend:sha-${{ env.SHORT_SHA }}",
        "context: .",
        "file: ./Dockerfile",
        "target: release",
        "context: ./frontend",
        "file: ./frontend/Dockerfile",
        "APP_VERSION=${{ env.APP_VERSION }}",
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${{ vars.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY }}",
        "NEXT_PUBLIC_SENTRY_DSN=${{ vars.NEXT_PUBLIC_SENTRY_DSN }}",
        "NEXT_PUBLIC_SENTRY_ENABLE_LOGS=${{ vars.NEXT_PUBLIC_SENTRY_ENABLE_LOGS }}",
        "NEXT_PUBLIC_SENTRY_ENVIRONMENT=${{ vars.NEXT_PUBLIC_SENTRY_ENVIRONMENT }}",
        "NEXT_PUBLIC_SENTRY_RELEASE=${{ vars.NEXT_PUBLIC_SENTRY_RELEASE }}",
    ):
        assert required in workflow

    assert ":latest" not in workflow


def test_ghcr_workflow_passes_clerk_publishable_key_to_frontend_build_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ghcr-build.yml").read_text(encoding="utf-8")

    api_step_start = workflow.index("name: Build and push API image")
    frontend_step_start = workflow.index("name: Build and push frontend image")
    api_step = workflow[api_step_start:frontend_step_start]
    frontend_step = workflow[frontend_step_start:]

    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${{ vars.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY }}" not in api_step
    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${{ vars.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY }}" in frontend_step


def test_ghcr_workflow_passes_public_sentry_values_to_frontend_build_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ghcr-build.yml").read_text(encoding="utf-8")

    api_step_start = workflow.index("name: Build and push API image")
    frontend_step_start = workflow.index("name: Build and push frontend image")
    api_step = workflow[api_step_start:frontend_step_start]
    frontend_step = workflow[frontend_step_start:]

    for arg in (
        "NEXT_PUBLIC_SENTRY_DSN=${{ vars.NEXT_PUBLIC_SENTRY_DSN }}",
        "NEXT_PUBLIC_SENTRY_ENABLE_LOGS=${{ vars.NEXT_PUBLIC_SENTRY_ENABLE_LOGS }}",
        "NEXT_PUBLIC_SENTRY_ENVIRONMENT=${{ vars.NEXT_PUBLIC_SENTRY_ENVIRONMENT }}",
        "NEXT_PUBLIC_SENTRY_RELEASE=${{ vars.NEXT_PUBLIC_SENTRY_RELEASE }}",
    ):
        assert arg not in api_step
        assert arg in frontend_step


def test_lab_env_templates_are_secret_free_and_cover_portainer_targets() -> None:
    portainer_env = (ROOT / "deploy" / "lab" / "portainer.env.example").read_text(encoding="utf-8")
    stack_env = (ROOT / "deploy" / "lab" / "stack.env.example").read_text(encoding="utf-8")

    for required in (
        "PORTAINER_URL=",
        "PORTAINER_API_TOKEN=",
        "PORTAINER_ENDPOINT_ID=",
        "PORTAINER_STAGING_STACK_ID=",
        "PORTAINER_PILOT_STACK_ID=",
        "PORTAINER_STAGING_STACK_NAME=ceres-staging",
        "PORTAINER_PILOT_STACK_NAME=ceres-pilot",
    ):
        assert required in portainer_env

    for required in (
        "WEBUI_SECRET_KEY=",
        "CLERK_JWT_ISSUER=",
        "CLERK_JWT_AUDIENCE=",
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=",
        "LOCAL_UID=1000",
        "LOCAL_GID=1000",
        "CERES_API_IMAGE=ghcr.io/agrinova-orbital/ceres-api:sha-",
        "CERES_FRONTEND_IMAGE=ghcr.io/agrinova-orbital/ceres-frontend:sha-",
        "APP_VERSION=0.2.0",
    ):
        assert required in stack_env

    combined = f"{portainer_env}\n{stack_env}"
    forbidden_values = ("sk_live_", "sk_test_", "pk_live_", "ghp_", "https://o", "Bearer ")
    for forbidden in forbidden_values:
        assert forbidden not in combined


def test_gitignore_excludes_private_lab_deployment_env_files() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "deploy/lab/portainer.env" in gitignore
    assert "deploy/lab/stack.env" in gitignore
    assert "!deploy/lab/*.env.example" in gitignore


def test_portainer_stack_template_uses_images_not_build_contexts() -> None:
    stack = (ROOT / "deploy" / "lab" / "docker-compose.portainer.yml").read_text(encoding="utf-8")

    assert "image: ${CERES_API_IMAGE}" in stack
    assert "image: ${CERES_FRONTEND_IMAGE}" in stack
    assert "web:" in stack
    assert "worker:" in stack
    assert "frontend:" in stack
    assert "redis:" in stack
    assert "APP_REQUIRE_CLERK_AUTH=true" in stack
    assert "build:" not in stack
    assert ":latest" not in stack


def test_portainer_stack_runs_api_and_worker_as_configured_lab_user() -> None:
    stack = (ROOT / "deploy" / "lab" / "docker-compose.portainer.yml").read_text(encoding="utf-8")

    web_start = stack.index("  web:")
    worker_start = stack.index("  worker:")
    frontend_start = stack.index("  frontend:")
    web_service = stack[web_start:worker_start]
    worker_service = stack[worker_start:frontend_start]

    assert 'user: "${LOCAL_UID:-1000}:${LOCAL_GID:-1000}"' in web_service
    assert 'user: "${LOCAL_UID:-1000}:${LOCAL_GID:-1000}"' in worker_service


def test_portainer_deploy_dry_run_outputs_redacted_update_payload(tmp_path: Path) -> None:
    env_file = tmp_path / "deploy.env"
    env_file.write_text(
        "\n".join(
            [
                "PORTAINER_URL=https://portainer.lab.example",
                "PORTAINER_API_TOKEN=test-token-must-not-leak",
                "PORTAINER_ENDPOINT_ID=2",
                "PORTAINER_STAGING_STACK_ID=17",
                "PORTAINER_STAGING_STACK_NAME=ceres-staging",
                "WEBUI_SECRET_KEY=test-secret-must-not-leak",
                "CLERK_JWT_ISSUER=https://clerk.test",
                "CLERK_JWT_AUDIENCE=ceres-test",
                "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_placeholder",
                "APP_VERSION=0.2.0",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/deploy_portainer_stack.py",
            "--env-file",
            str(env_file),
            "--target",
            "staging",
            "--api-image",
            "ghcr.io/agrinova-orbital/ceres-api:sha-abc123def456",
            "--frontend-image",
            "ghcr.io/agrinova-orbital/ceres-frontend:sha-abc123def456",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "test-token-must-not-leak" not in result.stdout
    assert "test-secret-must-not-leak" not in result.stdout

    payload = json.loads(result.stdout)
    assert payload["method"] == "PUT"
    assert payload["url"] == "https://portainer.lab.example/api/stacks/17?endpointId=2"
    assert payload["headers"]["X-API-Key"] == "<redacted>"
    assert payload["body"]["PullImage"] is True
    assert payload["body"]["Prune"] is True
    assert "ghcr.io/agrinova-orbital/ceres-api:sha-abc123def456" in payload["body"]["StackFileContent"]
    assert "ghcr.io/agrinova-orbital/ceres-frontend:sha-abc123def456" in payload["body"]["StackFileContent"]
    assert "latest" not in payload["body"]["StackFileContent"]


def test_portainer_deploy_loads_stack_env_separately_from_portainer_credentials(tmp_path: Path) -> None:
    portainer_env = tmp_path / "portainer.env"
    portainer_env.write_text(
        "\n".join(
            [
                "PORTAINER_URL=https://portainer.lab.example",
                "PORTAINER_API_TOKEN=test-token-must-not-leak",
                "PORTAINER_ENDPOINT_ID=2",
                "PORTAINER_STAGING_STACK_ID=17",
                "PORTAINER_STAGING_STACK_NAME=ceres-staging",
            ]
        ),
        encoding="utf-8",
    )
    stack_env = tmp_path / "stack.env"
    stack_env.write_text(
        "\n".join(
            [
                "WEBUI_SECRET_KEY=test-secret-must-not-leak",
                "CLERK_JWT_ISSUER=https://clerk.test",
                "CLERK_JWT_AUDIENCE=ceres-test",
                "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_placeholder",
                "APP_VERSION=0.2.0",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/deploy_portainer_stack.py",
            "--env-file",
            str(portainer_env),
            "--stack-env-file",
            str(stack_env),
            "--target",
            "staging",
            "--api-image",
            "ghcr.io/agrinova-orbital/ceres-api:sha-abc123def456",
            "--frontend-image",
            "ghcr.io/agrinova-orbital/ceres-frontend:sha-abc123def456",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "test-token-must-not-leak" not in result.stdout
    assert "test-secret-must-not-leak" not in result.stdout
    payload = json.loads(result.stdout)
    env = {item["name"]: item["value"] for item in payload["body"]["Env"]}
    assert env["WEBUI_SECRET_KEY"] == "<redacted>"
    assert env["CLERK_JWT_ISSUER"] == "https://clerk.test"


def test_portainer_deploy_rejects_latest_image_tags(tmp_path: Path) -> None:
    env_file = tmp_path / "deploy.env"
    env_file.write_text(
        "\n".join(
            [
                "PORTAINER_URL=https://portainer.lab.example",
                "PORTAINER_API_TOKEN=test-token",
                "PORTAINER_ENDPOINT_ID=2",
                "PORTAINER_STAGING_STACK_ID=17",
                "PORTAINER_STAGING_STACK_NAME=ceres-staging",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/deploy_portainer_stack.py",
            "--env-file",
            str(env_file),
            "--target",
            "staging",
            "--api-image",
            "ghcr.io/agrinova-orbital/ceres-api:latest",
            "--frontend-image",
            "ghcr.io/agrinova-orbital/ceres-frontend:sha-abc123def456",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "latest" in result.stderr
    assert "immutable" in result.stderr
