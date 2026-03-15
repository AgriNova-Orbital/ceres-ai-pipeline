"""Tests for scripts/verify_geotiff_band_complement.py.

Verifies the band complementarity check output format, numeric correctness,
and CLI argument handling.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

# Float32 machine epsilon: 2^-23 ≈ 1.192e-07.
_FLOAT32_EPS = 1.1920928955078125e-07


def _write_tif(path: Path, *, data: np.ndarray) -> None:
    c, h, w = data.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=c,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    ) as ds:
        ds.write(data)


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/verify_geotiff_band_complement.py", *args],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Unit tests for _check_complement
# ---------------------------------------------------------------------------

def test_check_complement_perfect_sum(tmp_path: Path) -> None:
    """Pixels where band_1 + band_last = 1.0 exactly yield diff = 0."""
    from scripts.verify_geotiff_band_complement import _check_complement

    # Exact complements using float32 values that sum to 1.0 without error.
    band1 = np.array([[0.25, 0.5], [0.75, 0.0]], dtype=np.float32)
    band2 = 1.0 - band1  # also float32-exact
    data = np.stack([band1, band2], axis=0)  # (2, 2, 2)

    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif, band_a=1, band_b=2)
    assert mean_d == pytest.approx(0.0, abs=1e-9)
    assert max_d == pytest.approx(0.0, abs=1e-9)


def test_check_complement_float32_epsilon_bound(tmp_path: Path) -> None:
    """Typical GEE export values stay within float32 machine epsilon."""
    from scripts.verify_geotiff_band_complement import _check_complement

    FLOAT32_EPS = np.float32(1.0) - np.float32(np.nextafter(np.float32(1.0), np.float32(0.0)))

    rng = np.random.default_rng(42)
    band1 = rng.uniform(-1.0, 1.0, (4, 4)).astype(np.float32)
    band2 = (np.float32(1.0) - band1).astype(np.float32)  # float32 complement
    data = np.stack([band1, band2], axis=0)

    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif)
    # Float32 subtraction introduces at most 1 ULP of error.
    assert max_d <= 2 * float(FLOAT32_EPS), f"max_abs_diff={max_d} exceeds 2*float32_eps"


def test_check_complement_all_nan_returns_nan(tmp_path: Path) -> None:
    """All-NaN file returns (nan, nan) without crashing."""
    from scripts.verify_geotiff_band_complement import _check_complement

    data = np.full((2, 3, 3), np.nan, dtype=np.float32)
    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif)
    assert math.isnan(mean_d)
    assert math.isnan(max_d)


def test_check_complement_ignores_nan_pixels(tmp_path: Path) -> None:
    """NaN pixels are excluded from the diff computation."""
    from scripts.verify_geotiff_band_complement import _check_complement

    band1 = np.array([[np.nan, 0.5], [0.25, np.nan]], dtype=np.float32)
    band2 = np.array([[np.nan, 0.5], [0.75, np.nan]], dtype=np.float32)
    data = np.stack([band1, band2], axis=0)

    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif)
    # Only two valid pixels (0.5+0.5=1.0, 0.25+0.75=1.0).
    assert mean_d == pytest.approx(0.0, abs=1e-9)
    assert max_d == pytest.approx(0.0, abs=1e-9)


def test_check_complement_non_complementary_pixels(tmp_path: Path) -> None:
    """Non-complementary pixels are correctly detected and quantified."""
    from scripts.verify_geotiff_band_complement import _check_complement

    # band_1 + band_2 = 1.5 (off by 0.5).
    band1 = np.array([[0.5, 0.3]], dtype=np.float32)
    band2 = np.array([[1.0, 0.5]], dtype=np.float32)  # sums: 1.5, 0.8
    data = np.stack([band1, band2], axis=0)

    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif)
    # |0.5+1.0-1.0|=0.5, |0.3+0.5-1.0|=0.2 → mean=0.35, max=0.5
    assert mean_d == pytest.approx(0.35, abs=1e-5)
    assert max_d == pytest.approx(0.5, abs=1e-5)


def test_check_complement_default_band_b_is_last(tmp_path: Path) -> None:
    """With band_b=None, the last band is used automatically."""
    from scripts.verify_geotiff_band_complement import _check_complement

    # 5 bands; band 5 = 1 - band 1 exactly.
    h, w = 3, 3
    band1 = np.full((h, w), 0.4, dtype=np.float32)
    other = np.full((h, w), 0.0, dtype=np.float32)
    band5 = np.float32(1.0) - band1
    data = np.stack([band1, other, other, other, band5], axis=0)

    tif = tmp_path / "test.tif"
    _write_tif(tif, data=data)

    mean_d, max_d = _check_complement(tif, band_a=1, band_b=None)
    # float32 round-trip through GeoTIFF may introduce at most 1 ULP.
    assert mean_d <= _FLOAT32_EPS
    assert max_d <= _FLOAT32_EPS


# ---------------------------------------------------------------------------
# run_verify (multi-file, sorted)
# ---------------------------------------------------------------------------

def test_run_verify_sorts_files_by_name(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Files are reported in sorted filename order."""
    from scripts.verify_geotiff_band_complement import run_verify

    h, w = 2, 2
    band1 = np.full((h, w), 0.5, dtype=np.float32)
    band2 = np.float32(1.0) - band1
    data = np.stack([band1, band2], axis=0)

    for idx in [3, 1, 2]:
        _write_tif(tmp_path / f"fr_wheat_feat_2025_data_{idx:03d}.tif", data=data)

    run_verify(tmp_path)
    captured = capsys.readouterr().out
    names = [l.split(" ")[0] for l in captured.splitlines() if l.strip()]
    assert names == sorted(names)


