from __future__ import annotations

from typing import Iterable

import numpy as np


def _safe_div(num: float, den: float) -> float:
    if den <= 0.0:
        return 0.0
    return float(num / den)


def binary_metrics_from_probs(
    y_true: np.ndarray,
    probs: np.ndarray,
    *,
    threshold: float,
    beta: float = 2.0,
) -> dict[str, float | int]:
    if y_true.shape != probs.shape:
        raise ValueError("y_true and probs must have the same shape")
    if beta <= 0.0:
        raise ValueError("beta must be > 0")

    yt = np.asarray(y_true).astype(np.int32, copy=False)
    pr = np.asarray(probs).astype(np.float32, copy=False)
    pred = (pr >= float(threshold)).astype(np.int32, copy=False)

    tp = int(np.sum((pred == 1) & (yt == 1)))
    fp = int(np.sum((pred == 1) & (yt == 0)))
    tn = int(np.sum((pred == 0) & (yt == 0)))
    fn = int(np.sum((pred == 0) & (yt == 1)))

    precision = _safe_div(float(tp), float(tp + fp))
    recall = _safe_div(float(tp), float(tp + fn))
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    b2 = float(beta * beta)
    fbeta = _safe_div((1.0 + b2) * precision * recall, (b2 * precision) + recall)

    return {
        "threshold": float(threshold),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "f2" if float(beta) == 2.0 else "fbeta": fbeta,
    }


def select_threshold_recall_first(
    y_true: np.ndarray,
    probs: np.ndarray,
    *,
    thresholds: Iterable[float],
    precision_floor: float,
    beta: float = 2.0,
) -> dict[str, float | int | bool]:
    if precision_floor < 0.0 or precision_floor > 1.0:
        raise ValueError("precision_floor must be between 0 and 1")

    all_rows: list[dict[str, float | int]] = []
    for th in thresholds:
        row = binary_metrics_from_probs(y_true, probs, threshold=float(th), beta=beta)
        all_rows.append(row)
    if not all_rows:
        raise ValueError("thresholds must not be empty")

    floor_rows = [
        r for r in all_rows if float(r["precision"]) >= float(precision_floor)
    ]
    meets_floor = len(floor_rows) > 0
    candidates = floor_rows if meets_floor else all_rows

    def _key(r: dict[str, float | int]) -> tuple[float, float, float, float]:
        fbeta_key = float(r["f2"] if "f2" in r else r["fbeta"])
        # recall-first, then fbeta, then precision, then lower threshold
        return (
            float(r["recall"]),
            fbeta_key,
            float(r["precision"]),
            -float(r["threshold"]),
        )

    best = max(candidates, key=_key)
    out: dict[str, float | int | bool] = dict(best)
    out["meets_precision_floor"] = bool(meets_floor)
    out["precision_floor"] = float(precision_floor)
    return out
