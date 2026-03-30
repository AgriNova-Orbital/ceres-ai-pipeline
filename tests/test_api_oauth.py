from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse


def test_api_oauth_login_requests_offline_access(tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:3002/api/oauth/callback"]}}',
        encoding="utf-8",
    )

    app = create_app(repo_root=tmp_path)
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:3002",
    )
    client = app.test_client()

    resp = client.get("/api/oauth/login")

    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["Location"]).query)
    assert qs["access_type"][0] == "offline"
    assert qs["prompt"][0] == "consent"
