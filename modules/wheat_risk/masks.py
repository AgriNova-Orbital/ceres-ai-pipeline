from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

from .collections import CollectionIds
from .config import PipelineConfig
from .validation import validate_bbox as _validate_bbox


def _import_ee() -> Any:
    """Import Google Earth Engine lazily with a friendly error message."""

    try:
        return importlib.import_module("ee")
    except ImportError as e:
        raise ImportError(
            "Google Earth Engine (Python package `earthengine-api`) is required for this "
            "operation. Install it (e.g. `uv pip install earthengine-api`), then authenticate "
            "with `earthengine authenticate` and initialize with `ee.Initialize()` in your "
            "runtime."
        ) from e


def validate_bbox(bbox: Sequence[object]) -> tuple[float, float, float, float]:
    return _validate_bbox(bbox)


def build_aoi(bbox: Sequence[object]) -> Any:
    """Build an EE AOI rectangle from a bbox."""

    bbox_t = validate_bbox(bbox)

    ee_any: Any = _import_ee()
    return ee_any.Geometry.Rectangle(bbox_t)


def cropland_mask_worldcover(aoi: Any) -> Any:
    """Cropland mask from ESA WorldCover (class 40 == cropland)."""

    ee_any: Any = _import_ee()

    wc = (
        ee_any.ImageCollection(CollectionIds.WORLDCOVER)
        .filterBounds(aoi)
        .first()
        .select("Map")
    )
    return wc.eq(40).selfMask().clip(aoi)


def cropland_mask_dynamicworld(aoi: Any, start: str, end: str) -> Any:
    """Cropland mask from Dynamic World (label 4 == crops)."""

    ee_any: Any = _import_ee()

    dw = (
        ee_any.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(aoi)
        .filterDate(start, end)
        .select("label")
    )

    mode_label = dw.reduce(ee_any.Reducer.mode())
    return mode_label.eq(4).selfMask().clip(aoi)


def get_cropland_mask(cfg: PipelineConfig) -> Any:
    """Select cropland mask source based on config."""

    aoi = build_aoi(cfg.bbox)

    if cfg.use_dynamicworld:
        if not cfg.start_date or not cfg.end_date:
            raise ValueError(
                "Dynamic World cropland mask requires non-empty cfg.start_date and cfg.end_date"
            )
        return cropland_mask_dynamicworld(aoi, cfg.start_date, cfg.end_date)
    return cropland_mask_worldcover(aoi)
