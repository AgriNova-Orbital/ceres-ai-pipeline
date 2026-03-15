"""Tests for modules/services/ndvi_forecast_service.py.

Covers:
- build_forecast_patches: X/y/M shapes, mask channel, NaN targets, sliding windows
- run_ndvi_forecast_build: full end-to-end build, index.csv, NPZ format
- CLI (scripts/build_ndvi_forecast_dataset.py): argument handling, exit codes
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tif(
    path: Path,
    *,
    data: np.ndarray,
    nodata: float | None = None,
) -> None:
    """Write a float32 GeoTIFF (nodata=None → GEE-style NaN-in-value)."""
    c, h, w = data.shape
    kw: dict = dict(
        driver="GTiff",
        height=h,
        width=w,
        count=c,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
    )
    if nodata is not None:
        kw["nodata"] = nodata
    with rasterio.open(path, "w", **kw) as ds:
        ds.write(data)


def _make_week_tifs(
    tmp_dir: Path,
    *,
    n_weeks: int,
    h: int = 8,
    w: int = 8,
    n_bands: int = 11,  # 10 feature bands + 1 risk band (last band)
    ndvi_value: float = 0.5,
    risk_value: float = 0.5,
    nan_mask: np.ndarray | None = None,
) -> None:
    """Create ``n_weeks`` GeoTIFFs in *tmp_dir* using the production file-naming convention."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, n_weeks + 1):
        data = np.full((n_bands, h, w), ndvi_value, dtype=np.float32)
        data[-1, :, :] = risk_value  # risk band
        if nan_mask is not None:
            data[:, nan_mask] = np.nan
        _write_tif(tmp_dir / f"fr_wheat_feat_2025_data_{i:03d}.tif", data=data)


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/build_ndvi_forecast_dataset.py", *args],
        check=False,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        text=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Unit tests: build_forecast_patches
# ---------------------------------------------------------------------------

