from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.wheat_risk.staged_training import build_matrix


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


def _read_index_npz_paths(index_csv: Path) -> list[str]:
    with index_csv.open(newline="") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first is None:
            return []
        header = [c.strip().lower() for c in first]
        col = 0
        if any(h in {"npz_path", "path", "npz", "file", "filename"} for h in header):
            for i, h in enumerate(header):
                if h in {"npz_path", "path", "npz", "file", "filename"}:
                    col = i
                    break
            rows = []
            for r in reader:
                if not r:
                    continue
                p = (r[col] if col < len(r) else "").strip()
                if p:
                    rows.append(p)
            return rows

        # No header, first line is data.
        rows = []
        p0 = first[col].strip() if col < len(first) else ""
        if p0:
            rows.append(p0)
        for r in reader:
            if not r:
                continue
            p = (r[col] if col < len(r) else "").strip()
            if p:
                rows.append(p)
        return rows


def _write_subset_index(index_csv: Path, npz_paths: Sequence[str]) -> None:
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    with index_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for p in npz_paths:
            w.writerow({"npz_path": p})


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
    cells = build_matrix(levels=levels, steps=steps, base_patch=int(args.base_patch))

    dry_run = bool(args.dry_run) or not bool(args.run)
    mode = "DRY RUN" if dry_run else "RUN"
    print(f"run_staged_training_matrix | mode={mode} cells={len(cells)}")

    for i, cell in enumerate(cells, start=1):
        print(
            f"{i:02d}. {cell.cell_name} "
            f"patch={cell.patch_size} step={cell.step_size} samples={cell.sample_size}"
        )

    if dry_run:
        return 0

    runs_dir = args.runs_dir
    runs_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = runs_dir / "summary.csv"

    execute_train = bool(args.execute_train)
    paths_cache: dict[str, list[str]] = {}
    if execute_train:
        if args.index_csv is None and not args.index_csv_template:
            raise SystemExit(
                "--index-csv or --index-csv-template is required with --execute-train"
            )
        if not args.train_script.exists():
            raise SystemExit(f"train script not found: {args.train_script}")

    rows: list[dict[str, str]] = []
    failures = 0
    for i, cell in enumerate(cells, start=1):
        cell_dir = runs_dir / f"L{cell.level_split}" / f"S{cell.sample_size}"
        cell_dir.mkdir(parents=True, exist_ok=True)
        config_path = cell_dir / "config.json"
        checkpoint_path = cell_dir / "model.pt"
        status = "planned"
        loss = ""
        wall_time_s = ""

        subset_count = cell.sample_size
        source_index_csv = ""
        all_paths: list[str] = []
        if execute_train:
            if args.index_csv_template:
                index_csv_for_cell = Path(
                    str(args.index_csv_template).format(level=cell.level_split)
                )
            elif args.index_csv is not None:
                index_csv_for_cell = args.index_csv
            else:
                index_csv_for_cell = Path("")

            source_index_csv = str(index_csv_for_cell)
            key = str(index_csv_for_cell)
            if key not in paths_cache:
                if not index_csv_for_cell.exists():
                    status = "failed"
                    failures += 1
                    (cell_dir / "train.log").write_text(
                        f"Missing index CSV: {index_csv_for_cell}\n"
                    )
                    rows.append(
                        {
                            "level": str(cell.level_split),
                            "step": str(cell.sample_size),
                            "n_train": "0",
                            "status": status,
                            "loss": loss,
                            "wall_time_s": wall_time_s,
                            "checkpoint_path": str(checkpoint_path),
                        }
                    )
                    continue
                parsed = _read_index_npz_paths(index_csv_for_cell)
                if not parsed:
                    status = "failed"
                    failures += 1
                    (cell_dir / "train.log").write_text(
                        f"No rows found in index CSV: {index_csv_for_cell}\n"
                    )
                    rows.append(
                        {
                            "level": str(cell.level_split),
                            "step": str(cell.sample_size),
                            "n_train": "0",
                            "status": status,
                            "loss": loss,
                            "wall_time_s": wall_time_s,
                            "checkpoint_path": str(checkpoint_path),
                        }
                    )
                    continue
                paths_cache[key] = parsed
            all_paths = paths_cache[key]
            subset_count = min(int(cell.sample_size), len(all_paths))

        payload = {
            "level_split": cell.level_split,
            "sample_size": cell.sample_size,
            "subset_size": subset_count,
            "source_index_csv": source_index_csv,
            "patch_size": cell.patch_size,
            "step_size": cell.step_size,
            "status": "planned" if not execute_train else "running",
        }
        config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

        if execute_train:
            subset_csv = cell_dir / "train_subset.csv"
            _write_subset_index(subset_csv, all_paths[:subset_count])

            cmd = [
                sys.executable,
                str(args.train_script),
                "--index-csv",
                str(subset_csv),
                "--epochs",
                str(args.epochs),
                "--batch-size",
                str(args.batch_size),
                "--lr",
                str(args.lr),
                "--max-invalid-ratio",
                str(args.max_invalid_ratio),
                "--embed-dim",
                str(args.embed_dim),
                "--hidden-dim",
                str(args.hidden_dim),
                "--num-workers",
                str(args.num_workers),
                "--device",
                str(args.device),
                "--seed",
                str(int(args.seed_base) + i - 1),
                "--save-path",
                str(checkpoint_path),
            ]
            root_dir_val: Path | None = None
            if args.root_dir_template:
                root_dir_val = Path(
                    str(args.root_dir_template).format(level=cell.level_split)
                )
            elif args.root_dir is not None:
                root_dir_val = args.root_dir
            if root_dir_val is not None:
                cmd.extend(["--root-dir", str(root_dir_val)])

            t0 = time.perf_counter()
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
            t1 = time.perf_counter()
            wall_time_s = f"{(t1 - t0):.3f}"
            log_path = cell_dir / "train.log"
            log_path.write_text(
                "CMD: " + " ".join(cmd) + "\n\n" + proc.stdout + "\n" + proc.stderr
            )

            if proc.returncode == 0:
                status = "success"
            else:
                status = "failed"
                failures += 1

        rows.append(
            {
                "level": str(cell.level_split),
                "step": str(cell.sample_size),
                "n_train": str(subset_count),
                "status": status,
                "loss": loss,
                "wall_time_s": wall_time_s,
                "checkpoint_path": str(checkpoint_path),
            }
        )

    with summary_csv.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "level",
                "step",
                "n_train",
                "status",
                "loss",
                "wall_time_s",
                "checkpoint_path",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {summary_csv} with {len(rows)} rows")
    if failures:
        print(f"Failed cells: {failures}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
