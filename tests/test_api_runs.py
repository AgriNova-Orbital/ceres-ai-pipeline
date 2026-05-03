from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


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


def test_api_run_downloader_preview_uses_export_task(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/downloader",
        json={
            "action": "preview_export",
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": "4",
        },
    )

    assert resp.status_code == 200
    assert resp.get_json()["job_id"] == "job-api-1"
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_export_weekly_risk_rasters"
    payload = kwargs["args"][0]
    assert payload["run"] is False
    assert payload["drive_folder"] is None


def test_api_run_downloader_run_export_requires_drive_folder(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/downloader",
        json={
            "action": "run_export",
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": "4",
        },
    )

    assert resp.status_code == 400
    assert "drive_folder" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


def test_api_run_downloader_refresh_inventory_uses_inventory_task(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-2"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/downloader",
        json={"action": "refresh_inventory", "raw_dir": "data/raw/france_2025_weekly"},
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_inventory"
    payload = kwargs["args"][0]
    assert payload["input_dir"].endswith("data/raw/france_2025_weekly")
    assert payload["output_dir"].endswith("reports")


def test_api_run_train_run_matrix_uses_task_run_matrix(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-3"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/train",
        json={"action": "run_matrix", "levels": "1,2", "steps": "100,500"},
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_matrix"
    payload = kwargs["args"][0]
    assert payload["levels"] == [1, 2]
    assert payload["steps"] == [100, 500]
    assert payload["dry_run"] is False


def test_api_run_train_execute_train_alias_maps_to_run_matrix(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-5"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/train",
        json={"action": "execute_train", "levels": "1", "steps": "100"},
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_matrix"
    payload = kwargs["args"][0]
    assert payload["execute_train"] is True
    assert payload["dry_run"] is False


def test_api_run_eval_uses_task_run_eval(monkeypatch, tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-4"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/api/run/eval",
        json={"levels": "1,2", "device": "cpu"},
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_eval"
    payload = kwargs["args"][0]
    assert payload["levels"] == [1, 2]
    assert payload["device"] == "cpu"
