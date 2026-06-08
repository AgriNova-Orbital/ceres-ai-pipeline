from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.wheat_risk.raw_integrity import plan_kaggle_shards, write_dict_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan Kaggle raw dataset shards from curated manifest CSV.")
    parser.add_argument("--curated-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-shard-gb", type=float, default=150.0)
    parser.add_argument("--slug-prefix", default="ceres-raw")
    return parser


def read_curated_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = read_curated_manifest(args.curated_manifest)
    max_bytes = int(args.max_shard_gb * 1024 * 1024 * 1024)
    shards = plan_kaggle_shards(rows, max_shard_bytes=max_bytes, slug_prefix=args.slug_prefix)
    write_dict_csv(
        args.out,
        shards,
        columns=("dataset_slug", "part_number", "file_count", "total_bytes", "week_keys"),
    )
    print(f"Wrote {len(shards)} shard plans to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
