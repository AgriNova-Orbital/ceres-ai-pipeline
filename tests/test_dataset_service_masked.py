"""Tests for masked/nodata handling in dataset_service._build_patch_and_save.

Covers the valid-ratio-based threshold, mask channel appended to X, and
finite-value guarantees for produced NPZ files.

Production data profile (GEE export):
  - 11 bands: 10 Sentinel-2/feature bands + 1 risk band (last)
  - nodata = null: no nodata value is registered in the GeoTIFF; masked
    pixels are stored as NaN float32 values (standard GEE export behavior).
  - read_masks() therefore returns all-255 (all valid) for these files;
    validity is determined purely by np.isfinite().
"""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin


def _write_tif(
    path: Path,
    *,
    data: np.ndarray,
    nodata: float | None = None,
) -> None:
    """Write a single-file GeoTIFF with optional nodata value."""
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


# ---------------------------------------------------------------------------
# Partial-valid patches
# ---------------------------------------------------------------------------

def test_partial_valid_patch_is_retained(tmp_path: Path) -> None:
    """A patch with ~50% valid pixels should be kept (valid ratio > 0.05)."""
    from modules.services.dataset_service import _build_patch_and_save

    # Top-left 2x2 pixels are nodata; bottom-right 2x2 are valid.
    data = np.ones((3, 4, 4), dtype=np.float32) * 2.0
    data[:, :2, :2] = 0.0  # nodata region

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data, nodata=0.0)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=[1, 2],
            risk_band=3,
            examples_dir=examples,
        )

    assert npz_rel is not None, "Partially valid patch must not be dropped"

    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)
    # X: (T=1, C_feat+1=3, H=4, W=4)
    assert npz["X"].shape == (1, 3, 4, 4)
    # Feature values must all be finite (invalid pixels imputed to 0).
    assert np.all(np.isfinite(npz["X"])), "X must be fully finite"
    # M key is also present with matching shape.
    assert npz["M"].shape == (1, 1, 4, 4)
    # Mask channel (last channel of X) should have some valid pixels.
    mask_ch = npz["X"][0, 2, :, :]
    assert mask_ch.sum() > 0, "Some pixels should be marked valid"
    assert mask_ch.sum() < mask_ch.size, "Some pixels should be marked invalid (nodata region)"


def test_partial_valid_patch_mask_channel_matches_M(tmp_path: Path) -> None:
    """The mask channel appended to X must equal M along the channel axis."""
    from modules.services.dataset_service import _build_patch_and_save

    data = np.ones((3, 4, 4), dtype=np.float32) * 3.0
    data[:, 0, 0] = -9999.0  # single nodata corner

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data, nodata=-9999.0)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=[1, 2],
            risk_band=3,
            examples_dir=examples,
        )

    assert npz_rel is not None
    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)
    # Last channel of X equals M[:, 0, :, :].
    np.testing.assert_array_equal(npz["X"][:, -1:, :, :], npz["M"])


# ---------------------------------------------------------------------------
# Fully-invalid patches
# ---------------------------------------------------------------------------

def test_fully_invalid_patch_is_dropped(tmp_path: Path) -> None:
    """A patch where every pixel is nodata should be dropped (valid ratio = 0)."""
    from modules.services.dataset_service import _build_patch_and_save

    data = np.zeros((3, 4, 4), dtype=np.float32)

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data, nodata=0.0)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=[1, 2],
            risk_band=3,
            examples_dir=examples,
            min_valid_ratio=0.05,
        )

    assert npz_rel is None, "Fully invalid patch must be dropped"


def test_near_fully_invalid_patch_below_threshold_is_dropped(tmp_path: Path) -> None:
    """A patch with valid ratio below min_valid_ratio is dropped."""
    from modules.services.dataset_service import _build_patch_and_save

    # Only 1 of 16 pixels valid -> ratio=1/16=0.0625; threshold=0.10 => drop
    data = np.zeros((3, 4, 4), dtype=np.float32)
    data[:, 0, 0] = 1.0  # single valid pixel

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data, nodata=0.0)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=[1, 2],
            risk_band=3,
            examples_dir=examples,
            min_valid_ratio=0.10,
        )

    # 1/16 = 0.0625 < 0.10 → dropped
    assert npz_rel is None


