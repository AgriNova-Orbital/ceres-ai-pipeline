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


def test_export_wheat_patches_dry_run_runs_from_file_path():
    proc = _run(["scripts/export_wheat_patches.py", "--stage", "1", "--dry-run"])
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout


def test_export_weekly_risk_rasters_dry_run_runs_from_file_path():
    proc = _run(["scripts/export_weekly_risk_rasters.py", "--stage", "1", "--dry-run"])
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout


def test_download_drive_folder_uses_shared_ingest_helper(
    monkeypatch, tmp_path: Path
) -> None:
    import scripts.download_drive_folder as cli

    class FakeFile:
        def __init__(self, file_id: str, name: str, size: int = 10):
            self.id = file_id
            self.name = name
            self.size = size

    monkeypatch.setattr(cli, "get_drive_service", lambda **_: object())
    monkeypatch.setattr(
        cli,
        "list_folder_files",
        lambda _svc, folder_id: [
            FakeFile("1", "fr_wheat_feat_2021W01-0000000000-0000000000.tif")
        ],
    )
    monkeypatch.setattr(
        cli,
        "download_file",
        lambda *args, **kwargs: (
            tmp_path / "fr_wheat_feat_2021W01-0000000000-0000000000.tif"
        ).write_text("x", encoding="utf-8"),
    )
    called: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "ingest_downloaded_geotiffs",
        lambda path: called.setdefault(
            "result",
            {
                "merged_weeks": [],
                "single_tile_weeks_normalized": ["2021W01"],
                "failed_weeks": [],
                "warnings": [],
                "unknown_files": [],
            },
        ),
    )

    rc = cli.main(["--folder", "abc", "--save", str(tmp_path), "--merge"])

    assert rc == 0
    assert called["result"]["single_tile_weeks_normalized"] == ["2021W01"]
