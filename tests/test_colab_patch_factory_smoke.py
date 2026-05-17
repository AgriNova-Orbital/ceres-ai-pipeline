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


def test_smoke_factory_has_no_import_time_colab_side_effects() -> None:
    source = Path("notebooks/colab_patch_factory_smoke.py").read_text()
    pre_main = source.split('if __name__ == "__main__":')[0]

    assert "ensure_imports()\n\nimport rasterio" not in source
    assert "\nensure_imports()\n" not in pre_main
    assert "\nmount_drive()\n" not in pre_main


def test_smoke_factory_uses_drive_local_atomic_tmp_and_ceil_progress() -> None:
    source = Path("notebooks/colab_patch_factory_smoke.py").read_text()

    assert 'tmp_path = final_path.with_suffix(".tmp.npz")' in source
    assert "tmp_path.replace(final_path)" in source
    assert "shutil.move" not in source
    assert "math.ceil(tile.height / STRIPE_HEIGHT)" in source
