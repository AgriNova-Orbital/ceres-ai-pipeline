import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from modules.wheat_risk.staged_training import build_matrix


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


def run_matrix(
    *,
    levels: list[int],
    steps: list[int],
    base_patch: int,
    dry_run: bool,
    execute_train: bool,
    runs_dir: Path,
    index_csv: Path | None,
    index_csv_template: str | None,
    root_dir: Path | None,
    root_dir_template: str | None,
    train_script: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    embed_dim: int,
    hidden_dim: int,
    num_workers: int,
    device: str,
    seed_base: int,
) -> int:
    cells = build_matrix(levels=levels, steps=steps, base_patch=base_patch)

    mode = "DRY RUN" if dry_run else "RUN"
    print(f"run_staged_training_matrix | mode={mode} cells={len(cells)}")

    for i, cell in enumerate(cells, start=1):
        print(
            f"{i:02d}. {cell.cell_name} "
            f"patch={cell.patch_size} step={cell.step_size} samples={cell.sample_size}"
        )

    if dry_run:
        return 0

    runs_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = runs_dir / "summary.csv"

    paths_cache: dict[str, list[str]] = {}
    if execute_train:
        if index_csv is None and not index_csv_template:
            raise SystemExit(
                "--index-csv or --index-csv-template is required with --execute-train"
            )
        if not train_script.exists():
            raise SystemExit(f"train script not found: {train_script}")

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
            if index_csv_template:
                index_csv_for_cell = Path(
                    str(index_csv_template).format(level=cell.level_split)
                )
            elif index_csv is not None:
                index_csv_for_cell = index_csv
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
                str(train_script),
                "--index-csv",
                str(subset_csv),
                "--epochs",
                str(epochs),
                "--batch-size",
                str(batch_size),
                "--lr",
                str(lr),
                "--max-invalid-ratio",
                "0.5",  # Hardcoded default
                "--embed-dim",
                str(embed_dim),
                "--hidden-dim",
                str(hidden_dim),
                "--num-workers",
                str(num_workers),
                "--device",
                str(device),
                "--seed",
                str(int(seed_base) + i - 1),
                "--save-path",
                str(checkpoint_path),
            ]
            root_dir_val: Path | None = None
            if root_dir_template:
                root_dir_val = Path(
                    str(root_dir_template).format(level=cell.level_split)
                )
            elif root_dir is not None:
                root_dir_val = root_dir
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
    return failures
