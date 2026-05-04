from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _enable_clerk(monkeypatch) -> None:
    monkeypatch.setenv("CLERK_JWT_ISSUER", "https://clerk.test")


def test_healthz_stays_public_when_clerk_auth_is_enabled(monkeypatch, tmp_path: Path):
    _enable_clerk(monkeypatch)
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_api_run_requires_clerk_bearer_when_clerk_auth_is_enabled(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.post("/api/run/downloader", json={"action": "preview_export"})

    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Not authenticated"


def test_api_run_uses_verified_clerk_subject_as_job_user_id(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-clerk-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    def fake_verify(token: str) -> dict[str, object]:
        assert token == "token-123"
        return {"sub": "user_clerk_123", "email": "grower@example.com"}

    monkeypatch.setattr("modules.clerk_auth.verify_clerk_token", fake_verify)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/downloader",
        json={"action": "preview_export"},
        headers={"Authorization": "Bearer token-123"},
    )

    assert resp.status_code == 200
    _, kwargs = mock_queue.enqueue.call_args
    payload = kwargs["args"][0]
    assert payload["user_id"] == "user_clerk_123"


def test_api_run_does_not_accept_cached_session_without_bearer(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-clerk-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "user_clerk_123"},
    )

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    first = client.post(
        "/api/run/downloader",
        json={"action": "preview_export"},
        headers={"Authorization": "Bearer token-123"},
    )
    assert first.status_code == 200

    second = client.post("/api/run/downloader", json={"action": "preview_export"})

    assert second.status_code == 401


def test_api_admin_rejects_invalid_clerk_bearer(monkeypatch, tmp_path: Path):
    _enable_clerk(monkeypatch)

    def fake_verify(token: str) -> dict[str, object]:
        raise ValueError("invalid token")

    monkeypatch.setattr("modules.clerk_auth.verify_clerk_token", fake_verify)

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get(
        "/api/admin/system",
        headers={"Authorization": "Bearer bad-token"},
    )

    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Not authenticated"


def test_clerk_token_verification_requires_configured_issuer(monkeypatch):
    monkeypatch.delenv("CLERK_JWT_ISSUER", raising=False)
    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.test/.well-known/jwks.json")

    from modules import clerk_auth

    monkeypatch.setattr(
        clerk_auth,
        "_fetch_jwks",
        lambda url: pytest.fail("JWKS should not be fetched without an issuer"),
    )

    with pytest.raises(clerk_auth.ClerkAuthError):
        clerk_auth.verify_clerk_token("token-123")
