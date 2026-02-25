from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
import shutil


def _write_fake_week(path: Path, *, base: float) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    h = 4
    w = 4
    data = np.zeros((3, h, w), dtype=np.float32)
    data[0, :, :] = base
    data[1, :, :] = base + 1.0
    data[2, :, :] = 0.25 * base

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=3,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    ) as ds:
        ds.write(data)


def test_dataset_service_creates_npz_files(tmp_path: Path):
    from modules.services.dataset_service import run_build

    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir(parents=True, exist_ok=True)

    _write_fake_week(raw / "fr_wheat_feat_2025_data_001.tif", base=1.0)
    _write_fake_week(raw / "fr_wheat_feat_2025_data_002.tif", base=2.0)

    run_build(
        input_dir=raw,
        output_dir=out,
        patch_size=2,
        step_size=2,
        expected_weeks=2,
        workers=2,
        gdal_cache_mb=32,
    )

    index_csv = out / "index.csv"
    assert index_csv.exists()
