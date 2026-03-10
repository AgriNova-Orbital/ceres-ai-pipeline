from __future__ import annotations

import json


def test_initialize_ee_for_export_uses_oauth_env(monkeypatch):
    from scripts import export_weekly_risk_rasters as export_script

    seen = {}

    class FakeEE:
        def Initialize(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_TOKEN_JSON",
        json.dumps({"access_token": "access-123", "refresh_token": "refresh-456"}),
    )

    export_script._initialize_ee_for_export(FakeEE(), ee_project="demo-project")

    assert seen["project"] == "demo-project"
    assert seen["credentials"].token == "access-123"
