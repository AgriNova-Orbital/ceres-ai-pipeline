"""Tests for masked/nodata handling in dataset_service._build_patch_and_save.

Covers the valid-ratio-based threshold, mask channel appended to X, and
finite-value guarantees for produced NPZ files.
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
