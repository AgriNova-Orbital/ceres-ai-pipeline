from pathlib import Path

import csv
import pytest


def test_training_matrix_service_has_run_matrix_function():
    from modules.services.training_matrix_service import run_matrix

    assert callable(run_matrix)


def test_run_matrix_rejects_index_rows_outside_repo_when_repo_root_set(
    tmp_path: Path,
) -> None:
    from modules.services.training_matrix_service import run_matrix

    repo_root = tmp_path / "repo"
    level_dir = repo_root / "data" / "wheat_risk" / "staged" / "L1"
    level_dir.mkdir(parents=True)
    index_csv = level_dir / "index.csv"
    outside_npz = tmp_path / "outside.npz"
    with index_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["npz_path"])
        writer.writeheader()
        writer.writerow({"npz_path": str(outside_npz)})

    train_script = repo_root / "scripts" / "fake_train.py"
    train_script.parent.mkdir(parents=True)
    train_script.write_text("raise SystemExit(0)\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="npz_path"):
        run_matrix(
            levels=[1],
            steps=[1],
            base_patch=64,
            dry_run=False,
            execute_train=True,
            runs_dir=repo_root / "runs",
            index_csv=None,
            index_csv_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}" / "index.csv"
            ),
            root_dir=None,
            root_dir_template=str(
                repo_root / "data" / "wheat_risk" / "staged" / "L{level}"
            ),
            train_script=train_script,
            epochs=1,
            batch_size=1,
            lr=0.001,
            embed_dim=8,
            hidden_dim=8,
            num_workers=0,
            device="cpu",
            seed_base=42,
            repo_root=repo_root,
        )
