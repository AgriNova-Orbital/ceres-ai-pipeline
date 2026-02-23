from __future__ import annotations

import numpy as np


def test_binary_metrics_counts_and_scores() -> None:
    from modules.wheat_risk.metrics import binary_metrics_from_probs

    y_true = np.array([1, 1, 1, 0, 0, 0], dtype=np.int32)
    probs = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.2], dtype=np.float32)

    m = binary_metrics_from_probs(y_true, probs, threshold=0.65, beta=2.0)
    assert m["tp"] == 3
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["tn"] == 3
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f2"] == 1.0


def test_select_threshold_recall_first_with_precision_floor() -> None:
    from modules.wheat_risk.metrics import select_threshold_recall_first

    y_true = np.array([1, 1, 1, 0, 0, 0], dtype=np.int32)
    probs = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.2], dtype=np.float32)
    thresholds = [0.5, 0.65, 0.75]

    best = select_threshold_recall_first(
        y_true,
        probs,
        thresholds=thresholds,
        precision_floor=0.8,
        beta=2.0,
    )
    assert best["threshold"] == 0.65
    assert bool(best["meets_precision_floor"]) is True
    assert best["recall"] == 1.0
    assert best["precision"] == 1.0


def test_select_threshold_recall_first_falls_back_when_floor_unmet() -> None:
    from modules.wheat_risk.metrics import select_threshold_recall_first

    y_true = np.array([1, 1, 0, 0], dtype=np.int32)
    probs = np.array([0.6, 0.55, 0.9, 0.8], dtype=np.float32)
    thresholds = [0.5, 0.7, 0.85]

    best = select_threshold_recall_first(
        y_true,
        probs,
        thresholds=thresholds,
        precision_floor=0.6,
        beta=2.0,
    )
    assert best["threshold"] == 0.5
    assert bool(best["meets_precision_floor"]) is False
    assert best["recall"] == 1.0
