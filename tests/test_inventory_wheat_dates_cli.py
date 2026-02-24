from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )


def test_inventory_cli_writes_json_and_missing_csv(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "reports"
    raw.mkdir(parents=True, exist_ok=True)

    # Missing the middle weekly node (index 2).
    (raw / "fr_wheat_feat_2025_data_001.tif").touch()
    (raw / "fr_wheat_feat_2025_data_003.tif").touch()

    proc = _run(
        [
            "scripts/inventory_wheat_dates.py",
            "--input-dir",
            str(raw),
            "--output-dir",
            str(out),
            "--start-date",
            "2025-01-01",
            "--cadence-days",
            "7",
        ]
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout

    inv_json = out / "data_inventory.json"
    missing_csv = out / "missing_dates.csv"
    assert inv_json.exists()
    assert missing_csv.exists()

    data = json.loads(inv_json.read_text())
    assert data["earliest_date"] == "2025-01-01"
    assert data["latest_date"] == "2025-01-15"
    assert data["missing_count"] == 1

    with missing_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert rows[0]["date"] == "2025-01-08"


def test_parse_temporal_filename_supports_underscore_suffixes() -> None:
    from modules.services.inventory_service import _parse_temporal_filename

    parsed_week = _parse_temporal_filename("fr_wheat_feat_2025_data_tile_W03.tif")
    assert parsed_week is not None
    d_w, idx_w, year_w = parsed_week
    assert d_w == __import__("datetime").date.fromisocalendar(2025, 3, 1)
    assert idx_w == 3
    assert year_w == 2025

    parsed_num = _parse_temporal_filename("fr_wheat_feat_2025_data_chunk_001.tif")
    assert parsed_num is not None
    d_n, idx_n, year_n = parsed_num
    assert d_n is None
    assert idx_n == 1
    assert year_n == 2025


def test_inventory_cli_reports_unparseable_file_count(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "reports"
    raw.mkdir(parents=True, exist_ok=True)

    (raw / "fr_wheat_feat_2025_data_001.tif").touch()
    (raw / "garbage_filename.tif").touch()

    proc = _run(
        [
            "scripts/inventory_wheat_dates.py",
            "--input-dir",
            str(raw),
            "--output-dir",
            str(out),
            "--start-date",
            "2025-01-01",
            "--cadence-days",
            "7",
        ]
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout
    assert "skipped_unparseable=1" in proc.stdout
