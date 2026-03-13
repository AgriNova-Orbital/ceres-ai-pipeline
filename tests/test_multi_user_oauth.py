from __future__ import annotations

from pathlib import Path

import pytest


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
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_auth_callback_creates_local_user(client, monkeypatch):
    from apps import wheat_risk_webui

    class FakeGoogle:
        def authorize_access_token(self):
            return {
                "access_token": "access-123",
                "refresh_token": "refresh-456",
                "userinfo": {
                    "sub": "sub-123",
                    "email": "user@example.com",
                    "name": "Demo User",
                },
            }

    fake_google = FakeGoogle()
    monkeypatch.setattr(wheat_risk_webui, "get_oauth_client", lambda app: fake_google)

    resp = client.get("/auth/callback", follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        assert sess["user_id"]
        assert sess["user"]["email"] == "user@example.com"
        assert sess["google_token"]["access_token"] == "access-123"


def test_auth_callback_reuses_same_local_uuid_for_same_google_sub(client, monkeypatch):
    from apps import wheat_risk_webui

    class FakeGoogle:
        def authorize_access_token(self):
            return {
                "access_token": "access-123",
                "refresh_token": "refresh-456",
                "userinfo": {
                    "sub": "sub-123",
                    "email": "user@example.com",
                    "name": "Demo User",
                },
            }

    fake_google = FakeGoogle()
    monkeypatch.setattr(wheat_risk_webui, "get_oauth_client", lambda app: fake_google)

    client.get("/auth/callback", follow_redirects=False)
    with client.session_transaction() as sess:
        user_id_1 = sess["user_id"]

    client.get("/auth/callback", follow_redirects=False)
    with client.session_transaction() as sess:
        user_id_2 = sess["user_id"]

    assert user_id_1 == user_id_2
