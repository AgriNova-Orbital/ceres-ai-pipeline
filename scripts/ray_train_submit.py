#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass(frozen=True, slots=True)
class SubmitArgs:
    data_url: str
    dataset_name: str
    cache_root: Path
    index_relpath: str
    epochs: int
    batch_size: int
    lr: float
    embed_dim: int
    hidden_dim: int
    num_workers: int
    device: str
    runs: int
    seeds: list[int]
    checkpoint_dir: Path | None
    load_from_dir: Path | None


def _parse_args(argv: Sequence[str] | None = None) -> SubmitArgs:
    p = argparse.ArgumentParser(
        description=(
            "Submit N independent training jobs to a Ray cluster. Each job requests 1 GPU "
            "and will download+cache the dataset locally on the worker."
        )
    )
    p.add_argument(
        "--data-url", required=True, help="HTTP URL to dataset archive (.tar.zst)"
    )
    p.add_argument("--dataset-name", default="stage1", help="Local cache dataset name")
    p.add_argument(
        "--cache-root",
        type=Path,
        default=Path.home() / ".cache" / "wheat-risk",
        help="Per-worker dataset cache directory",
    )
    p.add_argument(
        "--index-relpath",
        default="index.csv",
        help="Path to index.csv inside extracted dataset directory",
    )
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--embed-dim", type=int, default=64)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", default="cuda")
    p.add_argument("--runs", type=int, default=6, help="Number of Ray tasks to launch")
    p.add_argument(
        "--seeds",
        default="",
        help="Comma-separated seeds (if empty, uses 1..runs)",
    )
    p.add_argument("--checkpoint-dir", type=Path, default=None, help="Directory to save checkpoints")
    p.add_argument("--load-from-dir", type=Path, default=None, help="Directory to load checkpoints from")
    ns = p.parse_args(argv)

    if ns.epochs <= 0:
        raise SystemExit("--epochs must be > 0")
    if ns.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if ns.lr <= 0:
        raise SystemExit("--lr must be > 0")
    if ns.embed_dim <= 0:
        raise SystemExit("--embed-dim must be > 0")
    if ns.hidden_dim <= 0:
        raise SystemExit("--hidden-dim must be > 0")
    if ns.num_workers < 0:
        raise SystemExit("--num-workers must be >= 0")
    if ns.runs <= 0:
        raise SystemExit("--runs must be > 0")

    if ns.seeds:
        seeds = [int(s.strip()) for s in ns.seeds.split(",") if s.strip()]
    else:
        seeds = list(range(1, int(ns.runs) + 1))

    if len(seeds) < int(ns.runs):
        raise SystemExit("--seeds must provide at least --runs values")

    return SubmitArgs(
        data_url=ns.data_url,
        dataset_name=ns.dataset_name,
        cache_root=ns.cache_root,
        index_relpath=ns.index_relpath,
        epochs=int(ns.epochs),
        batch_size=int(ns.batch_size),
        lr=float(ns.lr),
        embed_dim=int(ns.embed_dim),
        hidden_dim=int(ns.hidden_dim),
        num_workers=int(ns.num_workers),
        device=str(ns.device),
        runs=int(ns.runs),
        seeds=seeds,
        checkpoint_dir=ns.checkpoint_dir,
        load_from_dir=ns.load_from_dir,
    )


def _import_ray():
    try:
        import ray  # type: ignore

        return ray
    except ImportError as e:
        raise SystemExit(
            "Ray is required. Install with `uv sync --dev --extra distributed` (Python 3.12)."
        ) from e


def _run_train_subprocess(
    *,
    dataset_root: Path,
    index_relpath: str,
    args: SubmitArgs,
    seed: int,
) -> int:
    index_csv = dataset_root / index_relpath
    cmd = [
        sys.executable,
        "scripts/train_wheat_risk_lstm.py",
        "--index-csv",
        str(index_csv),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(args.lr),
        "--embed-dim",
        str(args.embed_dim),
        "--hidden-dim",
        str(args.hidden_dim),
        "--num-workers",
        str(args.num_workers),
        "--device",
        str(args.device),
        "--seed",
        str(seed),
    ]

    if args.checkpoint_dir:
        save_path = args.checkpoint_dir / f"model_seed{seed}.pt"
        cmd.extend(["--save-path", str(save_path)])

    if args.load_from_dir:
        load_path = args.load_from_dir / f"model_seed{seed}.pt"
        cmd.extend(["--load-path", str(load_path)])
    print("RUN:", " ".join(shlex.quote(x) for x in cmd))
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    ray = _import_ray()
    # runtime_env attempts to zip the current directory and send it to workers.
    # Exclude heavy dirs like .venv, data, .git to keep it fast.
    ray.init(
        address="auto",
        runtime_env={
            "working_dir": ".",
            "excludes": [".venv", "data", ".git", "__pycache__", ".cache"]
        }
    )

    from modules.wheat_risk.data_cache import ensure_dataset_cached

    def train_one(seed: int) -> tuple[int, int, bytes | None]:
        # Returns: (seed, exit_code, checkpoint_bytes)
        ds_root = ensure_dataset_cached(
            data_url=args.data_url,
            dataset_name=args.dataset_name,
            cache_root=args.cache_root,
            expected_index_relpath=args.index_relpath,
        )
        
        # Determine local save path on worker
        save_path = None
        if args.checkpoint_dir:
            # We use a temp dir on worker to avoid clutter/permissions issues? 
            # Or just use the passed path relative to CWD.
            # CWD in Ray task is usually a temp dir.
            save_path = args.checkpoint_dir / f"model_seed{seed}.pt"

        code = _run_train_subprocess(
            dataset_root=ds_root,
            index_relpath=args.index_relpath,
            args=args,
            seed=seed,
        )

        chk_bytes = None
        if code == 0 and save_path and save_path.exists():
            try:
                chk_bytes = save_path.read_bytes()
            except Exception as e:
                print(f"Failed to read checkpoint {save_path}: {e}")

        return (seed, code, chk_bytes)

    train_one_remote = ray.remote(num_gpus=1)(train_one)

    refs = []
    for i in range(args.runs):
        refs.append(train_one_remote.remote(int(args.seeds[i])))

    results = ray.get(refs)
    
    # Analyze results and save checkpoints on Head
    failures = []
    for seed, code, blob in results:
        if code != 0:
            failures.append(seed)
        elif blob is not None and args.checkpoint_dir:
            # Save on Head
            local_path = args.checkpoint_dir / f"model_seed{seed}.pt"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(blob)
            print(f"Saved checkpoint from worker: {local_path}")

    if failures:
        print(f"ERROR: {len(failures)}/{len(results)} runs failed (seeds: {failures})")
        return 2
    print(f"OK: {len(results)}/{len(results)} runs succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
