from __future__ import annotations


def test_initialize_ee_accepts_credentials(monkeypatch):
    from modules import gee_api

    seen = {}

    class FakeEE:
        def Initialize(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(gee_api, "_ee", lambda: FakeEE())

    cred = object()
    gee_api.initialize_ee(project_id="demo-project", credentials=cred)

    assert seen["project"] == "demo-project"
    assert seen["credentials"] is cred
