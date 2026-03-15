"""Tests for scripts/inspect_geotiff_stats.py.

Verifies the per-file diagnostic output format, NaN/finite/zero ratio
computations, and CLI argument handling for the GeoTIFF inspection script.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin


def _write_tif(
    path: Path,
    *,
    data: np.ndarray,
    nodata: float | None = None,
) -> None:
    c, h, w = data.shape
    kwargs: dict = dict(
        driver="GTiff",
        height=h,
        width=w,
        count=c,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    )
    if nodata is not None:
        kwargs["nodata"] = nodata
    with rasterio.open(path, "w", **kwargs) as ds:
        ds.write(data)


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/inspect_geotiff_stats.py", *args],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Unit tests for inspect_file / _compute_band_stats
# ---------------------------------------------------------------------------

def test_compute_band_stats_all_finite(tmp_path: Path) -> None:
    """All-finite band: nan_ratio=0, zero_ratio computed from exact zeros."""
    from scripts.inspect_geotiff_stats import _compute_band_stats

    data = np.array([[1.0, 2.0], [0.0, 4.0]], dtype=np.float32)
    total = data.size  # 4
    stats = _compute_band_stats(data, total)

    assert stats["nan_ratio"] == 0.0
    assert stats["zero_ratio"] == pytest.approx(1 / 4)  # one exact zero
    assert stats["min"] == pytest.approx(0.0)
    assert stats["max"] == pytest.approx(4.0)
    assert stats["mean"] == pytest.approx(np.mean([1.0, 2.0, 0.0, 4.0]))


def test_compute_band_stats_all_nan() -> None:
    """All-NaN band: nan_ratio=1, min/max/mean are NaN."""
    from scripts.inspect_geotiff_stats import _compute_band_stats

    data = np.full((2, 2), np.nan, dtype=np.float32)
    stats = _compute_band_stats(data, data.size)

    assert stats["nan_ratio"] == pytest.approx(1.0)
    assert stats["zero_ratio"] == 0.0  # NaN != 0.0
    assert np.isnan(stats["min"])
    assert np.isnan(stats["max"])
    assert np.isnan(stats["mean"])


def test_compute_band_stats_mixed() -> None:
    """Mixed valid/NaN band: ratios sum correctly, stats on finite values."""
    from scripts.inspect_geotiff_stats import _compute_band_stats

    data = np.array([[np.nan, 3.0], [0.0, np.nan]], dtype=np.float32)
    total = data.size  # 4
    stats = _compute_band_stats(data, total)

    assert stats["nan_ratio"] == pytest.approx(0.5)
    assert stats["zero_ratio"] == pytest.approx(0.25)  # one zero out of 4
    assert stats["min"] == pytest.approx(0.0)
    assert stats["max"] == pytest.approx(3.0)
    assert stats["mean"] == pytest.approx(1.5)  # mean of [3.0, 0.0]


# ---------------------------------------------------------------------------
# inspect_file output format
# ---------------------------------------------------------------------------

def test_inspect_file_output_format(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """inspect_file prints the separator, filename, global stats, and per-band stats."""
    from scripts.inspect_geotiff_stats import inspect_file

    bands, h, w = 11, 4, 4
    data = np.ones((bands, h, w), dtype=np.float32) * 0.5
    # Mark top half as NaN (50% of pixels).
    data[:, :2, :] = np.nan

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data)

    inspect_file(tif)  # default: first and last band
    captured = capsys.readouterr().out

    lines = captured.splitlines()
    assert lines[0] == "=" * 100
    assert lines[1] == "file: fr_wheat_feat_2025_data_001.tif"
    assert "global_nan_ratio:" in captured
    assert "global_finite_ratio:" in captured
    # Default bands are 1 and 11 for an 11-band raster.
    assert "band_1_nan_ratio:" in captured
    assert "band_11_nan_ratio:" in captured
    assert lines[-1] == "=" * 100


def test_inspect_file_global_ratios_sum_to_one(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """global_nan_ratio + global_finite_ratio must equal 1."""
    from scripts.inspect_geotiff_stats import inspect_file

    data = np.ones((3, 4, 4), dtype=np.float32)
    data[:, :2, :] = np.nan  # 50% NaN
    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    inspect_file(tif, band_indices=[1])
    captured = capsys.readouterr().out

    nan_ratio = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("global_nan_ratio:"))
    )
    finite_ratio = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("global_finite_ratio:"))
    )
    assert nan_ratio + finite_ratio == pytest.approx(1.0)
    assert nan_ratio == pytest.approx(0.5)


def test_inspect_file_nodata_null_gee_profile(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """GEE-style file (nodata=None, NaN stored in data): correct ratios reported."""
    from scripts.inspect_geotiff_stats import inspect_file

    # Simulate production profile: 11 bands, no nodata tag, ~77% NaN.
    bands, h, w = 11, 10, 13  # 130 pixels per band
    data = np.ones((bands, h, w), dtype=np.float32) * 0.4
    # Mark 100 of 130 pixels as NaN (~76.9%).
    data[:, :, :10] = np.nan  # 10 columns × 10 rows = 100 pixels per band

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    # No nodata kwarg — GEE export convention.
    _write_tif(tif, data=data)

    inspect_file(tif, band_indices=[1, 11])
    captured = capsys.readouterr().out

    nan_ratio = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("global_nan_ratio:"))
    )
    assert nan_ratio == pytest.approx(100 / 130, abs=1e-6)

    # Band 11 (risk band) nan_ratio should match band 1.
    b1_nan = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("band_1_nan_ratio:"))
    )
    b11_nan = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("band_11_nan_ratio:"))
    )
    assert b1_nan == pytest.approx(b11_nan)

    # min/max/mean should be computed on finite values only (value = 0.4).
    b1_min = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("band_1_min:"))
    )
    assert b1_min == pytest.approx(0.4, abs=1e-5)


def test_inspect_file_custom_bands(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Custom --bands argument reports only the requested bands."""
    from scripts.inspect_geotiff_stats import inspect_file

    data = np.ones((5, 4, 4), dtype=np.float32)
    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    inspect_file(tif, band_indices=[2, 4])
    captured = capsys.readouterr().out

    assert "band_2_nan_ratio:" in captured
    assert "band_4_nan_ratio:" in captured
    assert "band_1_nan_ratio:" not in captured
    assert "band_5_nan_ratio:" not in captured


