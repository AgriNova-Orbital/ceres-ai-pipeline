from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.services.evaluation_service import run_evaluation


def _parse_int_csv(value: str) -> list[int]:
    out: list[int] = []
    for p in value.split(","):
        p2 = p.strip()
        if not p2:
            continue
        out.append(int(p2))
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate staged training checkpoints")
    p.add_argument(
        "--summary-csv", type=Path, default=Path("runs/staged_final/summary.csv")
    )
    p.add_argument("--index-csv-template", type=str, required=True)
    p.add_argument("--root-dir-template", type=str, required=True)
    p.add_argument(
        "--output-csv", type=Path, default=Path("runs/staged_final/eval_metrics.csv")
    )
    p.add_argument(
        "--best-json", type=Path, default=Path("runs/staged_final/best_model.json")
    )
    p.add_argument("--label-threshold", type=float, default=0.5)
    p.add_argument("--precision-floor", type=float, default=0.35)
    p.add_argument("--pred-threshold-min", type=float, default=0.05)
    p.add_argument("--pred-threshold-max", type=float, default=0.95)
    p.add_argument("--pred-threshold-step", type=float, default=0.01)
    p.add_argument("--eval-ratio", type=float, default=0.2)
    p.add_argument("--eval-min", type=int, default=128)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--embed-dim", type=int, default=64)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument(
        "--levels",
        type=str,
        default="",
        help="Optional level whitelist, e.g. 1,2,4",
    )
    ns = p.parse_args(argv)

    if ns.eval_ratio <= 0.0 or ns.eval_ratio > 1.0:
        raise SystemExit("--eval-ratio must be in (0,1]")
    if ns.eval_min <= 0:
        raise SystemExit("--eval-min must be > 0")
    if ns.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if ns.num_workers < 0:
        raise SystemExit("--num-workers must be >= 0")
    if ns.embed_dim <= 0 or ns.hidden_dim <= 0:
        raise SystemExit("--embed-dim and --hidden-dim must be > 0")
    if ns.pred_threshold_step <= 0.0:
        raise SystemExit("--pred-threshold-step must be > 0")
    if ns.pred_threshold_min < 0.0 or ns.pred_threshold_max > 1.0:
        raise SystemExit("prediction threshold range must be within [0,1]")
    if ns.pred_threshold_min >= ns.pred_threshold_max:
        raise SystemExit("--pred-threshold-min must be < --pred-threshold-max")
    return ns


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    keep_levels = _parse_int_csv(args.levels) if args.levels else None

    run_evaluation(
        summary_csv=args.summary_csv,
        index_csv_template=args.index_csv_template,
        root_dir_template=args.root_dir_template,
        output_csv=args.output_csv,
        best_json=args.best_json,
        label_threshold=args.label_threshold,
        precision_floor=args.precision_floor,
        pred_threshold_min=args.pred_threshold_min,
        pred_threshold_max=args.pred_threshold_max,
        pred_threshold_step=args.pred_threshold_step,
        eval_ratio=args.eval_ratio,
        eval_min=args.eval_min,
        seed=args.seed,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        device=args.device,
        embed_dim=args.embed_dim,
        hidden_dim=args.hidden_dim,
        levels=keep_levels,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
