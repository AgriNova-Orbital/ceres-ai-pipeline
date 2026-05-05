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


def test_env_example_documents_clerk_jwks_cache_ttl() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "CLERK_JWKS_CACHE_TTL_SECONDS=300" in env_example
