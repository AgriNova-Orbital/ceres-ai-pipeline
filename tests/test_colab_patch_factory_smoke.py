from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_colab_patch_factory():
    path = Path("notebooks/colab_patch_factory_smoke.py")
    spec = importlib.util.spec_from_file_location("colab_patch_factory_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_raw_dir_points_to_drive_beta_folder() -> None:
    module = _load_colab_patch_factory()

    assert module.RAW_DIR.name == "wheat_data_v2.0-beta"


def test_partial_edge_tile_dimensions_are_valid() -> None:
    module = _load_colab_patch_factory()

    module.validate_dimensions_for_patching(
        filename="fr_wheat_feat_2025W36-0000000000-0000049920.tif",
        width=4642,
        height=9984,
        patch_sizes=(64, 128),
        stripe_height=256,
    )
