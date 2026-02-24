from __future__ import annotations
from pathlib import Path
import json
import csv


def test_inventory_service_creates_reports(tmp_path: Path):
    from modules.services.inventory_service import run_inventory

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "fr_wheat_feat_2025_data_001.tif").touch()
    (raw_dir / "fr_wheat_feat_2025_data_003.tif").touch()

    output_dir = tmp_path / "reports"

    result = run_inventory(
        input_dir=raw_dir,
        output_dir=output_dir,
        start_date_str="2025-01-01",
        cadence_days=7,
    )

    assert result["missing_count"] == 1

    inv_json = output_dir / "data_inventory.json"
    missing_csv = output_dir / "missing_dates.csv"
    assert inv_json.exists()
    assert missing_csv.exists()

    data = json.loads(inv_json.read_text())
    assert data["earliest_date"] == "2025-01-01"
    assert data["missing_count"] == 1

    with missing_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["date"] == "2025-01-08"
