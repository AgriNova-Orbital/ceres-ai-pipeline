from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class MatrixCell:
    level_split: int
    sample_size: int
    patch_size: int
    step_size: int

    @property
    def level_name(self) -> str:
        return f"L{self.level_split}"

    @property
    def step_name(self) -> str:
        return f"S{self.sample_size}"

    @property
    def cell_name(self) -> str:
        return f"{self.level_name}-{self.step_name}"


def map_patch_size(*, base_patch: int, level_split: int) -> int:
    if base_patch <= 0:
        raise ValueError("base_patch must be > 0")
    if level_split <= 0:
        raise ValueError("level_split must be > 0")
    if base_patch % level_split != 0:
        raise ValueError(
            f"base_patch={base_patch} must be divisible by level_split={level_split}"
        )
    return int(base_patch // level_split)


def build_matrix(
    *, levels: Sequence[int], steps: Sequence[int], base_patch: int = 64
) -> list[MatrixCell]:
    if not levels:
        raise ValueError("levels must not be empty")
    if not steps:
        raise ValueError("steps must not be empty")

    cells: list[MatrixCell] = []
    for level in levels:
        if int(level) <= 0:
            raise ValueError("all levels must be > 0")
        patch = map_patch_size(base_patch=base_patch, level_split=int(level))
        for step in steps:
            if int(step) <= 0:
                raise ValueError("all steps must be > 0")
            cells.append(
                MatrixCell(
                    level_split=int(level),
                    sample_size=int(step),
                    patch_size=patch,
                    step_size=patch,
                )
            )
    return cells
