from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def _login_legacy_user(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}
        sess["user_id"] = "uuid-user-123"


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
    _login_legacy_user(client)

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
    assert payload["user_id"] == "uuid-user-123"


def test_api_run_downloader_run_export_requires_drive_folder(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

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
    _login_legacy_user(client)

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


def test_api_run_downloader_refresh_inventory_rejects_absolute_raw_dir(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/downloader",
        json={"action": "refresh_inventory", "raw_dir": "/tmp/outside-repo"},
    )

    assert resp.status_code == 400
    assert "raw_dir" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


def test_api_run_downloader_refresh_inventory_blank_raw_dir_uses_default(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-blank-raw"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/downloader",
        json={"action": "refresh_inventory", "raw_dir": "   "},
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_inventory"
    payload = kwargs["args"][0]
    assert payload["input_dir"].endswith("data/raw/france_2025_weekly")


def test_api_run_build_rejects_traversal_raw_dir(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/build",
        json={"action": "build_level", "raw_dir": "../outside-repo"},
    )

    assert resp.status_code == 400
    assert "raw_dir" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


def test_api_run_build_rejects_non_string_raw_dir(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/build",
        json={"action": "build_level", "raw_dir": ["data/raw/france_2025_weekly"]},
    )

    assert resp.status_code == 400
    assert "raw_dir" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


def test_api_run_build_resolves_contained_raw_dir_segments(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-contained-raw"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/build",
        json={
            "action": "build_level",
            "raw_dir": "data/raw/../raw/france_2025_weekly",
        },
    )

    assert resp.status_code == 200
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_build_dataset"
    payload = kwargs["args"][0]
    expected = (tmp_path / "data/raw/../raw/france_2025_weekly").resolve(
        strict=False
    )
    assert payload["input_dir"] == str(expected)
    assert ".." not in Path(payload["input_dir"]).parts


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
    _login_legacy_user(client)

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
    assert payload["repo_root"] == tmp_path
    assert payload["runs_dir"] == tmp_path / "runs"
    assert payload["index_csv_template"] == str(
        tmp_path / "data" / "wheat_risk" / "staged" / "L{level}" / "index.csv"
    )
    assert payload["root_dir_template"] == str(
        tmp_path / "data" / "wheat_risk" / "staged" / "L{level}"
    )
    assert payload["train_script"] == tmp_path / "scripts" / "train_wheat_risk_lstm.py"


def test_api_run_train_rejects_custom_train_script(
    monkeypatch, tmp_path: Path
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/train",
        json={
            "action": "run_matrix",
            "levels": "1",
            "steps": "100",
            "train_script": "scripts/custom_train.py",
        },
    )

    assert resp.status_code == 400
    assert "train_script" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


@pytest.mark.parametrize("train_script", [False, 0, [], {}])
def test_api_run_train_rejects_falsey_non_string_train_script(
    monkeypatch, tmp_path: Path, train_script
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/train",
        json={
            "action": "run_matrix",
            "levels": "1",
            "steps": "100",
            "train_script": train_script,
        },
    )

    assert resp.status_code == 400
    assert "train_script" in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


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
    _login_legacy_user(client)

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
    assert payload["repo_root"] == tmp_path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runs_dir", "/tmp/outside-repo"),
        ("index_csv_template", "../outside-repo/L{level}/index.csv"),
        ("root_dir_template", "/tmp/outside-repo/L{level}"),
    ],
)
def test_api_run_train_rejects_unsafe_matrix_paths(
    monkeypatch, tmp_path: Path, field: str, value: str
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-unsafe-train"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/train",
        json={
            "action": "run_matrix",
            "levels": "1",
            "steps": "100",
            field: value,
        },
    )

    assert resp.status_code == 400
    assert field in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()


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
    _login_legacy_user(client)

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
    assert payload["repo_root"] == tmp_path
    assert payload["summary_csv"] == tmp_path / "runs" / "staged_final" / "summary.csv"
    assert payload["index_csv_template"] == str(
        tmp_path / "data" / "wheat_risk" / "staged" / "L{level}" / "index.csv"
    )
    assert payload["root_dir_template"] == str(
        tmp_path / "data" / "wheat_risk" / "staged" / "L{level}"
    )
    assert payload["output_csv"] == tmp_path / "runs" / "staged_final" / "eval_metrics.csv"
    assert payload["best_json"] == tmp_path / "runs" / "staged_final" / "best_model.json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("summary_csv", "/tmp/outside-repo/summary.csv"),
        ("index_csv_template", "../outside-repo/L{level}/index.csv"),
        ("root_dir_template", "/tmp/outside-repo/L{level}"),
        ("output_csv", "../outside-repo/eval_metrics.csv"),
        ("best_json", "/tmp/outside-repo/best_model.json"),
    ],
)
def test_api_run_eval_rejects_unsafe_paths(
    monkeypatch, tmp_path: Path, field: str, value: str
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-api-unsafe-eval"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login_legacy_user(client)

    resp = client.post(
        "/api/run/eval",
        json={"levels": "1", field: value},
    )

    assert resp.status_code == 400
    assert field in str(resp.get_json().get("error", ""))
    mock_queue.enqueue.assert_not_called()