# ---------------------------------------------------------------------------
# NaN-in-feature handling (no explicit nodata set)
# ---------------------------------------------------------------------------

def test_nan_features_are_imputed_to_zero(tmp_path: Path) -> None:
    """NaN feature values should be replaced with 0 in the saved X."""
    from modules.services.dataset_service import _build_patch_and_save

    data = np.ones((3, 4, 4), dtype=np.float32)
    data[0, 1, 1] = np.nan  # NaN in feature band 1

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_tif(tif, data=data, nodata=None)  # no nodata set

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=[1, 2],
            risk_band=3,
            examples_dir=examples,
        )

    assert npz_rel is not None
    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)
    # X must be entirely finite: NaN was imputed.
    assert np.all(np.isfinite(npz["X"])), "X must have no NaN/inf values"
    # The NaN pixel should be flagged as invalid in the mask channel.
    mask_ch = npz["X"][0, 2, :, :]  # (H, W)
    assert mask_ch[1, 1] == 0.0, "Pixel with NaN feature should be marked invalid"


# ---------------------------------------------------------------------------
# Missing-week placeholder
# ---------------------------------------------------------------------------

def test_missing_week_produces_zero_features_and_zero_mask(tmp_path: Path) -> None:
    """When a time-step source is None, X=0 and M=0 for that step."""
    from modules.services.dataset_service import _build_patch_and_save

    examples = tmp_path / "examples"
    examples.mkdir()

    # srcs=[None] simulates a missing week
    npz_rel = _build_patch_and_save(
        row=0,
        col=0,
        patch_size=4,
        srcs=[None],
        feature_bands=[1, 2],
        risk_band=3,
        examples_dir=examples,
        min_valid_ratio=0.0,  # allow zero valid ratio for this test
    )

    assert npz_rel is not None
    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)
    # Feature channels must all be zero.
    np.testing.assert_array_equal(npz["X"][0, :2, :, :], 0.0)
    # Mask channel must be all zero (no valid pixels for a missing week).
    np.testing.assert_array_equal(npz["M"][0, 0, :, :], 0.0)
    # y must be NaN for missing week.
    assert np.isnan(npz["y"][0])


# ---------------------------------------------------------------------------
# Production data profile: 11 bands, nodata=null, NaN-stored invalids (GEE)
# ---------------------------------------------------------------------------

def _write_gee_style_tif(path: Path, *, data: np.ndarray) -> None:
    """Write a GeoTIFF with no nodata value — the GEE export convention.

    With nodata=null, rasterio's read_masks() returns all-255 (all valid).
    Masked pixels are represented as NaN in the float32 data itself.
    """
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
    # Deliberately no 'nodata' kwarg — results in nodata=None (equivalent to
    # 'nodata=null' in GDAL/rasterio metadata), which is the GEE export convention.
    ) as ds:
        ds.write(data)


def test_gee_export_nodata_null_read_masks_returns_all_valid(tmp_path: Path) -> None:
    """Confirm that read_masks() is all-255 for nodata=null files (GEE profile).

    This validates the assumption that our validity logic must fall back to
    np.isfinite() rather than relying on read_masks() for this data.
    """
    bands, h, w = 11, 4, 4
    data = np.ones((bands, h, w), dtype=np.float32)
    data[:, :2, :2] = np.nan  # masked region (GEE convention)

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_gee_style_tif(tif, data=data)

    with rasterio.open(tif) as src:
        assert src.nodata is None, "GEE export has no nodata value"
        masks = src.read_masks()
        assert masks.min() == 255, "read_masks() must be all-255 for nodata=null"
        assert masks.max() == 255


