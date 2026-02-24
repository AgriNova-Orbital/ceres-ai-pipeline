# tests/test_webui_enqueues_jobs.py
from unittest.mock import MagicMock
import pytest


def test_downloader_enqueues_job_instead_of_running(monkeypatch):
    mock_queue = MagicMock()
    # We need to create a fixture or a way to get the app object
    # For now, let's assume we have an app and a client
    from apps.wheat_risk_webui import create_app

    # This is tricky, we need to patch the get_queue function
    # Let's define it inside the webui module first
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue", lambda: mock_queue)

    app = create_app()
    client = app.test_client()

    client.post("/run/downloader", data={"action": "preview_export"})
    mock_queue.enqueue.assert_called_once()
