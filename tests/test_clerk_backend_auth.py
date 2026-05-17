from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _enable_clerk(monkeypatch) -> None:
    monkeypatch.setenv("CLERK_JWT_ISSUER", "https://clerk.test")


def _stub_admin_system_disk(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api_admin.shutil.disk_usage",
        lambda path: SimpleNamespace(total=100, used=25, free=75),
    )


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


def test_production_startup_requires_webui_secret_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("WEBUI_SECRET_KEY", raising=False)

    from apps.wheat_risk_webui import create_app

    with pytest.raises(RuntimeError, match="WEBUI_SECRET_KEY"):
        create_app(repo_root=tmp_path)


def test_required_clerk_auth_startup_requires_webui_secret_key(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", "true")
    monkeypatch.delenv("WEBUI_SECRET_KEY", raising=False)

    from apps.wheat_risk_webui import create_app

    with pytest.raises(RuntimeError, match="WEBUI_SECRET_KEY"):
        create_app(repo_root=tmp_path)


def test_non_production_startup_keeps_random_secret_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("WEBUI_SECRET_KEY", raising=False)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)

    assert app.config["SECRET_KEY"]


@pytest.mark.parametrize("truthy_value", ["1", "true", "TRUE", "yes", "on"])
def test_clerk_auth_required_accepts_truthy_values(monkeypatch, truthy_value: str):
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", truthy_value)

    from modules import clerk_auth

    assert clerk_auth.is_clerk_auth_required() is True


@pytest.mark.parametrize("falsey_value", ["", "0", "false", "no", "off", "unexpected"])
def test_clerk_auth_required_rejects_non_truthy_values(monkeypatch, falsey_value: str):
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", falsey_value)

    from modules import clerk_auth

    assert clerk_auth.is_clerk_auth_required() is False


def test_required_clerk_auth_returns_503_when_not_configured(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", "true")
    monkeypatch.setenv("WEBUI_SECRET_KEY", "test-secret")
    monkeypatch.delenv("CLERK_JWT_ISSUER", raising=False)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/api/admin/system")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "Authentication is not configured"


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


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/auth/login"),
        ("post", "/api/auth/register"),
        ("post", "/api/auth/change-password"),
        ("post", "/api/auth/logout"),
        ("get", "/api/auth/me"),
        ("get", "/api/auth/status"),
    ],
)
def test_legacy_password_auth_api_is_disabled_when_clerk_auth_is_enabled(
    monkeypatch, tmp_path: Path, method: str, path: str
):
    _enable_clerk(monkeypatch)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = getattr(client, method)(path, json={})

    assert resp.status_code == 410
    assert resp.get_json()["error"] == "Legacy password auth is disabled"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/auth/login"),
        ("post", "/api/auth/register"),
        ("post", "/api/auth/change-password"),
        ("post", "/api/auth/logout"),
        ("get", "/api/auth/me"),
        ("get", "/api/auth/status"),
    ],
)
def test_legacy_password_auth_api_fails_closed_when_clerk_is_required_but_missing(
    monkeypatch, tmp_path: Path, method: str, path: str
):
    monkeypatch.setenv("APP_REQUIRE_CLERK_AUTH", "true")
    monkeypatch.setenv("WEBUI_SECRET_KEY", "test-secret")
    monkeypatch.delenv("CLERK_JWT_ISSUER", raising=False)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = getattr(client, method)(path, json={})

    assert resp.status_code == 503
    assert resp.get_json() == {"error": "Authentication is not configured"}


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
    from modules import clerk_auth

    def fake_verify(token: str) -> dict[str, object]:
        raise clerk_auth.ClerkAuthError("invalid token")

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


def test_api_admin_rejects_authenticated_non_admin_clerk_user(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)
    _stub_admin_system_disk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "user_clerk_123", "public_metadata": {"role": "member"}},
    )

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get(
        "/api/admin/system",
        headers={"Authorization": "Bearer token-123"},
    )

    assert resp.status_code == 403
    assert resp.get_json() == {"error": "Admin role required"}


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "user_clerk_123", "public_metadata": {"role": "admin"}},
        {"sub": "user_clerk_123", "private_metadata": {"role": "admin"}},
        {"sub": "user_clerk_123", "roles": ["member", "admin"]},
        {"sub": "user_clerk_123", "role": "admin"},
        {"sub": "user_clerk_123", "org_role": "admin"},
    ],
)
def test_clerk_admin_role_is_detected_from_supported_claims(claims: dict[str, object]):
    from modules import clerk_auth

    assert clerk_auth.is_admin_claims(claims) is True


