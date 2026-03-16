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
