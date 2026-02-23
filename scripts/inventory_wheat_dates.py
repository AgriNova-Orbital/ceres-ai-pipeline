from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.wheat_risk.data_inventory import compute_inventory


WEEK_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
DATA_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
DATE8_IN_TEXT = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
DATE_SEP_IN_TEXT = re.compile(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)")
WEEK_IN_SUFFIX = re.compile(
    r"(?:^|[^0-9A-Za-z])W(\d{2})(?:[^0-9A-Za-z]|$)", re.IGNORECASE
)
NUM_IN_SUFFIX = re.compile(r"(?:^|[^0-9A-Za-z])(\d{1,3})(?:[^0-9A-Za-z]|$)")


def _to_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _extract_date_from_text(text: str) -> date | None:
    m = DATE_SEP_IN_TEXT.search(text)
    if m:
        d = _to_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d is not None:
            return d
    m2 = DATE8_IN_TEXT.search(text)
    if m2:
        d = _to_date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        if d is not None:
            return d
    return None


def _parse_temporal_filename(
    filename: str,
) -> tuple[date | None, int | None, int | None] | None:
    m_week = WEEK_PATTERN.match(filename)
    if m_week:
        y = int(m_week.group(1))
        wk = int(m_week.group(2))
        try:
            d = date.fromisocalendar(y, wk, 1)
        except ValueError:
            d = None
        return d, wk, y

    m_data = DATA_PATTERN.match(filename)
    if not m_data:
        return None

    y = int(m_data.group(1))
    suffix = m_data.group(2)

    d2 = _extract_date_from_text(suffix)
    if d2 is not None:
        return d2, None, y

    w = WEEK_IN_SUFFIX.search(suffix)
    if w:
        wk = int(w.group(1))
        try:
            d3 = date.fromisocalendar(y, wk, 1)
        except ValueError:
            d3 = None
        return d3, wk, y

    n = NUM_IN_SUFFIX.search(suffix)
    if n:
        return None, int(n.group(1)), y
    return None, None, y


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


def _resolve_observed_dates(
    *, input_dir: Path, start_date: date | None, cadence_days: int
) -> tuple[list[date], int]:
    observed: list[date] = []
    skipped_unparseable = 0
    for p in sorted(input_dir.glob("*.tif*")):
        parsed = _parse_temporal_filename(p.name)
        if parsed is None:
            skipped_unparseable += 1
            continue
        d, idx, year = parsed
        if d is not None:
            observed.append(d)
            continue
        if idx is None:
            skipped_unparseable += 1
            continue

        anchor = start_date
        if anchor is None and year is not None:
            anchor = date(int(year), 1, 1)
        if anchor is None:
            skipped_unparseable += 1
            continue

        observed.append(anchor + timedelta(days=(int(idx) - 1) * cadence_days))
    return observed, skipped_unparseable


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    if int(args.cadence_days) <= 0:
        raise SystemExit("--cadence-days must be > 0")

    start_date: date | None = None
    if args.start_date:
        try:
            start_date = date.fromisoformat(str(args.start_date))
        except ValueError as e:
            raise SystemExit("--start-date must be YYYY-MM-DD") from e

    observed, skipped_unparseable = _resolve_observed_dates(
        input_dir=args.input_dir,
        start_date=start_date,
        cadence_days=int(args.cadence_days),
    )
    if not observed:
        raise SystemExit("No parseable date keys found in input directory")

    inv = compute_inventory(observed, cadence_days=int(args.cadence_days))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inv_json = args.output_dir / "data_inventory.json"
    missing_csv = args.output_dir / "missing_dates.csv"

    payload = {
        "earliest_date": inv.earliest_date.isoformat(),
        "latest_date": inv.latest_date.isoformat(),
        "total_days": inv.total_days,
        "cadence_days": inv.cadence_days,
        "expected_nodes": inv.expected_nodes,
        "observed_nodes": inv.observed_nodes,
        "missing_count": len(inv.missing_dates),
        "missing_rate": inv.missing_rate,
        "max_consecutive_missing": inv.max_consecutive_missing,
    }
    inv_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with missing_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "position", "reason"])
        w.writeheader()
        for pos, d in enumerate(inv.missing_dates, start=1):
            w.writerow(
                {
                    "date": d.isoformat(),
                    "position": str(pos),
                    "reason": "missing_observation",
                }
            )

    print(
        "inventory_wheat_dates | "
        f"input={args.input_dir} output={args.output_dir} "
        f"earliest={payload['earliest_date']} latest={payload['latest_date']} "
        f"missing={payload['missing_count']} "
        f"skipped_unparseable={skipped_unparseable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
