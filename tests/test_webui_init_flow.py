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


def test_home_shows_setup_screen_when_not_initialized(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Checks" in body


def test_login_redirects_to_setup_when_not_initialized(client):
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "/setup" in resp.headers["Location"]


def test_setup_post_persists_settings(client, tmp_path: Path):
    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )

    resp = client.post(
        "/setup",
        data={
            "step": "3",
            "oauth_client_secret_path": str(secret),
            "redirect_base_url": "http://127.0.0.1:5055",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Initialization Saved" in resp.get_data(
        as_text=True
    ) or "Go to Dashboard" in resp.get_data(as_text=True)

    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "state" / "app.db")
    settings = store.get_settings()
    assert settings["initialized"] is True
    assert settings["oauth_client_secret_path"] == str(secret)
    assert settings["redirect_base_url"] == "http://127.0.0.1:5055"


def test_setup_post_can_store_uploaded_client_secret(client, tmp_path: Path):
    import io

    payload = io.BytesIO(
        b'{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}'
    )

    resp = client.post(
        "/setup",
        data={
            "step": "3",
            "oauth_client_secret_path": "",
            "redirect_base_url": "http://127.0.0.1:5055",
            "oauth_client_secret_upload": (payload, "client_secret_uploaded.json"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Initialization Saved" in resp.get_data(
        as_text=True
    ) or "Go to Dashboard" in resp.get_data(as_text=True)

    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "state" / "app.db")
    settings = store.get_settings()
    assert settings["initialized"] is True
    assert settings["oauth_client_secret_path"]
    assert settings["oauth_client_secret_path"].endswith("client_secret_uploaded.json")
