from __future__ import annotations

import csv
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin


def _write_fake_week(path: Path, *, base: float) -> None:
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


def test_build_script_parallel_workers_mode(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir(parents=True, exist_ok=True)

    _write_fake_week(raw / "fr_wheat_feat_2025_data_001.tif", base=1.0)
    _write_fake_week(raw / "fr_wheat_feat_2025_data_002.tif", base=2.0)

    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_npz_dataset_from_geotiffs.py",
            "--input-dir",
            str(raw),
            "--output-dir",
            str(out),
            "--patch-size",
            "2",
            "--step-size",
            "2",
            "--expected-weeks",
            "2",
            "--workers",
            "2",
            "--gdal-cache-mb",
            "32",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout

    index_csv = out / "index.csv"
    assert index_csv.exists()

    with index_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))

    # 4x4 raster with patch=2 and step=2 => 4 patches total.
    assert len(rows) == 4

    sample = np.load(out / rows[0]["npz_path"], allow_pickle=False)
    assert sample["X"].shape == (2, 2, 2, 2)
    assert sample["y"].shape == (2,)


def test_build_patch_all_nan_risk_emits_no_runtime_warning(tmp_path: Path) -> None:
    from modules.services.dataset_service import _build_patch_and_save

    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    tif = raw / "fr_wheat_feat_2025_data_001.tif"

    data = np.zeros((3, 4, 4), dtype=np.float32)
    data[0, :, :] = 1.0
    data[1, :, :] = 2.0
    data[2, :, :] = np.nan
    with rasterio.open(
        tif,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=3,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    ) as ds:
        ds.write(data)

    examples = tmp_path / "examples"
    examples.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tif) as src:
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter("always", RuntimeWarning)
            npz_rel = _build_patch_and_save(
                row=0,
                col=0,
                patch_size=2,
                srcs=[src],
                feature_bands=[1, 2],
                risk_band=3,
                examples_dir=examples,
            )

    assert npz_rel is not None
    runtime_warnings = [w for w in got if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warnings