class TestBuildForecastPatches:
    def test_x_shape(self, tmp_path: Path) -> None:
        """X must be (W, C_feat+1, H_p, W_p)."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        h, w, n_bands, window = 8, 8, 11, 4
        _make_week_tifs(tmp_path / "in", n_weeks=6, h=h, w=w, n_bands=n_bands)
        ex = tmp_path / "ex"
        ex.mkdir()

        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=list(range(1, n_bands)),  # bands 1..10
                ndvi_band=1,
                patch_size=4,
                window_size=window,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            assert len(results) > 0
            npz = np.load(ex / Path(results[0]).name)
            assert npz["X"].shape == (window, n_bands - 1 + 1, 4, 4)  # C_feat + 1 mask
        finally:
            for s in srcs:
                s.close()

    def test_y_is_ndvi_of_next_week(self, tmp_path: Path) -> None:
        """y must be the mean NDVI (band 1) of the *next* week."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        ndvi_val = 0.72
        _make_week_tifs(tmp_path / "in", n_weeks=5, n_bands=2, ndvi_value=ndvi_val)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=[1],
                ndvi_band=1,
                patch_size=4,
                window_size=3,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            # Every target week has NDVI = ndvi_val for all pixels.
            for rel in results:
                npz = np.load(ex / Path(rel).name)
                assert float(npz["y"]) == pytest.approx(ndvi_val, abs=1e-5)
        finally:
            for s in srcs:
                s.close()

    def test_m_is_last_x_channel(self, tmp_path: Path) -> None:
        """Standalone M must match the last channel of X."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        _make_week_tifs(tmp_path / "in", n_weeks=4, n_bands=3)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=[1, 2],
                ndvi_band=1,
                patch_size=4,
                window_size=2,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            for rel in results:
                npz = np.load(ex / Path(rel).name)
                np.testing.assert_array_equal(npz["M"], npz["X"][:, -1:, :, :])
        finally:
            for s in srcs:
                s.close()

    def test_nan_pixels_imputed_to_zero_in_x(self, tmp_path: Path) -> None:
        """NaN pixels must be imputed to 0 in X, with mask = 0 at those positions."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        h, w = 4, 4
        nan_mask = np.zeros((h, w), dtype=bool)
        nan_mask[0, 0] = True  # only top-left pixel is NaN
        _make_week_tifs(tmp_path / "in", n_weeks=4, h=h, w=w, n_bands=2, nan_mask=nan_mask)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=[1],
                ndvi_band=1,
                patch_size=4,
                window_size=2,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            for rel in results:
                npz = np.load(ex / Path(rel).name)
                # NaN pixel [0,0] should be 0 in X feature bands
                assert float(npz["X"][0, 0, 0, 0]) == 0.0
                # Mask should be 0 at [0,0]
                assert float(npz["M"][0, 0, 0, 0]) == 0.0
                # Valid pixel [0,1] should have mask = 1
                assert float(npz["M"][0, 0, 0, 1]) == 1.0
        finally:
            for s in srcs:
                s.close()

    def test_all_nan_target_week_gives_nan_y(self, tmp_path: Path) -> None:
        """When target week is all-NaN, y must be NaN."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        h, w, n_weeks = 4, 4, 4
        # All weeks have valid data except the last (target for window starting at t=0)
        for i in range(1, n_weeks + 1):
            data = np.full((2, h, w), 0.5, dtype=np.float32)
            if i == n_weeks:
                data[:] = np.nan  # last week all NaN
            _write_tif(
                tmp_path / f"fr_wheat_feat_2025_data_{i:03d}.tif",
                data=data,
            )
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted(tmp_path.glob("*.tif"))]
        window = n_weeks - 1  # exactly 1 target week: the all-NaN one
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=[1],
                ndvi_band=1,
                patch_size=4,
                window_size=window,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            assert len(results) == 1
            npz = np.load(ex / Path(results[0]).name)
            assert np.isnan(float(npz["y"]))
        finally:
            for s in srcs:
                s.close()

    def test_min_valid_ratio_filters_low_valid_patches(self, tmp_path: Path) -> None:
        """Patches below min_valid_ratio must be skipped."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        h, w = 4, 4
        # Make 99% of pixels NaN (only 1 valid pixel at [3,3]).
        nan_mask = np.ones((h, w), dtype=bool)
        nan_mask[3, 3] = False
        _make_week_tifs(tmp_path / "in", n_weeks=4, h=h, w=w, n_bands=2, nan_mask=nan_mask)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            # With 1 valid out of 16 pixels, valid ratio = 1/16 ≈ 0.0625.
            # min_valid_ratio=0.10 should discard; min_valid_ratio=0.05 should keep.
            results_discard = build_forecast_patches(
                srcs=srcs, feature_bands=[1], ndvi_band=1, patch_size=4,
                window_size=2, examples_dir=ex, row=0, col=0, min_valid_ratio=0.10,
            )
            results_keep = build_forecast_patches(
                srcs=srcs, feature_bands=[1], ndvi_band=1, patch_size=4,
                window_size=2, examples_dir=ex, row=0, col=0, min_valid_ratio=0.05,
            )
            assert len(results_discard) == 0
            assert len(results_keep) > 0
        finally:
            for s in srcs:
                s.close()

    def test_none_src_produces_zero_features_and_zero_mask(self, tmp_path: Path) -> None:
        """A ``None`` src (missing week) must contribute all-zero X and all-zero M."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        _make_week_tifs(tmp_path / "in", n_weeks=3, n_bands=2)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs: list = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        # Insert a None in the middle to simulate a missing week.
        srcs_with_gap: list = [srcs[0], None, srcs[1], srcs[2]]
        try:
            results = build_forecast_patches(
                srcs=srcs_with_gap,
                feature_bands=[1],
                ndvi_band=1,
                patch_size=4,
                window_size=2,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            # Window starting at t=0 (week 0=valid, week 1=None): mask for week 1 = 0.
            npz = np.load(ex / Path(results[0]).name)
            np.testing.assert_array_equal(npz["M"][1], np.zeros_like(npz["M"][1]))
            np.testing.assert_array_equal(npz["X"][1, :-1], np.zeros_like(npz["X"][1, :-1]))
        finally:
            for s in srcs:
                s.close()

    def test_sliding_window_count(self, tmp_path: Path) -> None:
        """Number of windows per patch = num_weeks − window_size."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        num_weeks, window = 8, 3
        _make_week_tifs(tmp_path / "in", n_weeks=num_weeks, n_bands=2)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs, feature_bands=[1], ndvi_band=1, patch_size=4,
                window_size=window, examples_dir=ex, row=0, col=0, min_valid_ratio=0.0,
            )
            assert len(results) == num_weeks - window
        finally:
            for s in srcs:
                s.close()

    def test_risk_band_excluded_from_x(self, tmp_path: Path) -> None:
        """The risk band (last band) must NOT appear in X features."""
        from modules.services.ndvi_forecast_service import build_forecast_patches

        n_bands = 11
        n_feat = n_bands - 1  # 10 feature bands
        _make_week_tifs(tmp_path / "in", n_weeks=5, n_bands=n_bands)
        ex = tmp_path / "ex"
        ex.mkdir()
        srcs = [rasterio.open(p) for p in sorted((tmp_path / "in").glob("*.tif"))]
        try:
            results = build_forecast_patches(
                srcs=srcs,
                feature_bands=list(range(1, n_bands)),  # bands 1..10
                ndvi_band=1,
                patch_size=4,
                window_size=2,
                examples_dir=ex,
                row=0,
                col=0,
                min_valid_ratio=0.0,
            )
            npz = np.load(ex / Path(results[0]).name)
            # X has n_feat feature channels + 1 mask channel.
            assert npz["X"].shape[1] == n_feat + 1
        finally:
            for s in srcs:
                s.close()


# ---------------------------------------------------------------------------
# Integration test: run_ndvi_forecast_build
# ---------------------------------------------------------------------------

