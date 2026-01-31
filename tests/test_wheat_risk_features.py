import importlib
import importlib.util

import pytest


def test_wheat_risk_features_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.features") is not None


def test_feature_schema_default_includes_required_feature_names() -> None:
    mod = importlib.import_module("modules.wheat_risk.features")
    FeatureSchema = mod.FeatureSchema

    schema = FeatureSchema.default()
    names = schema.feature_names

    assert isinstance(names, tuple)
    for req in (
        "ndvi",
        "ndmi",
        "s1_vv",
        "s1_vh",
        "rain_mm",
        "temp_c_mean",
        "temp_c_max",
        "lst_c",
    ):
        assert req in names

    # Guard against legacy names lingering in the default schema.
    for legacy in ("rain_sum", "temp_mean", "temp_max", "lst_mean"):
        assert legacy not in names


def test_feature_schema_validation_rejects_empty_and_duplicates() -> None:
    mod = importlib.import_module("modules.wheat_risk.features")
    FeatureSchema = mod.FeatureSchema

    with pytest.raises(ValueError, match=r"feature_names must not be empty"):
        FeatureSchema(feature_names=())

    with pytest.raises(ValueError, match=r"feature_names must be unique"):
        FeatureSchema(feature_names=("ndvi", "ndvi"))


def test_build_weekly_features_is_exposed() -> None:
    mod = importlib.import_module("modules.wheat_risk.features")
    assert callable(mod.build_weekly_features)
