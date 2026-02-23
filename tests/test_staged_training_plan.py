from __future__ import annotations


def test_nested_loop_order_level_outer_step_inner() -> None:
    from modules.wheat_risk.staged_training import build_matrix

    cells = build_matrix(levels=[1, 2, 4], steps=[100, 500, 2000], base_patch=64)
    got = [(c.level_split, c.sample_size) for c in cells]
    assert got == [
        (1, 100),
        (1, 500),
        (1, 2000),
        (2, 100),
        (2, 500),
        (2, 2000),
        (4, 100),
        (4, 500),
        (4, 2000),
    ]


def test_patch_size_mapping_from_base_patch() -> None:
    from modules.wheat_risk.staged_training import map_patch_size

    assert map_patch_size(base_patch=64, level_split=1) == 64
    assert map_patch_size(base_patch=64, level_split=2) == 32
    assert map_patch_size(base_patch=64, level_split=4) == 16
