from __future__ import annotations

import numpy as np


def test_fill_missing_weeks_old_to_new():
    from scripts.build_npz_dataset_from_geotiffs import fill_missing_weeks

    # Oldest->newest should be 3,2,1 (since 1 is newest in reverse scheme)
    items = [
        (-3, "w003"),
        (-1, "w001"),
    ]
    filled, mask = fill_missing_weeks(items, expected_len=3)
    assert filled == ["w003", None, "w001"]
    assert mask.tolist() == [True, False, True]


def test_apply_mask_to_loss():
    # sanity: how we'll treat NaNs later
    y = np.array([0.1, np.nan, 0.3], dtype=np.float32)
    mask = ~np.isnan(y)
    assert mask.tolist() == [True, False, True]
