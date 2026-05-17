from __future__ import annotations

import csv
from pathlib import Path

import pytest


def test_evaluation_service_has_run_evaluation_function():
    from modules.services.evaluation_service import run_evaluation

    assert callable(run_evaluation)


def _write_summary(summary_csv: Path, checkpoint_path: str) -> None:
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["level", "step", "n_train", "status", "checkpoint_path"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "level": "1",
                "step": "1",
                "n_train": "1",
                "status": "success",
                "checkpoint_path": checkpoint_path,
            }
        )


def _write_index(index_csv: Path, npz_path: str) -> None:
    index_csv.parent.mkdir(parents=True, exist_ok=True)
    with index_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["npz_path"])
        writer.writeheader()
        writer.writerow({"npz_path": npz_path})


def test_run_evaluation_rejects_summary_checkpoint_outside_repo_when_repo_root_set(
    tmp_path: Path,
) -> None:
    from modules.services.evaluation_service import run_evaluation

    repo_root = tmp_path / "repo"
    summary_csv = repo_root / "runs" / "staged_final" / "summary.csv"
    _write_summary(summary_csv, str(tmp_path / "outside.pt"))
    _write_index(
        repo_root / "data" / "wheat_risk" / "staged" / "L1" / "index.csv",
        "sample.npz",
    )

    with pytest.raises(SystemExit, match="checkpoint_path"):
        run_evaluation(
            summary_csv=summary_csv,
            index_csv_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}" / "index.csv"
            ),
            root_dir_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}"
            ),
            output_csv=repo_root / "runs" / "staged_final" / "eval_metrics.csv",
            best_json=repo_root / "runs" / "staged_final" / "best_model.json",
            device="cpu",
            levels=[1],
            repo_root=repo_root,
        )


def test_run_evaluation_rejects_index_rows_outside_repo_when_repo_root_set(
    tmp_path: Path,
) -> None:
    from modules.services.evaluation_service import run_evaluation

    repo_root = tmp_path / "repo"
    checkpoint_path = repo_root / "runs" / "staged_final" / "model.pt"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(b"not a real checkpoint")
    summary_csv = repo_root / "runs" / "staged_final" / "summary.csv"
    _write_summary(summary_csv, str(checkpoint_path))
    _write_index(
        repo_root / "data" / "wheat_risk" / "staged" / "L1" / "index.csv",
        str(tmp_path / "outside.npz"),
    )

    with pytest.raises(SystemExit, match="npz_path"):
        run_evaluation(
            summary_csv=summary_csv,
            index_csv_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}" / "index.csv"
            ),
            root_dir_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}"
            ),
            output_csv=repo_root / "runs" / "staged_final" / "eval_metrics.csv",
            best_json=repo_root / "runs" / "staged_final" / "best_model.json",
            device="cpu",
            levels=[1],
            repo_root=repo_root,
        )
