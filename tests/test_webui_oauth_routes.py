from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from pathlib import Path

import pytest


def _initialize_app(app, tmp_path: Path) -> None:
    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5055/api/oauth/callback"]}}',
        encoding="utf-8",
    )
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:5055",
    )
    app.config["SQLITE_STORE"].set_admin("admin", "strong-test-password")
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


def _login_admin(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}


def test_api_oauth_login_requires_legacy_session_when_clerk_disabled(client):
    _initialize_app(client.application, Path(client.application.config["REPO_ROOT"]))
    resp = client.get("/api/oauth/login")

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_api_oauth_login_redirects_to_google(client):
    _initialize_app(client.application, Path(client.application.config["REPO_ROOT"]))
    _login_admin(client)

    resp = client.get("/api/oauth/login")

    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["Location"]


def test_google_oauth_client_uses_openid_metadata(tmp_path: Path, monkeypatch):
    from flask import redirect

    captured: dict[str, object] = {}

    class FakeGoogle:
        def authorize_redirect(self, redirect_uri: str, **kwargs):
            captured["redirect_uri"] = redirect_uri
            captured["authorize_kwargs"] = kwargs
            return redirect("https://accounts.google.com/o/oauth2/v2/auth")

    class FakeOAuth:
        def __init__(self, app):
            self.google = FakeGoogle()

        def register(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("apps.api_oauth.OAuth", FakeOAuth)

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_admin(client)

    resp = client.get("/api/oauth/login")

    assert resp.status_code == 302
    assert captured["server_metadata_url"] == (
        "https://accounts.google.com/.well-known/openid-configuration"
    )


def test_login_route_uses_registered_redirect_uri_from_client_secret(
    client, tmp_path: Path, monkeypatch
):
    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"csecret","redirect_uris":["http://127.0.0.1:5055/api/oauth/callback"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", str(secret))

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    test_client = app.test_client()
    _login_admin(test_client)

    resp = test_client.get("/api/oauth/login")

    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["Location"]).query)
    assert qs["redirect_uri"][0] == "http://127.0.0.1:5055/api/oauth/callback"


def test_login_route_auto_discovers_client_secret_in_repo_root(
    tmp_path: Path, monkeypatch
):
    secret = tmp_path / "client_secret_demo.apps.googleusercontent.com.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"csecret","redirect_uris":["http://127.0.0.1:5055/api/oauth/callback"]}}',
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
    app.config["SQLITE_STORE"].set_admin("admin", "strong-test-password")
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()
    test_client = app.test_client()
    _login_admin(test_client)

    resp = test_client.get("/api/oauth/login")

    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["Location"]).query)
    assert qs["redirect_uri"][0] == "http://127.0.0.1:5055/api/oauth/callback"


def test_protected_routes_redirect_to_login(client):
    _initialize_app(client.application, Path(client.application.config["REPO_ROOT"]))
    resp = client.get("/api/jobs")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_home_landing_page_is_accessible_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
