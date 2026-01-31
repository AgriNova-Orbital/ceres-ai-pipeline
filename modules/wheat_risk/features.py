from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Mapping, Optional

from .collections import (
    S2_BANDS,
    get_chirps_daily,
    get_era5_land_hourly,
    get_modis_lst_8day,
    get_s1_grd,
    get_s2_sr,
)


RainSource = Literal["era5", "chirps", "stub"]
TempSource = Literal["era5", "stub"]
LstSource = Literal["modis", "stub"]


@lru_cache(maxsize=1)
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


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    """Defines the output band schema for weekly features."""

    feature_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.feature_names:
            raise ValueError("feature_names must not be empty")

        names: list[str] = []
        seen: set[str] = set()
        for i, name in enumerate(self.feature_names):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"feature_names[{i}] must be a non-empty str, got {name!r}"
                )
            n = name.strip()
            names.append(n)
            if n in seen:
                raise ValueError("feature_names must be unique")
            seen.add(n)

        object.__setattr__(self, "feature_names", tuple(names))

    @classmethod
    def default(cls) -> "FeatureSchema":
        # Keep names lowercase to avoid inconsistent band casing downstream.
        return cls(
            feature_names=(
                # Optical (S2 baseline)
                "ndvi",
                "ndmi",
                "nbr",
                # SAR (Sentinel-1)
                "s1_vv",
                "s1_vh",
                "s1_vh_vv",
                # Meteo
                "rain_mm",
                "temp_c_mean",
                "temp_c_max",
                # LST
                "lst_c",
            )
        )


@dataclass(frozen=True, slots=True)
class FeatureBuildConfig:
    """Configuration knobs for `build_weekly_features`.

    The defaults attempt to use real datasets, but can be set to stub constants.
    """

    max_cloud: Optional[float] = None

    rain_source: RainSource = "era5"
    temp_source: TempSource = "era5"
    lst_source: LstSource = "modis"

    # Stub constants (units are arbitrary; choose sane magnitudes)
    stub_rain_sum: float = 0.0
    stub_temp_mean: float = 15.0
    stub_temp_max: float = 25.0
    stub_lst_mean: float = 20.0

    def __post_init__(self) -> None:
        if self.max_cloud is not None:
            if not isinstance(self.max_cloud, (int, float)) or isinstance(
                self.max_cloud, bool
            ):
                raise ValueError("max_cloud must be a number (or None)")
            if not (0.0 <= float(self.max_cloud) <= 100.0):
                raise ValueError("max_cloud must be within [0, 100]")

        if self.rain_source not in ("era5", "chirps", "stub"):
            raise ValueError("rain_source must be one of ('era5', 'chirps', 'stub')")
        if self.temp_source not in ("era5", "stub"):
            raise ValueError("temp_source must be one of ('era5', 'stub')")
        if self.lst_source not in ("modis", "stub"):
            raise ValueError("lst_source must be one of ('modis', 'stub')")


def _coerce_cfg(cfg: Any) -> FeatureBuildConfig:
    if cfg is None:
        return FeatureBuildConfig()
    if isinstance(cfg, FeatureBuildConfig):
        return cfg
    if isinstance(cfg, Mapping):
        # Best-effort: accept dict-like config.
        return FeatureBuildConfig(**dict(cfg))
    raise TypeError(
        "cfg must be a FeatureBuildConfig, a mapping of config values, or None"
    )


def _end_exclusive_date(end_inclusive: str) -> Any:
    ee_any: Any = _import_ee()
    return ee_any.Date(end_inclusive).advance(1, "day")


def _weekly_s2_indices(aoi: Any, start: str, end: str, cfg: FeatureBuildConfig) -> Any:
    ee_any: Any = _import_ee()

    s2 = get_s2_sr().filterBounds(aoi).filterDate(start, _end_exclusive_date(end))
    if cfg.max_cloud is not None:
        s2 = s2.filterMetadata("CLOUDY_PIXEL_PERCENTAGE", "less_than", cfg.max_cloud)

    composite = s2.select(
        [S2_BANDS["red"], S2_BANDS["nir"], S2_BANDS["swir1"], S2_BANDS["swir2"]]
    ).median()

    red = composite.select(S2_BANDS["red"])
    nir = composite.select(S2_BANDS["nir"])
    swir1 = composite.select(S2_BANDS["swir1"])
    swir2 = composite.select(S2_BANDS["swir2"])

    ndvi = nir.subtract(red).divide(nir.add(red)).rename("ndvi")
    ndmi = nir.subtract(swir1).divide(nir.add(swir1)).rename("ndmi")
    nbr = nir.subtract(swir2).divide(nir.add(swir2)).rename("nbr")

    return ee_any.Image.cat([ndvi, ndmi, nbr]).clip(aoi)