def test_eleven_band_nodata_null_patch_X_shape_and_finite(tmp_path: Path) -> None:
    """11-band nodata=null file produces X with 10 feature + 1 mask = 11 channels."""
    from modules.services.dataset_service import _build_patch_and_save

    bands, h, w = 11, 4, 4
    data = np.ones((bands, h, w), dtype=np.float32) * 0.5
    data[:, :2, :2] = np.nan  # masked top-left quadrant

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_gee_style_tif(tif, data=data)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=list(range(1, 11)),  # bands 1-10 → 10 feature channels
            risk_band=11,
            examples_dir=examples,
        )

    assert npz_rel is not None, "Patch with 50% valid pixels must be retained"
    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)

    # X: (T=1, C_feat+1=11, H=4, W=4) — 10 feature bands + 1 mask channel
    assert npz["X"].shape == (1, 11, 4, 4), f"Unexpected X shape: {npz['X'].shape}"
    # X must be fully finite — NaN pixels are imputed to 0.
    assert np.all(np.isfinite(npz["X"])), "X must have no NaN or inf values"
    # M: (T=1, 1, H=4, W=4)
    assert npz["M"].shape == (1, 1, 4, 4)

    # Mask channel (last) must mark the NaN quadrant as invalid.
    mask_ch = npz["X"][0, 10, :, :]  # channel index 10 = the mask channel
    assert mask_ch[:2, :2].sum() == 0.0, "Top-left (NaN) pixels must be marked invalid"
    assert mask_ch[2:, 2:].sum() == 4.0, "Bottom-right (valid) pixels must be marked valid"


def test_eleven_band_nodata_null_nan_risk_yields_nan_y(tmp_path: Path) -> None:
    """When all risk-band pixels (band 11) are NaN, y must be NaN — no crash."""
    from modules.services.dataset_service import _build_patch_and_save

    bands, h, w = 11, 4, 4
    data = np.ones((bands, h, w), dtype=np.float32) * 0.5
    data[10, :, :] = np.nan  # all risk-band pixels are NaN (GEE masked region)

    tif = tmp_path / "fr_wheat_feat_2025_data_001.tif"
    _write_gee_style_tif(tif, data=data)

    examples = tmp_path / "examples"
    examples.mkdir()

    with rasterio.open(tif) as src:
        npz_rel = _build_patch_and_save(
            row=0,
            col=0,
            patch_size=4,
            srcs=[src],
            feature_bands=list(range(1, 11)),
            risk_band=11,
            examples_dir=examples,
        )

    assert npz_rel is not None
    npz = np.load(examples / "patch_r00000_c00000.npz", allow_pickle=False)
    # y must be NaN for the time step where risk band is fully NaN.
    assert np.isnan(npz["y"][0]), "y must be NaN when all risk pixels are NaN"
    # Feature part of X must still be finite (features are valid).
    assert np.all(np.isfinite(npz["X"][0, :10, :, :])), "Feature channels must be finite"


def test_eleven_band_nodata_null_run_build_end_to_end(tmp_path: Path) -> None:
    """End-to-end run_build with 11-band nodata=null files (production profile).

    Verifies that index.csv is populated and NPZ files have the expected
    schema: X shape (T, 11, H, W), M shape (T, 1, H, W), y shape (T,).
    """
    import csv as _csv
    from modules.services.dataset_service import run_build

    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir()

    bands, h, w = 11, 4, 4

    # Write two 11-band, nodata=null TIFFs with some NaN pixels.
    for idx, nan_frac in [(1, 0.25), (2, 0.25)]:
        data = np.ones((bands, h, w), dtype=np.float32) * float(idx)
        # First row masked for all bands — GEE export convention.
        data[:, 0, :] = np.nan
        _write_gee_style_tif(
            raw / f"fr_wheat_feat_2025_data_{idx:03d}.tif", data=data
        )

    run_build(
        input_dir=raw,
        output_dir=out,
        patch_size=2,
        step_size=2,
        expected_weeks=2,
        workers=1,
        gdal_cache_mb=32,
    )

    index_csv = out / "index.csv"
    assert index_csv.exists()

    with index_csv.open(newline="") as f:
        rows = list(_csv.DictReader(f))

    # 4x4 raster, patch=2, step=2 → 4 patches; all should pass (valid ratio > 0.05)
    assert len(rows) > 0, "index.csv must not be empty for partially valid GEE data"

    # Validate NPZ schema for the first sample.
    npz = np.load(out / rows[0]["npz_path"], allow_pickle=False)
    # T=2 weeks, C_feat+1=11 channels (10 feature + 1 mask), H=W=2
    assert npz["X"].shape == (2, 11, 2, 2), f"Unexpected X shape: {npz['X'].shape}"
    assert npz["y"].shape == (2,)
    assert npz["M"].shape == (2, 1, 2, 2)
    assert np.all(np.isfinite(npz["X"])), "X must be fully finite for GEE nodata=null data"
