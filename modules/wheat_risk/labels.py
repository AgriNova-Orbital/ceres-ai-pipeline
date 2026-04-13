from __future__ import annotations

import importlib
import math
from typing import Any, Mapping, overload

from .collections import get_era5_land_hourly, get_s2_sr


Cfg = Mapping[str, Any]


def sigmoid(x: float) -> float:
    """Numerically-stable logistic function.

    Returns values in [0, 1].

    Note: mathematically the logistic function is strictly within (0, 1) for finite
    x, but with floating-point arithmetic this implementation may return exactly
    0.0 or 1.0 for large-magnitude inputs.
    """

    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def gaussian(t: float, *, a: float, b: float, m: float, s: float) -> float:
    """Gaussian bump with baseline `a` and amplitude `b`.

    Defined so that gaussian(m) == a + b.
    """

    if s <= 0.0:
        raise ValueError("s must be > 0")

    z = (t - m) / s
    return a + b * math.exp(-0.5 * z * z)


def _import_ee() -> Any:
    """Import Google Earth Engine lazily with a friendly error message."""

    try:
        return importlib.import_module("ee")
    except ImportError as e:
        raise ImportError(
            "Google Earth Engine (Python package `earthengine-api`) is required for this "
            "operation. Install it (e.g. `uv add earthengine-api`), then authenticate "
            "with `earthengine authenticate` and initialize with `ee.Initialize()` in your "
            "runtime."
        ) from e


def _cfg_get(cfg: Cfg | None, key: str, default: Any) -> Any:
    if cfg is None:
        return default
    return cfg.get(key, default)


@overload
def gaussian_pheno_weekly(
    week_index: int | float,
    total_weeks: int | float,
    cfg: Cfg | None = None,
) -> float: ...


@overload
def gaussian_pheno_weekly(
    week_index: Any,
    total_weeks: Any,
    cfg: Cfg | None = None,
) -> Any: ...


def gaussian_pheno_weekly(
    week_index: Any,
    total_weeks: Any,
    cfg: Cfg | None = None,
) -> Any:
    """Phenology prior for a given week.

    Returns:
        Python float for numeric inputs, or ee.Number for Earth Engine inputs.
    """

    a = float(_cfg_get(cfg, "pheno_gaussian_a", 0.0))
    b = float(_cfg_get(cfg, "pheno_gaussian_b", 1.0))

    # Pure-python path.
    if (
        isinstance(week_index, (int, float))
        and not isinstance(week_index, bool)
        and isinstance(total_weeks, (int, float))
        and not isinstance(total_weeks, bool)
    ):
        # Peak mid-season by default.
        total_weeks_f = float(total_weeks)
        default_peak = (total_weeks_f - 1.0) / 2.0
        m = float(_cfg_get(cfg, "pheno_gaussian_peak_week", default_peak))

        default_sigma = max(1.0, total_weeks_f / 6.0)
        s = float(_cfg_get(cfg, "pheno_gaussian_sigma_weeks", default_sigma))
        return gaussian(float(week_index), a=a, b=b, m=m, s=s)

    ee_any: Any = _import_ee()

    tw = ee_any.Number(total_weeks)
    default_peak_ee = tw.subtract(1.0).divide(2.0)
    default_sigma_ee = tw.divide(6.0).max(1.0)

    sentinel = object()
    peak_cfg = _cfg_get(cfg, "pheno_gaussian_peak_week", sentinel)
    if peak_cfg is sentinel:
        m_ee = default_peak_ee
    else:
        m_ee = ee_any.Number(peak_cfg)

    sigma_cfg = _cfg_get(cfg, "pheno_gaussian_sigma_weeks", sentinel)
    if sigma_cfg is sentinel:
        s_ee = default_sigma_ee
    else:
        if isinstance(sigma_cfg, (int, float)) and float(sigma_cfg) <= 0.0:
            raise ValueError("pheno_gaussian_sigma_weeks must be > 0")
        s_ee = ee_any.Number(sigma_cfg)

    t = ee_any.Number(week_index)
    a_ee = ee_any.Number(a)
    b_ee = ee_any.Number(b)

    z = t.subtract(m_ee).divide(s_ee)
    bump = z.pow(2).multiply(-0.5).exp()
    return a_ee.add(b_ee.multiply(bump))


def _sigmoid_image(x: Any) -> Any:
    ee_any: Any = _import_ee()
    one = ee_any.Image.constant(1)
    return one.divide(x.multiply(-1).exp().add(1))


