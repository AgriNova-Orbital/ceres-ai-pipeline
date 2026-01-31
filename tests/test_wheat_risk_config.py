import importlib
import importlib.util

import pytest


def test_wheat_risk_config_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.config") is not None


def test_stage_preset_presets() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.config") is not None
    mod = importlib.import_module("modules.wheat_risk.config")

    assert hasattr(mod, "StagePreset")
    StagePreset = mod.StagePreset

    assert hasattr(StagePreset, "stage1")
    assert hasattr(StagePreset, "stage2")
    assert hasattr(StagePreset, "stage3")

    p1 = StagePreset.stage1()
    assert (p1.scale_m, p1.patch_size_px) == (100, 32)

    p2 = StagePreset.stage2()
    assert (p2.scale_m, p2.patch_size_px) == (50, 64)

    p3 = StagePreset.stage3()
    assert (p3.scale_m, p3.patch_size_px) == (10, 96)


def test_pipeline_config_default_france_2025() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.config") is not None
    mod = importlib.import_module("modules.wheat_risk.config")

    assert hasattr(mod, "StagePreset")
    assert hasattr(mod, "PipelineConfig")

    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage2()
    assert hasattr(PipelineConfig, "default_france_2025")
    cfg = PipelineConfig.default_france_2025(stage)

    assert cfg.bbox == (-1.5, 47.0, 6.5, 50.9)
    assert isinstance(cfg.bbox, tuple)
    assert cfg.start_date == "2025-01-01"
    assert cfg.end_date == "2025-12-31"
    assert cfg.time_grain == "weekly"
    assert cfg.stage.scale_m == 50
    assert cfg.stage.patch_size_px == 64


def test_pipeline_config_bbox_is_detached_from_mutable_input() -> None:
    mod = importlib.import_module("modules.wheat_risk.config")
    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage1()
    bbox = [-1.5, 47.0, 6.5, 50.9]
    cfg = PipelineConfig(
        bbox=bbox, start_date="2025-01-01", end_date="2025-12-31", stage=stage
    )

    bbox[0] = 123.0
    assert cfg.bbox == (-1.5, 47.0, 6.5, 50.9)


def test_pipeline_config_bbox_validation_errors() -> None:
    mod = importlib.import_module("modules.wheat_risk.config")
    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage1()

    with pytest.raises(ValueError, match=r"bbox must have exactly 4 elements"):
        PipelineConfig(
            bbox=(1.0, 2.0, 3.0),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )

    with pytest.raises(ValueError, match=r"bbox\[1\] must be a real number"):
        PipelineConfig(
            bbox=(1.0, "nope", 2.0, 3.0),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )

    with pytest.raises(ValueError, match=r"min_lon < max_lon"):
        PipelineConfig(
            bbox=(10.0, 0.0, 10.0, 1.0),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )

    with pytest.raises(ValueError, match=r"min_lat < max_lat"):
        PipelineConfig(
            bbox=(0.0, 5.0, 1.0, 5.0),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )


def test_pipeline_config_rejects_non_iso_dates() -> None:
    mod = importlib.import_module("modules.wheat_risk.config")
    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage1()

    with pytest.raises(ValueError, match=r"start_date must be an ISO date"):
        PipelineConfig(
            bbox=(-1.5, 47.0, 6.5, 50.9),
            start_date="2025/01/01",
            end_date="2025-12-31",
            stage=stage,
        )

    with pytest.raises(ValueError, match=r"end_date must be an ISO date"):
        PipelineConfig(
            bbox=(-1.5, 47.0, 6.5, 50.9),
            start_date="2025-01-01",
            end_date="2025-12-31T00:00:00",
            stage=stage,
        )


def test_pipeline_config_rejects_inverted_date_range() -> None:
    mod = importlib.import_module("modules.wheat_risk.config")
    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage1()

    with pytest.raises(ValueError, match=r"start_date must be <= end_date"):
        PipelineConfig(
            bbox=(-1.5, 47.0, 6.5, 50.9),
            start_date="2025-12-31",
            end_date="2025-01-01",
            stage=stage,
        )


def test_pipeline_config_rejects_bbox_out_of_bounds() -> None:
    mod = importlib.import_module("modules.wheat_risk.config")
    StagePreset = mod.StagePreset
    PipelineConfig = mod.PipelineConfig

    stage = StagePreset.stage1()

    with pytest.raises(ValueError, match=r"longitude must be within"):
        PipelineConfig(
            bbox=(-181.0, 47.0, 6.5, 50.9),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )

    with pytest.raises(ValueError, match=r"latitude must be within"):
        PipelineConfig(
            bbox=(-1.5, -91.0, 6.5, 50.9),
            start_date="2025-01-01",
            end_date="2025-12-31",
            stage=stage,
        )
