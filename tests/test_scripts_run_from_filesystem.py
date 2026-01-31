import os
import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )


def test_export_wheat_patches_dry_run_runs_from_file_path():
    proc = _run(["scripts/export_wheat_patches.py", "--stage", "1", "--dry-run"])
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout


def test_export_weekly_risk_rasters_dry_run_runs_from_file_path():
    proc = _run(["scripts/export_weekly_risk_rasters.py", "--stage", "1", "--dry-run"])
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout
