# tests/test_webui_enqueues_jobs.py
from pathlib import Path
from unittest.mock import MagicMock

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
    app.config["SQLITE_STORE"].set_admin("admin", "strong-test-password")
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()


def _login(client, app=None) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"email": "user@example.com", "sub": "sub-123"}
        sess["user_id"] = "uuid-user-123"
        sess["must_change_password"] = False
    if app is not None:
        store = app.config["SQLITE_STORE"]
        with store._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (
                    id, google_sub, email, display_name, created_at, last_login_at
                ) VALUES (
                    'uuid-user-123', 'google-sub-123', 'user@example.com',
                    'Demo User', '2026-01-01T00:00:00+00:00',
                    '2026-01-01T00:00:00+00:00'
                )
                """
            )
        store.save_user_oauth_token(
            user_id="uuid-user-123",
            token={"access_token": "abc", "refresh_token": "def"},
        )


def test_downloader_enqueues_job_instead_of_running(monkeypatch, tmp_path: Path):
    mock_queue = MagicMock()
    # We need to create a fixture or a way to get the app object
    # For now, let's assume we have an app and a client
    from apps.wheat_risk_webui import create_app

    # This is tricky, we need to patch the get_queue function
    # Let's define it inside the webui module first
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post("/run/downloader", data={"action": "preview_export"})
    mock_queue.enqueue.assert_called_once()


def test_webui_enqueues_service_tasks_instead_of_run_script(
    monkeypatch, tmp_path: Path
):
    from unittest.mock import MagicMock
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

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
    client.post("/run/train", data={"action": "run_matrix"})
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_run_matrix" in str(args[0])
    mock_queue.reset_mock()

    # Test eval
    client.post("/run/eval")
    args, _ = mock_queue.enqueue.call_args
    assert "modules.jobs.tasks.task_run_eval" in str(args[0])


def test_job_status_endpoint_returns_json(monkeypatch, tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    # We need to mock redis/rq to return a dummy job
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.get_id.return_value = "dummy-id"
    mock_job.get_status.return_value = "queued"
    mock_job.func_name = "test_func"
    mock_queue.jobs = [mock_job]

    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, dict)
    assert "jobs" in payload
    assert isinstance(payload["jobs"], list)
    if len(payload["jobs"]) > 0:
        assert "status" in payload["jobs"][0]


def test_job_status_endpoint_handles_real_enqueued_job_with_fakeredis(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("USE_FAKEREDIS", "1")

    from apps.wheat_risk_webui import create_app, get_queue_conn

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    _login(client, app)

    q = get_queue_conn()
    q.enqueue(
        "modules.jobs.tasks.task_run_inventory",
        {"input_dir": str(tmp_path), "output_dir": str(tmp_path)},
    )

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, dict)
    assert isinstance(payload["jobs"], list)
    assert payload["jobs"]
    assert not payload["jobs"][0].get("error")


def test_downloader_enqueue_includes_user_oauth_token(monkeypatch, tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post("/run/downloader", data={"action": "refresh_inventory"})
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["user_id"] == "uuid-user-123"
    assert "oauth_token" not in job_kwargs


def test_enqueued_jobs_include_local_user_id(monkeypatch, tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post("/run/eval")
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["user_id"] == "uuid-user-123"


def test_downloader_custom_raw_dir_overrides_scanned_selection(
    monkeypatch, tmp_path: Path
):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post(
        "/run/downloader",
        data={
            "action": "refresh_inventory",
            "raw_dir": "data/raw/france_2025_weekly",
            "raw_dir_custom": "/tmp/custom_raw_dir",
        },
    )
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["input_dir"] == "/tmp/custom_raw_dir"


def test_downloader_preview_export_passes_user_id_to_worker_task(
    monkeypatch, tmp_path: Path
):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post(
        "/run/downloader",
        data={
            "action": "preview_export",
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": "4",
        },
    )
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_export_weekly_risk_rasters"
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["user_id"] == "uuid-user-123"
    assert job_kwargs["run"] is False
    assert job_kwargs["stage"] == "1"


def test_run_train_execute_train_alias_maps_to_run_matrix(monkeypatch, tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    client.post(
        "/run/train",
        data={"action": "execute_train", "levels": "1", "steps": "100"},
    )
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_run_matrix"
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["execute_train"] is True
    assert job_kwargs["dry_run"] is False
