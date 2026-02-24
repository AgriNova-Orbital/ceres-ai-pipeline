from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest


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
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Wheat Risk WebUI" in body
    assert "Data Downloader" in body
    assert "Training Matrix" in body


def test_raw_preview_endpoint_returns_png(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    tif = tmp_path / "week_001.tif"
    _mk_fake_tif(tif)

    app = create_app(repo_root=tmp_path)
    client = app.test_client()
    resp = client.get(f"/api/preview/raw?path={tif}")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert len(resp.data) > 100


def test_patch_preview_endpoint_returns_png(tmp_path: Path) -> None:
    from apps.wheat_risk_webui import create_app

    npz = tmp_path / "sample.npz"
    _mk_fake_npz(npz)

    app = create_app(repo_root=tmp_path)
    client = app.test_client()
    resp = client.get(f"/api/preview/patch?path={npz}&t=1")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert len(resp.data) > 100


def test_downloader_preview_runs_dry_run_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_queue.enqueue.return_value = mock_job
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    client = app.test_client()
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
    _, kwargs = mock_queue.enqueue.call_args
    cmd = kwargs["args"][0]
    assert isinstance(cmd, list)
    assert "scripts/export_weekly_risk_rasters.py" in cmd
    assert "--dry-run" in cmd
