from __future__ import annotations

from datetime import date


def test_fill_missing_dates_weekly_grid() -> None:
    from scripts.build_npz_dataset_from_geotiffs import fill_missing_dates

    items = [
        (date(2025, 1, 1), "d1"),
        (date(2025, 1, 15), "d3"),
    ]
    values, dates, mask = fill_missing_dates(items, expected_len=3, step_days=7)

    assert dates == [date(2025, 1, 1), date(2025, 1, 8), date(2025, 1, 15)]
    assert values == ["d1", None, "d3"]
    assert mask.tolist() == [True, False, True]


def test_parse_temporal_filename_extracts_explicit_date() -> None:
    from scripts.build_npz_dataset_from_geotiffs import _parse_temporal_filename

    parsed = _parse_temporal_filename("fr_wheat_feat_2025_data_20250312.tif")
    assert parsed is not None

    d, idx, year = parsed
    assert d == date(2025, 3, 12)
    assert idx is None
    assert year == 2025


def test_parse_temporal_filename_supports_week_code() -> None:
    from scripts.build_npz_dataset_from_geotiffs import _parse_temporal_filename

    parsed = _parse_temporal_filename("fr_wheat_feat_2025W02.tif")
    assert parsed is not None

    d, idx, year = parsed
    assert d == date.fromisocalendar(2025, 2, 1)
    assert idx == 2
    assert year == 2025