def test_run_verify_empty_dir(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Empty directory prints a 'no files found' message without crashing."""
    from scripts.verify_geotiff_band_complement import run_verify

    run_verify(tmp_path)
    captured = capsys.readouterr().out
    assert "No GeoTIFF files found" in captured


def test_run_verify_output_format(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Output format exactly matches the problem statement: '<name> mean_abs_diff= X max_abs_diff= Y'."""
    from scripts.verify_geotiff_band_complement import run_verify

    band1 = np.array([[0.3, 0.7]], dtype=np.float32)
    band2 = np.float32(1.0) - band1
    data = np.stack([band1, band2], axis=0)
    _write_tif(tmp_path / "fr_wheat_feat_2025_data_001.tif", data=data)

    run_verify(tmp_path)
    line = capsys.readouterr().out.strip()

    assert line.startswith("fr_wheat_feat_2025_data_001.tif ")
    assert " mean_abs_diff= " in line
    assert " max_abs_diff= " in line


# ---------------------------------------------------------------------------
# CLI tests (subprocess)
# ---------------------------------------------------------------------------

def test_cli_produces_one_line_per_file(tmp_path: Path) -> None:
    """CLI outputs exactly one line per GeoTIFF file."""
    band1 = np.array([[0.4]], dtype=np.float32)
    band2 = np.float32(1.0) - band1
    data = np.stack([band1, band2], axis=0)
    for idx in range(1, 4):
        _write_tif(tmp_path / f"fr_wheat_feat_2025_data_{idx:03d}.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path)])
    assert proc.returncode == 0, proc.stderr
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    assert len(lines) == 3


def test_cli_output_within_float32_epsilon(tmp_path: Path) -> None:
    """max_abs_diff is within float32 machine epsilon for complementary data."""
    rng = np.random.default_rng(0)
    band1 = rng.uniform(-1.0, 1.0, (10, 10)).astype(np.float32)
    band2 = (np.float32(1.0) - band1).astype(np.float32)
    data = np.stack([band1, band2], axis=0)
    _write_tif(tmp_path / "fr_wheat_feat_2025_data_001.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path)])
    assert proc.returncode == 0, proc.stderr

    line = proc.stdout.strip()
    max_diff = float(line.split("max_abs_diff= ")[1])
    assert max_diff <= 2 * _FLOAT32_EPS, f"max_abs_diff={max_diff} exceeds 2*float32_eps"


def test_cli_custom_bands(tmp_path: Path) -> None:
    """--band-a and --band-b select the correct bands."""
    # 3-band file; band 2 + band 3 = 1.0 exactly, band 1 is garbage.
    h, w = 3, 3
    band1 = np.full((h, w), 99.0, dtype=np.float32)
    band2 = np.full((h, w), 0.6, dtype=np.float32)
    band3 = np.float32(1.0) - band2
    data = np.stack([band1, band2, band3], axis=0)
    _write_tif(tmp_path / "test.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path), "--band-a", "2", "--band-b", "3"])
    assert proc.returncode == 0, proc.stderr

    line = proc.stdout.strip()
    mean_diff = float(line.split("mean_abs_diff= ")[1].split(" ")[0])
    assert mean_diff == pytest.approx(0.0, abs=1e-9)


def test_cli_missing_input_dir_exits_nonzero(tmp_path: Path) -> None:
    """Non-existent --input-dir causes non-zero exit."""
    proc = _run_script(["--input-dir", str(tmp_path / "does_not_exist")])
    assert proc.returncode != 0


def test_cli_all_nan_file_reports_nan(tmp_path: Path) -> None:
    """All-NaN file prints 'nan' for both diffs without crashing."""
    data = np.full((2, 3, 3), np.nan, dtype=np.float32)
    _write_tif(tmp_path / "fr_wheat_feat_2025_data_001.tif", data=data)

    proc = _run_script(["--input-dir", str(tmp_path)])
    assert proc.returncode == 0, proc.stderr
    assert "nan" in proc.stdout.lower()
