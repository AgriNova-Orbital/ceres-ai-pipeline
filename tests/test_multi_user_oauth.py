from __future__ import annotations

from pathlib import Path

import pytest


def _install_fake_google_oauth(monkeypatch, token: dict[str, object]) -> None:
    class FakeGoogle:
        def authorize_access_token(self):
            return token

    class FakeOAuth:
        def __init__(self, app):
            self.google = FakeGoogle()

        def register(self, **kwargs):
            return None

    monkeypatch.setattr("apps.api_oauth.OAuth", FakeOAuth)


def _login_admin(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    app.config["TESTING"] = True
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:5055",
    )
    app.config["SQLITE_STORE"].set_admin("admin", "strong-test-password")
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_create_app_uses_secret_key_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("WEBUI_SECRET_KEY", "test-secret")
    db_path = tmp_path / "state" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    assert app.config["SECRET_KEY"] == "test-secret"


def test_auth_callback_creates_local_user(client, monkeypatch, app):
    _install_fake_google_oauth(
        monkeypatch,
        {
            "access_token": "access-123",
            "refresh_token": "refresh-456",
            "userinfo": {
                "sub": "sub-123",
                "email": "user@example.com",
                "name": "Demo User",
            },
        },
    )
    _login_admin(client)

    resp = client.get("/api/oauth/callback", follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        assert sess["user_id"]
        assert "google_token" not in sess

    store = app.config["SQLITE_STORE"]
    with client.session_transaction() as sess:
        user_id = sess["user_id"]
    stored_token = store.get_user_oauth_token(user_id)
    assert stored_token is not None
    assert stored_token["access_token"] == "access-123"


def test_auth_callback_reuses_same_local_uuid_for_same_google_sub(
    client, monkeypatch, app
):
    _install_fake_google_oauth(
        monkeypatch,
        {
            "access_token": "access-123",
            "refresh_token": "refresh-456",
            "userinfo": {
                "sub": "sub-123",
                "email": "user@example.com",
                "name": "Demo User",
            },
        },
    )
    _login_admin(client)

    client.get("/api/oauth/callback", follow_redirects=False)
    with client.session_transaction() as sess:
        user_id_1 = sess["user_id"]

    client.get("/api/oauth/callback", follow_redirects=False)
    with client.session_transaction() as sess:
        user_id_2 = sess["user_id"]

    assert user_id_1 == user_id_2


def test_auth_callback_binds_google_token_to_pending_clerk_user(
    client, monkeypatch, app
):
    monkeypatch.setenv("CLERK_JWT_ISSUER", "https://clerk.test")
    _install_fake_google_oauth(
        monkeypatch,
        {
            "access_token": "access-123",
            "refresh_token": "refresh-456",
            "userinfo": {
                "sub": "google-sub-123",
                "email": "user@example.com",
                "name": "Demo User",
            },
        },
    )
    with client.session_transaction() as sess:
        sess["pending_clerk_user"] = {"sub": "user_clerk_123", "exp": 2000000000}

    resp = client.get("/api/oauth/callback", follow_redirects=False)

    assert resp.status_code == 302
    store = app.config["SQLITE_STORE"]
    user = store.get_user_by_clerk_user_id("user_clerk_123")
    assert user is not None
    assert user["google_sub"] == "google-sub-123"
    assert store.get_user_oauth_token_for_principal("user_clerk_123")["access_token"] == "access-123"
