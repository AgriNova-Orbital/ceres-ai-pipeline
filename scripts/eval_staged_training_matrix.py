from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.wheat_risk.dataset import WheatRiskNpzSequenceDataset
from modules.wheat_risk.metrics import (
    binary_metrics_from_probs,
    select_threshold_recall_first,
)
from modules.wheat_risk.model import CnnLstmRisk


def _import_torch() -> Any:
    try:
        import torch  # type: ignore

        return torch
    except ImportError as e:
        raise SystemExit(
            "PyTorch is required. Run `uv sync --extra ml` and retry."
        ) from e


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


def _read_summary_rows(summary_csv: Path) -> list[dict[str, str]]:
    if not summary_csv.exists():
        raise SystemExit(f"summary CSV not found: {summary_csv}")
    with summary_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"summary CSV has no rows: {summary_csv}")
    return rows


def _read_index_npz_paths(index_csv: Path) -> list[str]:
    with index_csv.open(newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames is None:
            raise SystemExit(f"Invalid index CSV (no header): {index_csv}")
        if "npz_path" not in r.fieldnames:
            raise SystemExit(f"index CSV missing npz_path column: {index_csv}")
        out = [
            row["npz_path"].strip() for row in r if (row.get("npz_path") or "").strip()
        ]
    if not out:
        raise SystemExit(f"No npz rows in {index_csv}")
    return out


def _write_eval_subset(index_csv: Path, selected_paths: list[str]) -> None:
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    with index_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for p in selected_paths:
            w.writerow({"npz_path": p})


def _resolve_checkpoint(ckpt_str: str, summary_csv: Path) -> Path:
    p = Path(ckpt_str)
    if p.is_absolute() and p.exists():
        return p
    p1 = Path.cwd() / p
    if p1.exists():
        return p1
    p2 = summary_csv.parent / p
    if p2.exists():
        return p2
    raise SystemExit(f"checkpoint not found: {ckpt_str}")


def _evaluate_checkpoint(
    *,
    checkpoint_path: Path,
    eval_index_csv: Path,
    root_dir: Path,
    device: str,
    batch_size: int,
    num_workers: int,
    embed_dim: int,
    hidden_dim: int,
    label_threshold: float,
    precision_floor: float,
    thresholds: np.ndarray,
) -> dict[str, Any]:
    torch = _import_torch()

    ds = WheatRiskNpzSequenceDataset(index_csv=eval_index_csv, root_dir=root_dir)
    x0, _ = ds[0]
    in_channels = int(x0.shape[1])

    model = CnnLstmRisk(
        in_channels=in_channels,
        embed_dim=int(embed_dim),
        hidden_dim=int(hidden_dim),
    )
    model.to(torch.device(device))
    state = torch.load(checkpoint_path, map_location=torch.device(device))
    model.load_state_dict(state, strict=True)
    model.eval()

    dl = torch.utils.data.DataLoader(
        ds,
        batch_size=int(batch_size),
        shuffle=False,
        num_workers=int(num_workers),
    )

    probs_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    with torch.no_grad():
        for xb, yb in dl:
            xb = xb.to(device)
            yb = yb.to(device).float()
            logits = model(xb)
            probs = torch.sigmoid(logits)
            mask = torch.isfinite(yb) & torch.isfinite(probs)
            if bool(mask.any().detach().cpu().item()):
                probs_list.append(probs[mask].detach().cpu().numpy())
                y_list.append(yb[mask].detach().cpu().numpy())

    if not probs_list:
        raise SystemExit(f"No valid eval points for checkpoint: {checkpoint_path}")

    probs_all = np.concatenate(probs_list, axis=0).astype(np.float32, copy=False)
    y_all = np.concatenate(y_list, axis=0).astype(np.float32, copy=False)
    y_true = (y_all >= float(label_threshold)).astype(np.int32, copy=False)

    fixed = binary_metrics_from_probs(y_true, probs_all, threshold=0.5, beta=2.0)
    best = select_threshold_recall_first(
        y_true,
        probs_all,
        thresholds=thresholds,
        precision_floor=float(precision_floor),
        beta=2.0,
    )

    out: dict[str, Any] = {
        "n_eval_examples": len(ds),
        "n_eval_points": int(y_true.shape[0]),
        "label_positive_rate": float(y_true.mean()) if y_true.size > 0 else 0.0,
        "fixed_threshold": 0.5,
        "fixed_precision": float(fixed["precision"]),
        "fixed_recall": float(fixed["recall"]),
        "fixed_f2": float(fixed["f2"]),
        "best_threshold": float(best["threshold"]),
        "best_precision": float(best["precision"]),
        "best_recall": float(best["recall"]),
        "best_f2": float(best["f2"]),
        "meets_precision_floor": bool(best["meets_precision_floor"]),
        "precision_floor": float(best["precision_floor"]),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    summary_rows = _read_summary_rows(args.summary_csv)
    keep_levels = set(_parse_int_csv(args.levels)) if args.levels else None

    th_grid = np.arange(
        float(args.pred_threshold_min),
        float(args.pred_threshold_max) + (float(args.pred_threshold_step) / 2.0),
        float(args.pred_threshold_step),
        dtype=np.float32,
    )

    eval_cache_dir = args.output_csv.parent / "_eval_cache"
    eval_cache_dir.mkdir(parents=True, exist_ok=True)
    eval_index_by_level: dict[int, tuple[Path, Path]] = {}

    used_levels = sorted({int(r["level"]) for r in summary_rows if r.get("level")})
    for level in used_levels:
        if keep_levels is not None and level not in keep_levels:
            continue
        index_csv = Path(str(args.index_csv_template).format(level=level))
        root_dir = Path(str(args.root_dir_template).format(level=level))
        if not index_csv.exists():
            raise SystemExit(f"Index CSV for level {level} not found: {index_csv}")

        all_paths = _read_index_npz_paths(index_csv)
        n_total = len(all_paths)
        n_eval = min(
            n_total, max(int(args.eval_min), int(round(n_total * args.eval_ratio)))
        )
        rng = np.random.default_rng(int(args.seed) + int(level))
        idx = rng.choice(n_total, size=n_eval, replace=False)
        selected = [all_paths[int(i)] for i in idx]
        selected.sort()

        eval_index = eval_cache_dir / f"L{level}_eval.csv"
        _write_eval_subset(eval_index, selected)
        eval_index_by_level[level] = (eval_index, root_dir)

    out_rows: list[dict[str, Any]] = []
    for r in summary_rows:
        level = int(r["level"])
        step = int(r["step"])
        if keep_levels is not None and level not in keep_levels:
            continue
        if level not in eval_index_by_level:
            continue

        eval_index, root_dir = eval_index_by_level[level]
        ckpt = _resolve_checkpoint(r["checkpoint_path"], args.summary_csv)

        metrics = _evaluate_checkpoint(
            checkpoint_path=ckpt,
            eval_index_csv=eval_index,
            root_dir=root_dir,
            device=str(args.device),
            batch_size=int(args.batch_size),
            num_workers=int(args.num_workers),
            embed_dim=int(args.embed_dim),
            hidden_dim=int(args.hidden_dim),
            label_threshold=float(args.label_threshold),
            precision_floor=float(args.precision_floor),
            thresholds=th_grid,
        )

        out_rows.append(
            {
                "level": level,
                "step": step,
                "n_train": int(r.get("n_train", 0) or 0),
                "status": r.get("status", ""),
                "checkpoint_path": str(ckpt),
                **metrics,
            }
        )

    if not out_rows:
        raise SystemExit("No rows evaluated")

    out_rows.sort(key=lambda x: (int(x["level"]), int(x["step"])))
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "level",
                "step",
                "n_train",
                "status",
                "checkpoint_path",
                "n_eval_examples",
                "n_eval_points",
                "label_positive_rate",
                "fixed_threshold",
                "fixed_precision",
                "fixed_recall",
                "fixed_f2",
                "best_threshold",
                "best_precision",
                "best_recall",
                "best_f2",
                "meets_precision_floor",
                "precision_floor",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    floor_rows = [r for r in out_rows if bool(r["meets_precision_floor"])]
    cands = floor_rows if floor_rows else out_rows
    best = max(
        cands,
        key=lambda r: (
            float(r["best_recall"]),
            float(r["best_f2"]),
            float(r["best_precision"]),
            -float(r["best_threshold"]),
        ),
    )
    args.best_json.parent.mkdir(parents=True, exist_ok=True)
    args.best_json.write_text(json.dumps(best, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {args.output_csv} with {len(out_rows)} rows")
    print(
        "Best checkpoint | "
        f"L{best['level']}-S{best['step']} "
        f"best_threshold={best['best_threshold']:.2f} "
        f"recall={best['best_recall']:.4f} precision={best['best_precision']:.4f} "
        f"f2={best['best_f2']:.4f} meets_floor={best['meets_precision_floor']}"
    )
    print(f"Wrote {args.best_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
