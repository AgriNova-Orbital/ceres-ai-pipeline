from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

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


def run_evaluation(
    *,
    summary_csv: Path,
    index_csv_template: str,
    root_dir_template: str,
    output_csv: Path,
    best_json: Path,
    label_threshold: float = 0.5,
    precision_floor: float = 0.35,
    pred_threshold_min: float = 0.05,
    pred_threshold_max: float = 0.95,
    pred_threshold_step: float = 0.01,
    eval_ratio: float = 0.2,
    eval_min: int = 128,
    seed: int = 42,
    batch_size: int = 8,
    num_workers: int = 0,
    device: str = "cuda",
    embed_dim: int = 64,
    hidden_dim: int = 128,
    levels: list[int] | None = None,
) -> dict[str, Any]:
    summary_rows = _read_summary_rows(summary_csv)
    keep_levels = set(levels) if levels is not None else None

    th_grid = np.arange(
        float(pred_threshold_min),
        float(pred_threshold_max) + (float(pred_threshold_step) / 2.0),
        float(pred_threshold_step),
        dtype=np.float32,
    )

    eval_cache_dir = output_csv.parent / "_eval_cache"
    eval_cache_dir.mkdir(parents=True, exist_ok=True)
    eval_index_by_level: dict[int, tuple[Path, Path]] = {}

    used_levels = sorted({int(r["level"]) for r in summary_rows if r.get("level")})
    for level in used_levels:
        if keep_levels is not None and level not in keep_levels:
            continue
        index_csv = Path(str(index_csv_template).format(level=level))
        root_dir = Path(str(root_dir_template).format(level=level))
        if not index_csv.exists():
            raise SystemExit(f"Index CSV for level {level} not found: {index_csv}")

        all_paths = _read_index_npz_paths(index_csv)
        n_total = len(all_paths)
        n_eval = min(n_total, max(int(eval_min), int(round(n_total * eval_ratio))))
        rng = np.random.default_rng(int(seed) + int(level))
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
        ckpt = _resolve_checkpoint(r["checkpoint_path"], summary_csv)

        metrics = _evaluate_checkpoint(
            checkpoint_path=ckpt,
            eval_index_csv=eval_index,
            root_dir=root_dir,
            device=device,
            batch_size=batch_size,
            num_workers=num_workers,
            embed_dim=embed_dim,
            hidden_dim=hidden_dim,
            label_threshold=label_threshold,
            precision_floor=precision_floor,
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
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
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
    best_json.parent.mkdir(parents=True, exist_ok=True)
    best_json.write_text(json.dumps(best, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {output_csv} with {len(out_rows)} rows")
    print(
        "Best checkpoint | "
        f"L{best['level']}-S{best['step']} "
        f"best_threshold={best['best_threshold']:.2f} "
        f"recall={best['best_recall']:.4f} precision={best['best_precision']:.4f} "
        f"f2={best['best_f2']:.4f} meets_floor={best['meets_precision_floor']}"
    )
    print(f"Wrote {best_json}")

    return best
