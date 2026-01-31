import importlib
import importlib.util
from datetime import date

import pytest


def test_wheat_risk_timebins_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.timebins") is not None


def test_week_bins_exists() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    assert hasattr(mod, "week_bins")
    assert callable(mod.week_bins)


def test_week_bins_2025_has_reasonable_number_of_bins() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    bins = mod.week_bins("2025-01-01", "2025-12-31")
    assert 50 <= len(bins) <= 54


def test_week_bins_are_contiguous_and_forward() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    bins = mod.week_bins("2025-01-01", "2025-12-31")

    assert bins, "expected at least one bin"

    starts = [date.fromisoformat(s) for s, _ in bins]
    ends = [date.fromisoformat(e) for _, e in bins]

    assert starts[0] == date(2025, 1, 1)
    assert ends[-1] == date(2025, 12, 31)

    for i in range(len(bins)):
        assert starts[i] <= ends[i]
        assert (ends[i] - starts[i]).days + 1 <= 7
        if i:
            assert starts[i] == (ends[i - 1] + date.resolution)


def test_week_bins_start_after_end_raises() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    with pytest.raises(ValueError):
        mod.week_bins("2025-01-02", "2025-01-01")


def test_week_bins_start_equals_end_returns_one_bin() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    assert mod.week_bins("2025-01-01", "2025-01-01") == [("2025-01-01", "2025-01-01")]


def test_week_bins_invalid_date_string_raises() -> None:
    mod = importlib.import_module("modules.wheat_risk.timebins")
    with pytest.raises(ValueError):
        mod.week_bins("2025-01-xx", "2025-01-01")
