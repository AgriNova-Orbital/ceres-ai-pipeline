from __future__ import annotations


def test_google_client_config_auto_discovers_client_secret_file(monkeypatch, tmp_path):
    from modules.google_user_oauth import (
        get_google_oauth_redirect_uri,
        get_google_web_client_config,
    )

    secret = tmp_path / "client_secret_demo.apps.googleusercontent.com.json"
    secret.write_text(
        '{"web":{"client_id":"cid-auto","client_secret":"csecret-auto","project_id":"proj-auto","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )

    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)
    monkeypatch.chdir(tmp_path)

    client_id, client_secret, project_id = get_google_web_client_config()
    redirect_uri = get_google_oauth_redirect_uri()

    assert client_id == "cid-auto"
    assert client_secret == "csecret-auto"
    assert project_id == "proj-auto"
    assert redirect_uri == "http://127.0.0.1:5055/auth/callback"


def test_build_google_credentials_from_oauth_token_uses_client_env(monkeypatch):
    from modules.google_user_oauth import build_google_credentials_from_oauth_token

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    token = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "scope": "openid email profile https://www.googleapis.com/auth/drive",
    }

    creds = build_google_credentials_from_oauth_token(token)

    assert creds.token == "access-123"
    assert creds.refresh_token == "refresh-456"
    assert creds.client_id == "client-id"
    assert creds.client_secret == "client-secret"



def test_google_client_config_discovers_client_secret_next_to_app_db(monkeypatch, tmp_path):
    from modules.google_user_oauth import get_google_web_client_config

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    secret = state_dir / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid-state","client_secret":"csecret-state","project_id":"proj-state","redirect_uris":["http://127.0.0.1:3002/api/oauth/callback"]}}',
        encoding="utf-8",
    )

    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", raising=False)
    monkeypatch.setenv("APP_DB_PATH", str(state_dir / "app.db"))
    monkeypatch.chdir(tmp_path)

    client_id, client_secret, project_id = get_google_web_client_config()

    assert client_id == "cid-state"
    assert client_secret == "csecret-state"
    assert project_id == "proj-state"
