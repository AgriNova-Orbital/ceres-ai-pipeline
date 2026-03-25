from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_start_local_dev_supports_verbose_and_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "start_local_dev.sh"

    env = os.environ.copy()
    env["USE_FAKEREDIS"] = "1"

    proc = subprocess.run(
        ["bash", str(script), "--dry-run", "--verbose"],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    out = proc.stdout + proc.stderr
    assert "Verbose mode enabled" in out
    assert "[dry-run] uv run python -m modules.jobs.worker" in out
    assert (
        "[dry-run] uv run gunicorn --bind 0.0.0.0:5055 --workers 1 --access-logfile - --error-logfile - --log-level debug apps.wheat_risk_webui:create_app()"
        in out
    )
    assert "Worker logs will stream to stdout" in out


def test_start_local_dev_exports_webui_secret_key(tmp_path: Path):
    script = Path(__file__).resolve().parent.parent / "start_local_dev.sh"
    assert script.exists(), "start_local_dev.sh not found"

    content = script.read_text(encoding="utf-8")
    assert "WEBUI_SECRET_KEY" in content
    assert "export WEBUI_SECRET_KEY" in content
