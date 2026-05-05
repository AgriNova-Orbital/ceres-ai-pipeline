from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(client) -> None:
    client.application.config["SQLITE_STORE"].set_admin(
        "admin", "strong-test-password"
    )
    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}


def test_home_redirects_to_login_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert 'name="username"' in resp.get_data(as_text=True)


def test_oauth_upload_secret_persists_settings(client, tmp_path: Path):
    import io

    _login_admin(client)
    payload = io.BytesIO(
        b'{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/api/oauth/callback"]}}'
    )
    resp = client.post(
        "/api/oauth/upload-secret",
        data={
            "redirect_base_url": "http://127.0.0.1:5055",
            "file": (payload, "client_secret_uploaded.json"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "state" / "app.db")
    settings = store.get_settings()
    assert settings["initialized"] is True
    assert settings["oauth_client_secret_path"].endswith("client_secret.json")
    assert settings["redirect_base_url"] == "http://127.0.0.1:5055"


def test_oauth_upload_secret_requires_authentication(client):
    resp = client.post("/api/oauth/upload-secret")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
