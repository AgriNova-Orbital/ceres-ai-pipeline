from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )


def test_runner_dry_run_prints_nested_order() -> None:
    proc = _run(
        [
            "scripts/run_staged_training_matrix.py",
            "--dry-run",
            "--levels",
            "1,2,4",
            "--steps",
            "100,500,2000",
            "--base-patch",
            "64",
        ]
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout

    out = proc.stdout
    assert "L1-S100" in out
    assert "L1-S2000" in out
    assert "L2-S100" in out
    assert out.index("L1-S2000") < out.index("L2-S100")


def test_runner_execute_train_mode_creates_cell_outputs(tmp_path: Path) -> None:
    index_csv = tmp_path / "index.csv"
    with index_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for i in range(1, 7):
            w.writerow({"npz_path": f"examples/e{i:03d}.npz"})

    fake_train = tmp_path / "fake_train.py"
    fake_train.write_text(
        """
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--index-csv', required=True)
p.add_argument('--save-path', required=True)
p.add_argument('--seed', type=int, default=0)
args, _ = p.parse_known_args()

rows = Path(args.index_csv).read_text().strip().splitlines()
if len(rows) <= 1:
    raise SystemExit('empty subset')

Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)
Path(args.save_path).write_text('ok')
print(f'trained rows={len(rows)-1} seed={args.seed}')
""".strip()
        + "\n"
    )

    runs_dir = tmp_path / "runs"
    proc = _run(
        [
            "scripts/run_staged_training_matrix.py",
            "--run",
            "--execute-train",
            "--levels",
            "1",
            "--steps",
            "2,4",
            "--base-patch",
            "64",
            "--runs-dir",
            str(runs_dir),
            "--index-csv",
            str(index_csv),
            "--train-script",
            str(fake_train),
            "--seed-base",
            "100",
        ]
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout

    summary_csv = runs_dir / "summary.csv"
    assert summary_csv.exists()
    with summary_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert [r["status"] for r in rows] == ["success", "success"]

    cell1 = runs_dir / "L1" / "S2"
    cell2 = runs_dir / "L1" / "S4"
    assert (cell1 / "model.pt").exists()
    assert (cell2 / "model.pt").exists()
    assert (cell1 / "train_subset.csv").exists()
    assert (cell2 / "train_subset.csv").exists()


def test_runner_execute_train_uses_level_index_template(tmp_path: Path) -> None:
    l1 = tmp_path / "L1"
    l2 = tmp_path / "L2"
    l1.mkdir(parents=True, exist_ok=True)
    l2.mkdir(parents=True, exist_ok=True)

    idx1 = l1 / "index.csv"
    with idx1.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for i in range(1, 4):
            w.writerow({"npz_path": f"l1/e{i:03d}.npz"})

    idx2 = l2 / "index.csv"
    with idx2.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for i in range(1, 6):
            w.writerow({"npz_path": f"l2/e{i:03d}.npz"})

    fake_train = tmp_path / "fake_train.py"
    fake_train.write_text(
        """
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--index-csv', required=True)
p.add_argument('--save-path', required=True)
args, _ = p.parse_known_args()
Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)
Path(args.save_path).write_text('ok')
""".strip()
        + "\n"
    )

    runs_dir = tmp_path / "runs"
    proc = _run(
        [
            "scripts/run_staged_training_matrix.py",
            "--run",
            "--execute-train",
            "--levels",
            "1,2",
            "--steps",
            "4",
            "--base-patch",
            "64",
            "--runs-dir",
            str(runs_dir),
            "--index-csv-template",
            str(tmp_path / "L{level}" / "index.csv"),
            "--train-script",
            str(fake_train),
        ]
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout

    with (runs_dir / "summary.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["level"] == "1"
    assert rows[0]["n_train"] == "3"
    assert rows[1]["level"] == "2"
    assert rows[1]["n_train"] == "4"