class TestRunNdviForecastBuild:
    def test_creates_index_csv_and_examples(self, tmp_path: Path) -> None:
        """Full build produces index.csv with correct content and NPZ files."""
        from modules.services.ndvi_forecast_service import run_ndvi_forecast_build

        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        _make_week_tifs(in_dir, n_weeks=6, h=16, w=16, n_bands=11)

        run_ndvi_forecast_build(
            input_dir=in_dir,
            output_dir=out_dir,
            patch_size=4,
            step_size=4,
            window_size=3,
            min_valid_ratio=0.0,
            workers=1,
        )

        assert (out_dir / "index.csv").exists()
        assert (out_dir / "examples").is_dir()

        with open(out_dir / "index.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert all(r["npz_path"].startswith("examples/") for r in rows)

        # Every referenced NPZ must exist.
        for row in rows:
            npz_path = out_dir / row["npz_path"]
            assert npz_path.exists(), f"Missing {npz_path}"

    def test_npz_always_finite(self, tmp_path: Path) -> None:
        """X and M in built NPZ must be fully finite (no NaN/inf)."""
        from modules.services.ndvi_forecast_service import run_ndvi_forecast_build

        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        # Mix of valid and NaN pixels.
        nan_mask = np.zeros((8, 8), dtype=bool)
        nan_mask[0:4, 0:4] = True
        _make_week_tifs(in_dir, n_weeks=5, h=8, w=8, n_bands=3, nan_mask=nan_mask)

        run_ndvi_forecast_build(
            input_dir=in_dir, output_dir=out_dir,
            patch_size=4, step_size=4, window_size=2,
            min_valid_ratio=0.0, workers=1,
        )

        for npz_path in (out_dir / "examples").glob("*.npz"):
            npz = np.load(npz_path)
            assert np.isfinite(npz["X"]).all(), f"X has non-finite values in {npz_path.name}"
            assert np.isfinite(npz["M"]).all(), f"M has non-finite values in {npz_path.name}"

    def test_skip_existing_returns_early(self, tmp_path: Path) -> None:
        """With skip_existing=True and existing index.csv, build is skipped."""
        from modules.services.ndvi_forecast_service import run_ndvi_forecast_build

        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        # Write a sentinel index.csv so the build thinks it's done.
        sentinel = out_dir / "index.csv"
        sentinel.write_text("npz_path\n")

        _make_week_tifs(in_dir, n_weeks=5, n_bands=2)

        run_ndvi_forecast_build(
            input_dir=in_dir, output_dir=out_dir,
            patch_size=4, step_size=4, window_size=2,
            workers=1, skip_existing=True,
        )

        # index.csv must still only have the header (no examples written).
        with open(sentinel) as f:
            content = f.read()
        assert content == "npz_path\n"

    def test_window_size_too_large_raises(self, tmp_path: Path) -> None:
        """window_size >= T must raise RuntimeError."""
        from modules.services.ndvi_forecast_service import run_ndvi_forecast_build

        in_dir = tmp_path / "in"
        in_dir.mkdir()
        _make_week_tifs(in_dir, n_weeks=3, n_bands=2)

        with pytest.raises(RuntimeError, match="Not enough weeks"):
            run_ndvi_forecast_build(
                input_dir=in_dir, output_dir=tmp_path / "out",
                patch_size=4, step_size=4, window_size=3, workers=1,
            )

    def test_index_csv_sorted(self, tmp_path: Path) -> None:
        """NPZ paths in index.csv must be lexicographically sorted."""
        from modules.services.ndvi_forecast_service import run_ndvi_forecast_build

        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        _make_week_tifs(in_dir, n_weeks=6, h=8, w=8, n_bands=2)

        run_ndvi_forecast_build(
            input_dir=in_dir, output_dir=out_dir,
            patch_size=4, step_size=4, window_size=2,
            min_valid_ratio=0.0, workers=1,
        )

        with open(out_dir / "index.csv") as f:
            rows = list(csv.DictReader(f))
        paths = [r["npz_path"] for r in rows]
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# CLI tests (subprocess)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_end_to_end(self, tmp_path: Path) -> None:
        """CLI produces index.csv and NPZ files for valid inputs."""
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out_dir = tmp_path / "out"
        _make_week_tifs(in_dir, n_weeks=5, h=8, w=8, n_bands=3)

        proc = _run_script([
            "--input-dir", str(in_dir),
            "--output-dir", str(out_dir),
            "--window-size", "2",
            "--patch-size", "4",
            "--step-size", "4",
            "--min-valid-ratio", "0.0",
            "--workers", "1",
        ])
        assert proc.returncode == 0, proc.stderr
        assert (out_dir / "index.csv").exists()

    def test_cli_missing_input_dir_exits_nonzero(self, tmp_path: Path) -> None:
        """Non-existent --input-dir causes non-zero exit."""
        proc = _run_script([
            "--input-dir", str(tmp_path / "does_not_exist"),
            "--output-dir", str(tmp_path / "out"),
        ])
        assert proc.returncode != 0

    def test_cli_window_size_2_is_minimum(self, tmp_path: Path) -> None:
        """window_size=1 (< minimum) raises an error."""
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        _make_week_tifs(in_dir, n_weeks=5, n_bands=2)
        proc = _run_script([
            "--input-dir", str(in_dir),
            "--output-dir", str(tmp_path / "out"),
            "--window-size", "1",
            "--patch-size", "4",
            "--step-size", "4",
            "--workers", "1",
        ])
        assert proc.returncode != 0