def test_unsafe_metadata_admin_role_does_not_grant_admin_access(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)
    _stub_admin_system_disk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "user_clerk_123", "unsafe_metadata": {"role": "admin"}},
    )

    from modules import clerk_auth
    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get(
        "/api/admin/system",
        headers={"Authorization": "Bearer token-123"},
    )

    assert clerk_auth.is_admin_claims({"unsafe_metadata": {"role": "admin"}}) is False
    assert resp.status_code == 403
    assert resp.get_json() == {"error": "Admin role required"}


def test_api_admin_accepts_admin_clerk_user(monkeypatch, tmp_path: Path):
    _enable_clerk(monkeypatch)
    _stub_admin_system_disk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {"sub": "user_clerk_123", "roles": ["admin"]},
    )

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get(
        "/api/admin/system",
        headers={"Authorization": "Bearer token-123"},
    )

    assert resp.status_code == 200
    assert "cpu_count" in resp.get_json()


def test_api_auth_reports_verification_outage_as_service_unavailable(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)

    from modules import clerk_auth

    def fake_verify(token: str) -> dict[str, object]:
        raise clerk_auth.ClerkVerificationUnavailable("jwks timeout")

    monkeypatch.setattr("modules.clerk_auth.verify_clerk_token", fake_verify)

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get(
        "/api/admin/system",
        headers={"Authorization": "Bearer token-123"},
    )

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "Authentication service unavailable"


def test_oauth_login_stores_minimal_pending_clerk_session(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)
    monkeypatch.setattr(
        "modules.clerk_auth.verify_clerk_token",
        lambda token: {
            "sub": "user_clerk_123",
            "email": "grower@example.com",
            "private_metadata": {"team": "ops"},
            "exp": 2000000000,
        },
    )

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    client.get(
        "/api/oauth/login",
        headers={"Authorization": "Bearer token-123"},
    )

    with client.session_transaction() as sess:
        pending_user = sess["pending_clerk_user"]

    assert pending_user == {"sub": "user_clerk_123", "exp": 2000000000}


def test_oauth_callback_uses_pending_clerk_session_without_bearer(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["pending_clerk_user"] = {"sub": "user_clerk_123", "exp": 2000000000}

    resp = client.get("/api/oauth/callback")

    assert resp.status_code in {302, 401}
    assert resp.status_code != 401 or resp.get_json()["error"] != "Not authenticated"
    with client.session_transaction() as sess:
        assert "pending_clerk_user" not in sess


def test_oauth_callback_rejects_expired_pending_clerk_session(
    monkeypatch, tmp_path: Path
):
    _enable_clerk(monkeypatch)

    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["pending_clerk_user"] = {"sub": "user_clerk_123", "exp": 1}

    resp = client.get("/api/oauth/callback")

    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Not authenticated"
    with client.session_transaction() as sess:
        assert "pending_clerk_user" not in sess


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


def test_clerk_auth_is_not_enabled_with_jwks_url_only(monkeypatch):
    monkeypatch.delenv("CLERK_JWT_ISSUER", raising=False)
    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.test/.well-known/jwks.json")

    from modules import clerk_auth

    assert clerk_auth.is_clerk_auth_enabled() is False


def test_clerk_jwks_cache_refreshes_after_ttl(monkeypatch):
    from modules import clerk_auth

    calls: list[str] = []
    now = 1000.0

    def fake_time() -> float:
        return now

    def fake_download(url: str) -> dict[str, object]:
        calls.append(url)
        return {"keys": [{"kid": str(len(calls))}]}

    monkeypatch.setenv("CLERK_JWKS_CACHE_TTL_SECONDS", "10")
    monkeypatch.setattr(clerk_auth.time, "time", fake_time)
    monkeypatch.setattr(clerk_auth, "_download_jwks", fake_download)
    clerk_auth.clear_jwks_cache()

    assert clerk_auth._fetch_jwks("https://clerk.test/jwks")["keys"][0]["kid"] == "1"
    assert clerk_auth._fetch_jwks("https://clerk.test/jwks")["keys"][0]["kid"] == "1"
    now = 1011.0
    assert clerk_auth._fetch_jwks("https://clerk.test/jwks")["keys"][0]["kid"] == "2"
    assert calls == ["https://clerk.test/jwks", "https://clerk.test/jwks"]
