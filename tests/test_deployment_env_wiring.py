from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service_block(compose_text: str, service_name: str) -> str:
    lines = compose_text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == f"  {service_name}:")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = i
            break
    return "\n".join(lines[start:end])


def test_compose_wires_clerk_env_to_web_and_frontend_services() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    for profile in ("dev", "beta", "release"):
        web = _service_block(compose, f"web-{profile}")
        assert "CLERK_JWT_ISSUER=${CLERK_JWT_ISSUER:-}" in web
        assert "CLERK_JWKS_URL=${CLERK_JWKS_URL:-}" in web
        assert "CLERK_JWT_AUDIENCE=${CLERK_JWT_AUDIENCE:-}" in web
        assert "CLERK_JWKS_CACHE_TTL_SECONDS=${CLERK_JWKS_CACHE_TTL_SECONDS:-300}" in web

        frontend = _service_block(compose, f"frontend-{profile}")
        assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: ${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}" in frontend
        assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}" in frontend
        assert "CLERK_SECRET_KEY=${CLERK_SECRET_KEY:-}" in frontend


def test_frontend_dockerfile_only_bakes_public_clerk_key() -> None:
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=" in dockerfile
    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" in dockerfile
    assert "ARG CLERK_SECRET_KEY" not in dockerfile


def test_frontend_dockerfile_copies_public_assets_for_standalone_runtime() -> None:
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY --from=builder --chown=nextjs:nodejs /app/public ./public" in dockerfile


def test_root_dockerignore_excludes_frontend_build_artifacts() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "frontend/node_modules/" in dockerignore
    assert "frontend/.next/" in dockerignore


def test_env_example_documents_clerk_jwks_cache_ttl() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "CLERK_JWKS_CACHE_TTL_SECONDS=300" in env_example


def test_compose_enables_sentry_logs_for_docker_services() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    for profile in ("dev", "beta", "release"):
        for service_prefix in ("web", "worker"):
            service = _service_block(compose, f"{service_prefix}-{profile}")
            assert "SENTRY_ENABLE_LOGS=${SENTRY_ENABLE_LOGS:-true}" in service
            assert "SENTRY_LOG_LEVEL=${SENTRY_LOG_LEVEL:-" in service
            assert "SENTRY_BREADCRUMB_LEVEL=${SENTRY_BREADCRUMB_LEVEL:-" in service
            assert "SENTRY_EVENT_LEVEL=${SENTRY_EVENT_LEVEL:-ERROR}" in service
            assert "APP_LOG_LEVEL=${APP_LOG_LEVEL:-" in service

        frontend = _service_block(compose, f"frontend-{profile}")
        assert "SENTRY_DSN=${SENTRY_DSN:-}" in frontend
        assert "SENTRY_ENABLE_LOGS=${SENTRY_ENABLE_LOGS:-true}" in frontend
        assert "NEXT_PUBLIC_SENTRY_ENABLE_LOGS=${NEXT_PUBLIC_SENTRY_ENABLE_LOGS:-true}" in frontend
        assert "NEXT_PUBLIC_SENTRY_ENVIRONMENT=${SENTRY_ENVIRONMENT:-" in frontend
        assert f"NEXT_PUBLIC_SENTRY_RELEASE=${{NEXT_PUBLIC_SENTRY_RELEASE:-{version}}}" in frontend


def test_env_example_documents_sentry_log_controls() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "SENTRY_ENABLE_LOGS=true" in env_example
    assert "SENTRY_LOG_LEVEL=INFO" in env_example
    assert "SENTRY_BREADCRUMB_LEVEL=INFO" in env_example
    assert "SENTRY_EVENT_LEVEL=ERROR" in env_example
    assert "APP_LOG_LEVEL=INFO" in env_example
