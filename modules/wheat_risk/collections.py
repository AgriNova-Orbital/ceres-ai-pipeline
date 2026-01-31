from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping


class CollectionIds:
    SENTINEL2_SR: str = "COPERNICUS/S2_SR_HARMONIZED"
    SENTINEL1_GRD: str = "COPERNICUS/S1_GRD"
    # NOTE: "ESA/WorldCover" is a folder. Use a concrete version collection.
    WORLDCOVER: str = "ESA/WorldCover/v200"

    # Landsat Collection 2 Level 2 surface reflectance (separate L8/L9 IDs).
    LANDSAT_8_C2_L2: str = "LANDSAT/LC08/C02/T1_L2"
    LANDSAT_9_C2_L2: str = "LANDSAT/LC09/C02/T1_L2"

    ERA5_LAND_HOURLY: str = "ECMWF/ERA5_LAND/HOURLY"
    CHIRPS_DAILY: str = "UCSB-CHG/CHIRPS/DAILY"

    # MODIS Terra LST 8-day (Collection 6.1)
    MODIS_LST_8DAY: str = "MODIS/061/MOD11A2"


# Minimal band name maps used by vegetation/water/burn indices later.
S2_BANDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "red": "B4",
        "nir": "B8",
        "swir1": "B11",
        "swir2": "B12",
    }
)

LANDSAT_L2_BANDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "red": "SR_B4",
        "nir": "SR_B5",
        "swir1": "SR_B6",
        "swir2": "SR_B7",
    }
)


def get_s2_sr() -> Any:
    import ee

    ee_any: Any = ee

    return ee_any.ImageCollection(CollectionIds.SENTINEL2_SR)


def get_landsat_l2(*, satellites: Iterable[int] = (8, 9)) -> Any:
    import ee

    ee_any: Any = ee

    satellites = tuple(satellites)

    collections: list[Any] = []
    for sat in satellites:
        if sat == 8:
            collections.append(ee_any.ImageCollection(CollectionIds.LANDSAT_8_C2_L2))
        elif sat == 9:
            collections.append(ee_any.ImageCollection(CollectionIds.LANDSAT_9_C2_L2))
        else:
            raise ValueError(
                f"Unsupported Landsat satellite: {sat!r} (expected 8 or 9)"
            )

    if not collections:
        raise ValueError("satellites must include at least one of (8, 9)")

    merged = collections[0]
    for c in collections[1:]:
        merged = merged.merge(c)
    return merged


def get_s1_grd() -> Any:
    import ee

    ee_any: Any = ee

    return ee_any.ImageCollection(CollectionIds.SENTINEL1_GRD)


def get_era5_land_hourly() -> Any:
    import ee

    ee_any: Any = ee

    return ee_any.ImageCollection(CollectionIds.ERA5_LAND_HOURLY)


def get_chirps_daily() -> Any:
    import ee

    ee_any: Any = ee

    return ee_any.ImageCollection(CollectionIds.CHIRPS_DAILY)


def get_modis_lst_8day() -> Any:
    import ee

    ee_any: Any = ee

    return ee_any.ImageCollection(CollectionIds.MODIS_LST_8DAY)
