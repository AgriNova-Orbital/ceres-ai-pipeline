from __future__ import annotations

import importlib


def test_experimental_sentinel2_module_importable() -> None:
    mod = importlib.import_module("experiments.sentinel2_stac_ml_pipeline")
    assert mod is not None


def test_experimental_sentinel2_has_main() -> None:
    mod = importlib.import_module("experiments.sentinel2_stac_ml_pipeline")
    assert callable(getattr(mod, "main", None))
