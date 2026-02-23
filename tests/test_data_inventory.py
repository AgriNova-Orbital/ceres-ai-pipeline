from __future__ import annotations

from datetime import date

import pytest


def test_inventory_reports_missing_7day_nodes() -> None:
    from modules.wheat_risk.data_inventory import compute_inventory

    observed = [date(2025, 1, 1), date(2025, 1, 15)]
    inv = compute_inventory(observed, cadence_days=7)

    assert inv.missing_dates == [date(2025, 1, 8)]
    assert inv.expected_nodes == 3
    assert inv.observed_nodes == 2


def test_inventory_reports_range_and_total_days() -> None:
    from modules.wheat_risk.data_inventory import compute_inventory

    observed = [date(2025, 1, 1), date(2025, 1, 22)]
    inv = compute_inventory(observed, cadence_days=7)

    assert inv.earliest_date == date(2025, 1, 1)
    assert inv.latest_date == date(2025, 1, 22)
    assert inv.total_days == 22


def test_inventory_rejects_empty_observed_dates() -> None:
    from modules.wheat_risk.data_inventory import compute_inventory

    with pytest.raises(ValueError, match="observed_dates must not be empty"):
        compute_inventory([], cadence_days=7)
