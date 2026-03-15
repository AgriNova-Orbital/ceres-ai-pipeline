from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.services.training_matrix_service import run_matrix


def _parse_int_csv(name: str, value: str) -> list[int]:
    out: list[int] = []
    for p in value.split(","):
        p2 = p.strip()
        if not p2:
            continue
        try:
            n = int(p2)
        except ValueError as e:
            raise SystemExit(f"--{name} must be comma-separated ints") from e
        if n <= 0:
            raise SystemExit(f"--{name} values must be > 0")
        out.append(n)
    if not out:
        raise SystemExit(f"--{name} must not be empty")
    return out


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run wheat-risk staged training matrix")
    p.add_argument(
        "--levels", default="1,2,4", help="Outer-loop level splits (comma-separated)"
    )
    p.add_argument(
        "--steps",
        default="100,500,2000",
        help="Inner-loop sample sizes (comma-separated)",
    )
    p.add_argument("--base-patch", type=int, default=64)
    p.add_argument(
        "--dry-run", action="store_true", help="Only print nested execution plan"
    )
    p.add_argument(
        "--run", action="store_true", help="Create per-cell artifacts and summary CSV"
    )
    p.add_argument(
        "--execute-train",
        action="store_true",
        help="When used with --run, execute the training command per cell.",
    )
    p.add_argument("--runs-dir", type=Path, default=Path("runs/staged"))
    p.add_argument(
        "--index-csv",
        type=Path,
        default=None,
        help="Base index CSV used for train subset creation in execute-train mode.",
    )
    p.add_argument(
        "--index-csv-template",
        type=str,
        default=None,
        help="Per-level index CSV template, e.g. data/staged/L{level}/index.csv",
    )
    p.add_argument(
        "--root-dir",
        type=Path,
        default=None,
        help="Optional root-dir passed to training script.",
    )
    p.add_argument(
        "--root-dir-template",
        type=str,
        default=None,
        help="Optional per-level root-dir template, e.g. data/staged/L{level}",
    )
    p.add_argument(
        "--train-script",
        type=Path,
        default=Path("scripts/train_wheat_risk_lstm.py"),
        help="Training script path for execute-train mode.",
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--max-invalid-ratio", type=float, default=0.5)
    p.add_argument("--embed-dim", type=int, default=64)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", default="cpu")
    p.add_argument("--seed-base", type=int, default=42)
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.base_patch <= 0:
        raise SystemExit("--base-patch must be > 0")
    if args.epochs <= 0:
        raise SystemExit("--epochs must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.lr <= 0:
        raise SystemExit("--lr must be > 0")
    if args.max_invalid_ratio < 0.0 or args.max_invalid_ratio > 1.0:
        raise SystemExit("--max-invalid-ratio must be between 0 and 1")
    if args.embed_dim <= 0:
        raise SystemExit("--embed-dim must be > 0")
    if args.hidden_dim <= 0:
        raise SystemExit("--hidden-dim must be > 0")
    if args.num_workers < 0:
        raise SystemExit("--num-workers must be >= 0")

    levels = _parse_int_csv("levels", args.levels)
    steps = _parse_int_csv("steps", args.steps)

    dry_run = bool(args.dry_run) or not bool(args.run)

    failures = run_matrix(
        levels=levels,
        steps=steps,
        base_patch=int(args.base_patch),
        dry_run=dry_run,
        execute_train=bool(args.execute_train),
        runs_dir=args.runs_dir,
        index_csv=args.index_csv,
        index_csv_template=args.index_csv_template,
        root_dir=args.root_dir,
        root_dir_template=args.root_dir_template,
        train_script=args.train_script,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        embed_dim=args.embed_dim,
        hidden_dim=args.hidden_dim,
        num_workers=args.num_workers,
        device=args.device,
        seed_base=args.seed_base,
    )

    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
