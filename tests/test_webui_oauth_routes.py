from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from pathlib import Path

import pytest


def _initialize_app(app, tmp_path: Path) -> None:
    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:5055",
    )
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()


@pytest.fixture
def app(tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    app.config.update({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_login_route_redirects_to_google(client):
    _initialize_app(client.application, Path(client.application.config["REPO_ROOT"]))
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["Location"]


def test_google_oauth_client_uses_openid_metadata(tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    oauth = app.extensions["authlib.integrations.flask_client"]
    client = oauth.create_client("google")

    assert client is not None
    assert getattr(client, "_server_metadata_url", None) == (
        "https://accounts.google.com/.well-known/openid-configuration"
    )


def test_login_route_uses_registered_redirect_uri_from_client_secret(
    client, tmp_path: Path, monkeypatch
):
    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"csecret","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", str(secret))

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    test_client = app.test_client()
    resp = test_client.get("/login")

    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["Location"]).query)
    assert qs["redirect_uri"][0] == "http://127.0.0.1:5055/auth/callback"


def test_login_route_auto_discovers_client_secret_in_repo_root(
    tmp_path: Path, monkeypatch
):
    secret = tmp_path / "client_secret_demo.apps.googleusercontent.com.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"csecret","redirect_uris":["http://127.0.0.1:5055/auth/callback"]}}',
        encoding="utf-8",
    )
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:5055",
    )
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()
    test_client = app.test_client()
    resp = test_client.get("/login")

    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["Location"]).query)
    assert qs["redirect_uri"][0] == "http://127.0.0.1:5055/auth/callback"


def test_protected_routes_redirect_to_login(client):
    _initialize_app(client.application, Path(client.application.config["REPO_ROOT"]))
    resp = client.get("/api/jobs")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_home_landing_page_is_accessible_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Initialization" in body or "Login with Google" in body
