from __future__ import annotations

from typing import Any

from modules.ee_import import require_ee

from .config import PipelineConfig, StagePreset


def patch_tensor_shape(
    time_steps: int, channels: int, stage: StagePreset
) -> tuple[int, int, int, int]:
    """Return the expected (T, C, H, W) tensor shape for a single patch.

    H and W are derived from the stage preset's `patch_size_px`.
    """

    return (
        int(time_steps),
        int(channels),
        int(stage.patch_size_px),
        int(stage.patch_size_px),
    )


def sample_patch_grid(aoi: Any, cfg: PipelineConfig) -> Any:
    """EE-side stub: return patch centers on cropland.

    This is a placeholder for a future implementation that will:
    - identify cropland within `aoi`
    - sample point centers for patch extraction
    - return an `ee.FeatureCollection` of centers
    """

    ee = require_ee("patch grid sampling")
    # Stub: return an empty collection (no real sampling yet).
    return ee.FeatureCollection([])


def export_patch_tensors_to_drive(grid: Any, cfg: PipelineConfig) -> None:
    """EE-side stub: export patch tensors to Google Drive.

    This is a placeholder for a future implementation that will:
    - sample patch windows for each center feature
    - assemble a (T,C,H,W) tensor per sample
    - export to Drive in a ML-friendly format
    """

    require_ee("patch export")
    raise NotImplementedError("Patch tensor export is not implemented yet.")
