from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
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
        sess["user"] = {"email": "user@example.com"}
        sess["user_id"] = "uuid-user-123"
        sess["must_change_password"] = False
    if app is not None:
        store = app.config["SQLITE_STORE"]
        store.save_user_oauth_token(
            user_id="uuid-user-123",
            token={"access_token": "abc", "refresh_token": "def"},
        )


def _mk_fake_tif(path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    arr = np.zeros((3, 16, 16), dtype=np.float32)
    arr[0] = 0.2
    arr[1] = 0.5
    arr[2] = 0.8
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=16,
        width=16,
        count=3,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    ) as ds:
        ds.write(arr)


def _mk_fake_npz(path: Path) -> None:
    x = np.random.default_rng(42).random((4, 3, 16, 16), dtype=np.float32)
    y = np.array([0.1, 0.2, 0.8, 0.9], dtype=np.float32)
    np.savez_compressed(path, X=x, y=y)


def test_webui_home_renders_tabs(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Wheat Risk WebUI" in body
    assert "Data Downloader" in body
    assert "Training Matrix" in body


def test_webui_raw_dir_dropdown_auto_scans_data_directories(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    raw_base = tmp_path / "data" / "raw"
    fr_dir = raw_base / "france_2025_weekly"
    de_dir = raw_base / "germany_2025_weekly"
    empty_dir = raw_base / "empty_dir"
    fr_dir.mkdir(parents=True)
    de_dir.mkdir(parents=True)
    empty_dir.mkdir(parents=True)

    _mk_fake_tif(fr_dir / "week_001.tif")
    _mk_fake_tif(de_dir / "week_001.tif")

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<select name="raw_dir">' in body
    assert 'value="data/raw/france_2025_weekly"' in body
    assert 'value="data/raw/germany_2025_weekly"' in body
    assert "empty_dir" not in body


def test_webui_path_fields_support_scanned_choices_and_custom_input(
    tmp_path: Path,
) -> None:
    from apps.wheat_risk_webui import create_app

    raw_base = tmp_path / "data" / "raw" / "france_2025_weekly"
    raw_base.mkdir(parents=True)
    tif = raw_base / "week_001.tif"
    _mk_fake_tif(tif)

    patch_base = tmp_path / "data" / "wheat_risk" / "staged" / "L1" / "examples"
    patch_base.mkdir(parents=True)
    npz = patch_base / "sample_001.npz"
    _mk_fake_npz(npz)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="raw_path_select"' in body
    assert 'id="raw_path_custom"' in body
    assert 'id="patch_path_select"' in body
    assert 'id="patch_path_custom"' in body
    assert 'value="data/raw/france_2025_weekly/week_001.tif"' in body
    assert 'value="data/wheat_risk/staged/L1/examples/sample_001.npz"' in body
    assert 'name="raw_dir_custom"' in body


def test_raw_preview_endpoint_returns_png(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    data_dir = tmp_path / "data" / "raw" / "france_2025_weekly"
    data_dir.mkdir(parents=True)
    tif = data_dir / "week_001.tif"
    _mk_fake_tif(tif)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get(f"/api/preview/raw?path={tif}")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert len(resp.data) > 100


def test_patch_preview_endpoint_returns_png(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    data_dir = tmp_path / "data" / "wheat_risk" / "staged" / "L1"
    data_dir.mkdir(parents=True)
    npz = data_dir / "sample.npz"
    _mk_fake_npz(npz)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    resp = client.get(f"/api/preview/patch?path={npz}&t=1")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert len(resp.data) > 100


def test_patch_preview_rejects_paths_outside_repo_allowlist(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    outside = Path("/tmp/outside-preview.npz")
    _mk_fake_npz(outside)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.get(f"/api/preview/patch?path={outside}&t=0")
    assert resp.status_code == 403


def test_raw_preview_rejects_paths_outside_repo_allowlist(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    outside = Path("/tmp/outside-preview.tif")
    _mk_fake_tif(outside)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.get(f"/api/preview/raw?path={outside}")
    assert resp.status_code == 403


def test_downloader_preview_runs_dry_run_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    resp = client.post(
        "/run/downloader",
        data={
            "action": "preview_export",
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": "4",
            "drive_folder": "EarthEngine",
            "ee_project": "demo-proj",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    mock_queue.enqueue.assert_called_once()
    args, kwargs = mock_queue.enqueue.call_args
    assert args[0] == "modules.jobs.tasks.task_export_weekly_risk_rasters"
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["run"] is False
    assert job_kwargs["drive_folder"] == "EarthEngine"
    assert job_kwargs["ee_project"] == "demo-proj"


def test_drive_download_accepts_json_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-drive-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.post(
        "/api/drive/download",
        json={"file_ids": ["file-1", "file-2"], "save_dir": "data/raw/drive_download"},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["job_id"] == "job-drive-1"
    _, kwargs = mock_queue.enqueue.call_args
    job_kwargs = kwargs["args"][0]
    assert job_kwargs["file_ids"] == ["file-1", "file-2"]
    assert job_kwargs["save_dir"] == "data/raw/drive_download"


def test_api_jobs_respects_limit_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeRegistry:
        def __init__(self, ids):
            self._ids = ids

        def get_job_ids(self):
            return self._ids

    class FakeJob:
        def __init__(self, jid: str):
            self.id = jid
            self.description = f"train: job-{jid}"
            self.meta = {}
            self.result = None
            self.exc_info = None
            self.enqueued_at = None
            self.started_at = None
            self.ended_at = None

        def get_status(self):
            return "finished"

    class FakeQueue:
        def __init__(self):
            ids = [f"job-{i:03d}" for i in range(150)]
            self._ids = ids
            self.started_job_registry = FakeRegistry([])
            self.finished_job_registry = FakeRegistry(ids)
            self.failed_job_registry = FakeRegistry([])

        def get_job_ids(self):
            return []

        def fetch_job(self, jid):
            return FakeJob(jid)

    class FakeWorker:
        name = "worker-1"

        def get_state(self):
            return "idle"

        def get_current_job_id(self):
            return None

    monkeypatch.setattr("rq.Queue", lambda connection=None: FakeQueue())
    monkeypatch.setattr("rq.Worker.all", lambda connection=None: [FakeWorker()])

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp_default = client.get("/api/jobs")
    assert resp_default.status_code == 200
    data_default = resp_default.get_json()
    assert len(data_default["jobs"]) == 100

    resp_500 = client.get("/api/jobs?limit=500")
    assert resp_500.status_code == 200
    data_500 = resp_500.get_json()
    assert len(data_500["jobs"]) == 150

    resp_all = client.get("/api/jobs?all=1")
    assert resp_all.status_code == 200
    data_all = resp_all.get_json()
    assert len(data_all["jobs"]) == 150
