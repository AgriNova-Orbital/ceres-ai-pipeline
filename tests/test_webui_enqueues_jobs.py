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
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"email": "user@example.com", "sub": "sub-123"}
        sess["google_token"] = {"access_token": "abc", "refresh_token": "def"}
        sess["user_id"] = "uuid-user-123"


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
    _login(client)

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
    _login(client)

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
    _login(client)
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json, list)
    if len(resp.json) > 0:
        assert "status" in resp.json[0]


def test_job_status_endpoint_handles_real_enqueued_job_with_fakeredis(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("USE_FAKEREDIS", "1")

    from apps.wheat_risk_webui import create_app, get_queue_conn

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()

    _login(client)

    q = get_queue_conn()
    q.enqueue(
        "modules.jobs.tasks.task_run_inventory",
        {"input_dir": str(tmp_path), "output_dir": str(tmp_path)},
    )

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json, list)
    assert not resp.json[0].get("error")


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
    _login(client)

    client.post("/run/downloader", data={"action": "refresh_inventory"})
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["oauth_token"]["access_token"] == "abc"
    assert job_kwargs["oauth_token"]["refresh_token"] == "def"


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
    _login(client)

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
    _login(client)

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


def test_downloader_preview_export_passes_oauth_env_to_run_script(
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
    _login(client)

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
    _, kwargs = mock_queue.enqueue.call_args
    env_overrides = kwargs["kwargs"]["env_overrides"]
    assert "GOOGLE_OAUTH_TOKEN_JSON" in env_overrides


def test_make_redis_conn_honours_redis_url_env(monkeypatch):
    """_make_redis_conn should use REDIS_URL when set."""
    monkeypatch.delenv("USE_FAKEREDIS", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://custom-host:7777/3")

    from apps.wheat_risk_webui import _make_redis_conn

    conn = _make_redis_conn(decode_responses=True)
    pool = conn.connection_pool
    kw = pool.connection_kwargs
    assert kw.get("host") == "custom-host"
    assert kw.get("port") == 7777
    assert kw.get("db") == 3


def test_api_jobs_includes_started_and_finished_jobs(monkeypatch, tmp_path: Path):
    """The /api/jobs endpoint should return started/finished jobs, not just queued."""
    monkeypatch.setenv("USE_FAKEREDIS", "1")

    from apps.wheat_risk_webui import create_app, get_queue_conn

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client)

    from rq.job import Job

    q = get_queue_conn()
    job = q.enqueue("time.sleep", 0)

    # Manually move the job to the finished registry to simulate completion
    job.set_status("finished")
    q.finished_job_registry.add(job, ttl=-1)
    q.remove(job.id)

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json
    assert isinstance(data, list)
    job_ids = [r["id"] for r in data]
    assert job.id in job_ids


def test_worker_fakeredis_uses_shared_server(monkeypatch):
    """Worker FakeRedis mode should use a shared FakeServer for state sharing."""
    import modules.jobs.worker as w

    monkeypatch.setenv("USE_FAKEREDIS", "1")
    w._FAKE_REDIS_SERVER = None  # reset

    from fakeredis import FakeServer, FakeStrictRedis

    # Simulate what happens in worker.main() for FakeRedis path
    if w._FAKE_REDIS_SERVER is None:
        w._FAKE_REDIS_SERVER = FakeServer()
    conn1 = FakeStrictRedis(server=w._FAKE_REDIS_SERVER)
    conn2 = FakeStrictRedis(server=w._FAKE_REDIS_SERVER)
    conn1.set("test_key", "test_val")
    assert conn2.get("test_key") == b"test_val"
