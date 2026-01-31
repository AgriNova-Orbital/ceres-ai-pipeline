from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .validation import validate_bbox, validate_date_range


@dataclass(frozen=True, slots=True)
class StagePreset:
    scale_m: int
    patch_size_px: int

    @classmethod
    def stage1(cls) -> "StagePreset":
        return cls(scale_m=100, patch_size_px=32)

    @classmethod
    def stage2(cls) -> "StagePreset":
        return cls(scale_m=50, patch_size_px=64)

    @classmethod
    def stage3(cls) -> "StagePreset":
        return cls(scale_m=10, patch_size_px=96)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    # [min_lon, min_lat, max_lon, max_lat]
    bbox: tuple[float, float, float, float]
    start_date: str
    end_date: str
    stage: StagePreset
    time_grain: str = "weekly"

    # Optional knobs (for later pipeline stages)
    sample_count: Optional[int] = None
    seed: Optional[int] = None
    drive_folder: Optional[str] = None
    max_cloud: Optional[float] = None
    use_dynamicworld: Optional[bool] = None

    def __post_init__(self) -> None:
        bbox = validate_bbox(self.bbox)

        start_date = self.start_date
        end_date = self.end_date
        if start_date == "" and end_date == "":
            # Allow unset dates for pipeline stages that do not require time filtering.
            pass
        else:
            start_date, end_date = validate_date_range(start_date, end_date)

        # Ensure values are immutable and detached from external mutable sequences.
        object.__setattr__(self, "bbox", bbox)
        object.__setattr__(self, "start_date", start_date)
        object.__setattr__(self, "end_date", end_date)

    @classmethod
    def default_france_2025(cls, stage: StagePreset) -> "PipelineConfig":
        return cls(
            bbox=(-1.5, 47.0, 6.5, 50.9),
            start_date="2025-01-01",
            end_date="2025-12-31",
            time_grain="weekly",
            stage=stage,
        )