def r0_env_weekly(aoi: Any, start: str, end: str, cfg: Cfg | None = None) -> Any:
    """Environmental component of R0 (weekly).

    Produces an ee.Image with band `r0_env`.
    """

    ee_any: Any = _import_ee()

    source = str(_cfg_get(cfg, "r0_env_source", "era5_land")).lower()
    if source == "constant":
        val = float(_cfg_get(cfg, "r0_env_constant", 0.0))
        return ee_any.Image.constant(val).rename("r0_env").clip(aoi)

    if source != "era5_land":
        raise ValueError(
            "Unsupported r0_env_source (expected 'era5_land' or 'constant'): "
            f"{source!r}"
        )

    era5 = get_era5_land_hourly().filterBounds(aoi).filterDate(start, end)

    # ERA5-Land hourly uses Kelvin for temperature_2m and meters for total_precipitation.
    temp_c = era5.select("temperature_2m").mean().subtract(273.15)
    precip_mm = era5.select("total_precipitation").sum().multiply(1000.0)

    temp_mid_c = float(_cfg_get(cfg, "r0_env_temp_mid_c", 15.0))
    temp_scale_c = float(_cfg_get(cfg, "r0_env_temp_scale_c", 5.0))
    precip_mid_mm = float(_cfg_get(cfg, "r0_env_precip_mid_mm", 10.0))
    precip_scale_mm = float(_cfg_get(cfg, "r0_env_precip_scale_mm", 5.0))

    if temp_scale_c <= 0.0:
        raise ValueError("r0_env_temp_scale_c must be > 0")
    if precip_scale_mm <= 0.0:
        raise ValueError("r0_env_precip_scale_mm must be > 0")

    temp_score = _sigmoid_image(temp_c.subtract(temp_mid_c).divide(temp_scale_c))
    precip_score = _sigmoid_image(
        precip_mm.subtract(precip_mid_mm).divide(precip_scale_mm)
    )

    r0_env = temp_score.multiply(precip_score).rename("r0_env").clip(aoi)
    return r0_env


def _mask_s2_sr_qa60(image: Any) -> Any:
    qa = image.select("QA60")
    cloud = 1 << 10
    cirrus = 1 << 11
    mask = qa.bitwiseAnd(cloud).eq(0).And(qa.bitwiseAnd(cirrus).eq(0))
    return image.updateMask(mask)


def remote_stress_weekly(
    aoi: Any,
    start: str,
    end: str,
    cfg: Cfg | None = None,
    cropland_mask: Any | None = None,
) -> Any:
    """Remote-sensing stress proxy (weekly).

    Produces an ee.Image with band `remote_stress`.
    """

    ee_any: Any = _import_ee()

    max_cloud = float(_cfg_get(cfg, "s2_max_cloud", _cfg_get(cfg, "max_cloud", 60.0)))
    apply_qa60 = bool(_cfg_get(cfg, "s2_apply_qa60", True))

    s2 = (
        get_s2_sr()
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee_any.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
    )

    if apply_qa60:
        s2 = s2.map(_mask_s2_sr_qa60)

    composite = s2.median().clip(aoi)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")

    ndvi_min = float(_cfg_get(cfg, "ndvi_min", 0.2))
    ndvi_max = float(_cfg_get(cfg, "ndvi_max", 0.8))
    if ndvi_max <= ndvi_min:
        raise ValueError("ndvi_max must be > ndvi_min")

    ndvi_scaled = ndvi.subtract(ndvi_min).divide(ndvi_max - ndvi_min).clamp(0, 1)
    remote_stress = (
        ee_any.Image.constant(1).subtract(ndvi_scaled).rename("remote_stress")
    )

    if cropland_mask is not None:
        remote_stress = remote_stress.updateMask(cropland_mask)

    return remote_stress.clip(aoi)


def risk_weekly(
    aoi: Any,
    start: str,
    end: str,
    cfg: Cfg | None = None,
    *,
    cropland_mask: Any | None = None,
    week_index: Any | None = None,
    total_weeks: Any | None = None,
) -> Any:
    """Weekly risk label image.

    Components:
    - phenology prior (Gaussian)
    - environmental suitability proxy (r0_env)
    - remote-sensing stress proxy (remote_stress)

    Returns an ee.Image with band `risk`.
    """

    if (week_index is None) != (total_weeks is None):
        raise ValueError("week_index and total_weeks must be provided together")

    ee_any: Any = _import_ee()

    w1 = float(_cfg_get(cfg, "w1", 1.0))
    w2 = float(_cfg_get(cfg, "w2", 1.0))
    w3 = float(_cfg_get(cfg, "w3", 1.0))
    bias = float(_cfg_get(cfg, "risk_bias", 0.0))

    prior: Any
    if week_index is None and total_weeks is None:
        prior = 0.0
    else:
        prior = gaussian_pheno_weekly(week_index, total_weeks, cfg)

    env = r0_env_weekly(aoi, start, end, cfg).select("r0_env")
    stress = remote_stress_weekly(
        aoi, start, end, cfg, cropland_mask=cropland_mask
    ).select("remote_stress")

    logits = (
        env.multiply(w2)
        .add(stress.multiply(w3))
        .add(ee_any.Image.constant(prior).multiply(w1))
        .add(bias)
    )

    risk = _sigmoid_image(logits).rename("risk")
    if cropland_mask is not None:
        risk = risk.updateMask(cropland_mask)
    return risk.clip(aoi)
