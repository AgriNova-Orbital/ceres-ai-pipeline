from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
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


def _login(client, app=None) -> None:
    with client.session_transaction() as sess:
        sess["user"] = {"email": "user@example.com"}
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
    assert job_kwargs["user_id"] == "uuid-user-123"


def test_drive_list_uses_current_user_token_not_latest_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    discovery = pytest.importorskip("googleapiclient.discovery")
    seen_token: dict[str, object] = {}

    class FakeListRequest:
        def execute(self):
            return {"files": []}

    class FakeFilesApi:
        def list(self, **kwargs):
            return FakeListRequest()

    class FakeService:
        def files(self):
            return FakeFilesApi()

    monkeypatch.setattr(
        "modules.google_user_oauth.build_google_credentials_from_oauth_token",
        lambda token: seen_token.update(token) or object(),
    )
    monkeypatch.setattr(discovery, "build", lambda *args, **kwargs: FakeService())

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)
    store = app.config["SQLITE_STORE"]
    other_user = store.get_or_create_user(
        google_sub="google-sub-other",
        email="other@example.com",
        display_name="Other User",
    )
    store.save_user_oauth_token(
        user_id=other_user["id"],
        token={"access_token": "other-token", "refresh_token": "other-refresh"},
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE user_oauth_tokens SET updated_at = '2099-01-01T00:00:00+00:00' WHERE user_id = ?",
            (other_user["id"],),
        )

    resp = client.get("/api/drive/list?id=root")

    assert resp.status_code == 200
    assert seen_token["access_token"] == "abc"


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


def test_api_job_detail_returns_single_rq_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeJob:
        id = "job-123"
        description = "downloader: refresh_inventory"
        meta = {"progress": 100, "step": "done"}
        enqueued_at = None
        started_at = None
        ended_at = None

        def return_value(self):
            return {"ok": True, "report": "reports/inventory.json"}

        def latest_result(self):
            return None

        def get_status(self):
            return "finished"

    class FakeQueue:
        def fetch_job(self, jid):
            return FakeJob() if jid == "job-123" else None

    monkeypatch.setattr("rq.Queue", lambda connection=None: FakeQueue())

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.get("/api/jobs/job-123")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["job"]["id"] == "job-123"
    assert payload["job"]["status"] == "finished"
    assert payload["job"]["meta"] == {"progress": 100, "step": "done"}
    assert payload["job"]["result"]["report"] == "reports/inventory.json"


def test_api_job_detail_uses_modern_rq_result_accessors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeResult:
        exc_string = "boom"

    class FakeJob:
        id = "job-123"
        description = "downloader: refresh_inventory"
        meta = {}
        enqueued_at = None
        started_at = None
        ended_at = None

        @property
        def result(self):
            raise AssertionError("deprecated result property should not be read")

        @property
        def exc_info(self):
            raise AssertionError("deprecated exc_info property should not be read")

        def return_value(self):
            return {"ok": True, "report": "reports/inventory.json"}

        def latest_result(self):
            return FakeResult()

        def get_status(self):
            return "finished"

    class FakeQueue:
        def fetch_job(self, jid):
            return FakeJob() if jid == "job-123" else None

    monkeypatch.setattr("rq.Queue", lambda connection=None: FakeQueue())

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.get("/api/jobs/job-123")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["job"]["result"]["report"] == "reports/inventory.json"
    assert payload["job"]["error"] == "boom"


def test_api_job_detail_returns_404_for_unknown_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeQueue:
        def fetch_job(self, jid):
            return None

    monkeypatch.setattr("rq.Queue", lambda connection=None: FakeQueue())

    app = create_app(repo_root=tmp_path)
    _initialize_app(app, tmp_path)
    client = app.test_client()
    _login(client, app)

    resp = client.get("/api/jobs/missing-job")

    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Job not found"


def test_healthz_reports_app_redis_and_sqlite_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeRedis:
        def ping(self):
            return True

    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: FakeRedis())

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/healthz")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["redis"] is True
    assert payload["db"] is True
    assert payload["checks"]["app"]["status"] == "ok"
    assert payload["checks"]["redis"]["status"] == "ok"
    assert payload["checks"]["sqlite"]["status"] == "ok"
    assert "path" not in payload["checks"]["sqlite"]


def test_healthz_returns_503_when_redis_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeRedis:
        def ping(self):
            raise RuntimeError("redis down")

    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: FakeRedis())

    app = create_app(repo_root=tmp_path)
    client = app.test_client()

    resp = client.get("/healthz")

    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["status"] == "degraded"
    assert payload["redis"] is False
    assert payload["db"] is True
    assert payload["checks"]["redis"]["status"] == "error"
    assert "redis down" not in str(payload)


def test_healthz_returns_503_when_sqlite_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    class FakeRedis:
        def ping(self):
            return True

    def fail_connect():
        raise RuntimeError("sqlite down")

    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: FakeRedis())

    app = create_app(repo_root=tmp_path)
    monkeypatch.setattr(app.config["SQLITE_STORE"], "_connect", fail_connect)
    client = app.test_client()

    resp = client.get("/healthz")

    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["status"] == "degraded"
    assert payload["redis"] is True
    assert payload["db"] is False
    assert payload["checks"]["sqlite"]["status"] == "error"
    assert "sqlite down" not in str(payload)
