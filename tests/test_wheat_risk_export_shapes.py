import importlib
import importlib.util


def test_wheat_risk_export_patches_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.export_patches") is not None


def test_patch_tensor_shape_matches_stage_patch_size() -> None:
    cfg_mod = importlib.import_module("modules.wheat_risk.config")
    exp_mod = importlib.import_module("modules.wheat_risk.export_patches")

    StagePreset = cfg_mod.StagePreset
    patch_tensor_shape = exp_mod.patch_tensor_shape

    for stage in (StagePreset.stage1(), StagePreset.stage2(), StagePreset.stage3()):
        shape = patch_tensor_shape(time_steps=12, channels=5, stage=stage)
        assert shape == (12, 5, stage.patch_size_px, stage.patch_size_px)