def test_inspect_file_zero_ratio_excludes_nan(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """NaN pixels must not be counted as zeros in zero_ratio."""
    from scripts.inspect_geotiff_stats import inspect_file

    # All pixels are NaN → zero_ratio must be 0.
    data = np.full((2, 4, 4), np.nan, dtype=np.float32)
    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    inspect_file(tif, band_indices=[1])
    captured = capsys.readouterr().out

    zero_ratio = float(
        next(l.split(": ")[1] for l in captured.splitlines() if l.startswith("band_1_zero_ratio:"))
    )
    assert zero_ratio == 0.0


# ---------------------------------------------------------------------------
# run_inspect (multi-file, sorted)
# ---------------------------------------------------------------------------

def test_run_inspect_sorts_files_by_name(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Files are reported in sorted filename order."""
    from scripts.inspect_geotiff_stats import run_inspect

    data = np.ones((2, 2, 2), dtype=np.float32)
    for idx in [3, 1, 2]:
        _write_tif(tmp_path / f"fr_wheat_feat_2025_data_{idx:03d}.tif", data=data)

    run_inspect(tmp_path, band_indices=[1])
    captured = capsys.readouterr().out

    file_lines = [l for l in captured.splitlines() if l.startswith("file:")]
    names = [l.split("file: ")[1] for l in file_lines]
    assert names == sorted(names), "Files must be reported in sorted order"


def test_run_inspect_empty_dir(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Empty directory prints a 'no files found' message without crashing."""
    from scripts.inspect_geotiff_stats import run_inspect

    run_inspect(tmp_path)
    captured = capsys.readouterr().out
    assert "No GeoTIFF files found" in captured


# ---------------------------------------------------------------------------
# CLI tests (subprocess)
# ---------------------------------------------------------------------------

def test_cli_produces_expected_output(tmp_path: Path) -> None:
    """CLI end-to-end: correct format and content for a known input."""
    data = np.ones((3, 4, 4), dtype=np.float32) * 2.0
    data[:, :2, :] = np.nan  # 50% NaN
    _write_tif(tmp_path / "fr_wheat_feat_2025_data_001.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path), "--bands", "1,3"])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    assert "file: fr_wheat_feat_2025_data_001.tif" in out
    assert "global_nan_ratio:" in out
    assert "global_finite_ratio:" in out
    assert "band_1_nan_ratio:" in out
    assert "band_3_nan_ratio:" in out
    assert "=" * 100 in out


def test_cli_missing_input_dir_exits_nonzero(tmp_path: Path) -> None:
    """Non-existent --input-dir causes non-zero exit code."""
    proc = _run_script(["--input-dir", str(tmp_path / "does_not_exist")])
    assert proc.returncode != 0


def test_cli_invalid_bands_exits_nonzero(tmp_path: Path) -> None:
    """Invalid --bands value causes non-zero exit code."""
    data = np.ones((2, 2, 2), dtype=np.float32)
    _write_tif(tmp_path / "test.tif", data=data)
    proc = _run_script(["--input-dir", str(tmp_path), "--bands", "abc"])
    assert proc.returncode != 0


def test_cli_default_bands_first_and_last(tmp_path: Path) -> None:
    """Without --bands, script reports band 1 and the last band."""
    bands = 5
    data = np.ones((bands, 3, 3), dtype=np.float32)
    _write_tif(tmp_path / "fr_wheat_feat_2025_data_001.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path)])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    assert "band_1_nan_ratio:" in out
    assert f"band_{bands}_nan_ratio:" in out
    # Intermediate bands should NOT appear.
    assert "band_2_nan_ratio:" not in out
    assert "band_3_nan_ratio:" not in out
