import importlib
import importlib.util


def test_wheat_risk_collections_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.collections") is not None


def test_collection_ids_constants() -> None:
    mod = importlib.import_module("modules.wheat_risk.collections")
    CollectionIds = mod.CollectionIds

    assert CollectionIds.SENTINEL2_SR == "COPERNICUS/S2_SR_HARMONIZED"
    assert CollectionIds.SENTINEL1_GRD == "COPERNICUS/S1_GRD"
    assert CollectionIds.WORLDCOVER == "ESA/WorldCover/v200"
    assert CollectionIds.LANDSAT_8_C2_L2 == "LANDSAT/LC08/C02/T1_L2"
    assert CollectionIds.LANDSAT_9_C2_L2 == "LANDSAT/LC09/C02/T1_L2"
    assert CollectionIds.ERA5_LAND_HOURLY == "ECMWF/ERA5_LAND/HOURLY"
    assert CollectionIds.CHIRPS_DAILY == "UCSB-CHG/CHIRPS/DAILY"
    assert CollectionIds.MODIS_LST_8DAY == "MODIS/061/MOD11A2"


def test_band_maps_present() -> None:
    mod = importlib.import_module("modules.wheat_risk.collections")

    assert hasattr(mod, "S2_BANDS")
    assert hasattr(mod, "LANDSAT_L2_BANDS")

    s2 = mod.S2_BANDS
    ls = mod.LANDSAT_L2_BANDS

    assert s2["red"] == "B4"
    assert s2["nir"] == "B8"
    assert s2["swir1"] == "B11"
    assert s2["swir2"] == "B12"

    assert ls["red"] == "SR_B4"
    assert ls["nir"] == "SR_B5"
    assert ls["swir1"] == "SR_B6"
    assert ls["swir2"] == "SR_B7"


def test_helper_stubs_importable() -> None:
    mod = importlib.import_module("modules.wheat_risk.collections")

    assert callable(mod.get_s2_sr)
    assert callable(mod.get_landsat_l2)
    assert callable(mod.get_s1_grd)
    assert callable(mod.get_era5_land_hourly)
    assert callable(mod.get_chirps_daily)
    assert callable(mod.get_modis_lst_8day)
