from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from modules.services.inventory_service import run_inventory


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Inventory weekly date coverage for wheat-risk rasters"
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing GeoTIFF files",
    )
    p.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for inventory reports"
    )
    p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Anchor date (YYYY-MM-DD) used when filenames only have numeric index",
    )
    p.add_argument(
        "--cadence-days",
        type=int,
        default=7,
        help="Expected cadence between observations in days (default: 7)",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_inventory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            start_date_str=args.start_date,
            cadence_days=args.cadence_days,
        )
        print(
            "inventory_wheat_dates | "
            f"input={args.input_dir} output={args.output_dir} "
            f"earliest={payload['earliest_date']} latest={payload['latest_date']} "
            f"missing={payload['missing_count']} "
            f"skipped_unparseable={payload['skipped_unparseable']}"
        )
        return 0
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
