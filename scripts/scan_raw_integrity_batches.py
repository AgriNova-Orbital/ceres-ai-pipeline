from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.wheat_risk.raw_integrity import (
    build_repair_candidates,
    choose_batch,
    scan_raw_batch,
    write_dict_csv,
    write_scan_csv,
    write_summary_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan raw wheat-risk GeoTIFFs in resumable batches.")
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--read-sample", action="store_true")
    parser.add_argument("--week-failure-threshold", type=int, default=5)
    return parser


def completed_relative_paths(batch_dir: Path) -> set[str]:
    completed: set[str] = set()
    for csv_path in sorted(batch_dir.glob("batch_*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                completed.add(row["relative_path"])
    return completed


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidates = sorted(args.raw_root.rglob("*.tif"))
    batch_dir = args.report_root / "batches"
    completed = completed_relative_paths(batch_dir)

    selected = choose_batch(
        candidates,
        raw_root=args.raw_root,
        completed_relative_paths=completed,
        batch_size=args.batch_size,
    )
    batch_number = len(list(batch_dir.glob("batch_*.csv"))) + 1
    records = scan_raw_batch(selected, raw_root=args.raw_root, read_sample=args.read_sample)
    batch_path = batch_dir / f"batch_{batch_number:06d}.csv"
    write_scan_csv(batch_path, records)
    write_summary_json(args.report_root / "summary.json", records)
    repair_candidates = build_repair_candidates(records, week_failure_threshold=args.week_failure_threshold)
    write_dict_csv(
        args.report_root / "repair_candidates.csv",
        repair_candidates,
        columns=("repair_scope", "week_key", "relative_path", "tile_key", "reason"),
    )
    print(f"Scanned {len(records)} files into {batch_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