def _weekly_s1_sar(aoi: Any, start: str, end: str) -> Any:
    ee_any: Any = _import_ee()

    s1 = (
        get_s1_grd()
        .filterBounds(aoi)
        .filterDate(start, _end_exclusive_date(end))
        .filter(ee_any.Filter.eq("instrumentMode", "IW"))
        .filter(ee_any.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee_any.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV", "VH"])
    )

    med = s1.median()
    vv = med.select("VV").rename("s1_vv")
    vh = med.select("VH").rename("s1_vh")
    vh_vv = vh.divide(vv).rename("s1_vh_vv")
    return ee_any.Image.cat([vv, vh, vh_vv]).clip(aoi)


def _weekly_meteo(aoi: Any, start: str, end: str, cfg: FeatureBuildConfig) -> Any:
    ee_any: Any = _import_ee()

    bands: list[Any] = []

    if cfg.rain_source == "stub":
        bands.append(ee_any.Image.constant(cfg.stub_rain_sum).rename("rain_mm"))
    elif cfg.rain_source == "chirps":
        rain = (
            get_chirps_daily()
            .filterBounds(aoi)
            .filterDate(start, _end_exclusive_date(end))
            .select("precipitation")
            .sum()
            .rename("rain_mm")
        )
        bands.append(rain)
    else:  # era5
        # total_precipitation is in meters of water; convert to mm.
        rain = (
            get_era5_land_hourly()
            .filterBounds(aoi)
            .filterDate(start, _end_exclusive_date(end))
            .select("total_precipitation")
            .sum()
            .multiply(1000.0)
            .rename("rain_mm")
        )
        bands.append(rain)

    if cfg.temp_source == "stub":
        bands.append(ee_any.Image.constant(cfg.stub_temp_mean).rename("temp_c_mean"))
        bands.append(ee_any.Image.constant(cfg.stub_temp_max).rename("temp_c_max"))
    else:
        temp = (
            get_era5_land_hourly()
            .filterBounds(aoi)
            .filterDate(start, _end_exclusive_date(end))
            .select("temperature_2m")
        )
        temp_mean = temp.mean().subtract(273.15).rename("temp_c_mean")
        temp_max = temp.max().subtract(273.15).rename("temp_c_max")
        bands.extend([temp_mean, temp_max])

    return ee_any.Image.cat(bands).clip(aoi)


def _weekly_lst(aoi: Any, start: str, end: str, cfg: FeatureBuildConfig) -> Any:
    ee_any: Any = _import_ee()

    if cfg.lst_source == "stub":
        return ee_any.Image.constant(cfg.stub_lst_mean).rename("lst_c").clip(aoi)

    lst_ic = (
        get_modis_lst_8day()
        .filterBounds(aoi)
        .filterDate(start, _end_exclusive_date(end))
        .select("LST_Day_1km")
    )
    # MOD11A2 LST scale factor is 0.02 Kelvin.
    lst_c = lst_ic.mean().multiply(0.02).subtract(273.15).rename("lst_c")
    return lst_c.clip(aoi)


def build_weekly_features(
    aoi: Any,
    start: str,
    end: str,
    cfg: Any = None,
    cropland_mask: Any = None,
) -> Any:
    """Build a weekly multi-source feature stack.

    Args:
        aoi: EE Geometry for the area of interest.
        start: Inclusive start date (YYYY-MM-DD).
        end: Inclusive end date (YYYY-MM-DD).
        cfg: FeatureBuildConfig or dict-like override.
        cropland_mask: Optional EE image mask to apply to all output bands.

    Returns:
        ee.Image with bands matching (at least) FeatureSchema.default().

    Notes:
        This function does not call ee.Initialize(). Callers must initialize EE
        in their runtime.
    """

    ee_any: Any = _import_ee()
    cfg_t = _coerce_cfg(cfg)

    optical = _weekly_s2_indices(aoi, start, end, cfg_t)
    sar = _weekly_s1_sar(aoi, start, end)
    meteo = _weekly_meteo(aoi, start, end, cfg_t)
    lst = _weekly_lst(aoi, start, end, cfg_t)

    img = ee_any.Image.cat([optical, sar, meteo, lst]).clip(aoi)
    if cropland_mask is not None:
        img = img.updateMask(cropland_mask)
    return img


def required_feature_names() -> tuple[str, ...]:
    """Return the canonical output band ordering used by this module."""

    return FeatureSchema.default().feature_names
