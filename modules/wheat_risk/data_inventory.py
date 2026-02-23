from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence


@dataclass(frozen=True, slots=True)
class InventoryResult:
    earliest_date: date
    latest_date: date
    total_days: int
    cadence_days: int
    expected_nodes: int
    observed_nodes: int
    missing_dates: list[date]
    missing_rate: float
    max_consecutive_missing: int


def _expected_nodes(*, start: date, end: date, cadence_days: int) -> list[date]:
    nodes: list[date] = []
    d = start
    step = timedelta(days=cadence_days)
    while d <= end:
        nodes.append(d)
        d += step
    return nodes


def _max_consecutive_true(flags: Sequence[bool]) -> int:
    best = 0
    run = 0
    for f in flags:
        if f:
            run += 1
            if run > best:
                best = run
        else:
            run = 0
    return best


def compute_inventory(
    observed_dates: Sequence[date], *, cadence_days: int = 7
) -> InventoryResult:
    if cadence_days <= 0:
        raise ValueError("cadence_days must be > 0")
    if not observed_dates:
        raise ValueError("observed_dates must not be empty")

    unique_obs = sorted(set(observed_dates))
    start = unique_obs[0]
    end = unique_obs[-1]
    total_days = (end - start).days + 1

    expected = _expected_nodes(start=start, end=end, cadence_days=cadence_days)
    obs_set = set(unique_obs)
    missing = [d for d in expected if d not in obs_set]

    expected_n = len(expected)
    observed_n = expected_n - len(missing)
    missing_rate = (len(missing) / expected_n) if expected_n > 0 else 0.0
    missing_flags = [d not in obs_set for d in expected]
    max_consecutive_missing = _max_consecutive_true(missing_flags)

    return InventoryResult(
        earliest_date=start,
        latest_date=end,
        total_days=total_days,
        cadence_days=cadence_days,
        expected_nodes=expected_n,
        observed_nodes=observed_n,
        missing_dates=missing,
        missing_rate=missing_rate,
        max_consecutive_missing=max_consecutive_missing,
    )
