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
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app()
    client = app.test_client()

    client.post("/run/downloader", data={"action": "preview_export"})
    mock_queue.enqueue.assert_called_once()


def test_webui_enqueues_service_tasks_instead_of_run_script(monkeypatch):
    from unittest.mock import MagicMock
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app()
    client = app.test_client()

    # Test inventory
    client.post("/run/downloader", data={"action": "refresh_inventory"})
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_run_inventory" in str(args[0])
    mock_queue.reset_mock()

    # Test build
    client.post("/run/build", data={"action": "build_level", "level": "1"})
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_build_dataset" in str(args[0])
    mock_queue.reset_mock()

    # Test train
    client.post("/run/train", data={"action": "execute_train"})
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_run_matrix" in str(args[0])
    mock_queue.reset_mock()

    # Test eval
    client.post("/run/eval")
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_run_eval" in str(args[0])


def test_job_status_endpoint_returns_json(monkeypatch):
    from apps.wheat_risk_webui import create_app

    # We need to mock redis/rq to return a dummy job
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.get_id.return_value = "dummy-id"
    mock_job.get_status.return_value = "queued"
    mock_job.func_name = "test_func"
    mock_queue.jobs = [mock_job]

    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app()
    client = app.test_client()
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json, list)
    if len(resp.json) > 0:
        assert "status" in resp.json[0]
