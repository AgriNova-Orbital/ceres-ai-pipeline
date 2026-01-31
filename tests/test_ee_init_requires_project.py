import os
import subprocess
import sys


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_export_weekly_risk_rasters_prints_project_hint_on_init_error():
    # Ensure no project is passed; in environments without EE auth this should fail,
    # but we want a helpful message.
    env = dict(os.environ)
    env.pop("EE_PROJECT", None)
    env.pop("GOOGLE_CLOUD_PROJECT", None)

    proc = _run(
        [
            "scripts/export_weekly_risk_rasters.py",
            "--stage",
            "1",
            "--limit",
            "1",
            "--run",
            "--drive-folder",
            "EarthEngine",
        ],
        env,
    )

    # We don't expect this to succeed in CI; we just want the hint.
    assert proc.returncode != 0
    out = (proc.stdout + proc.stderr).lower()
    assert "--ee-project" in out or "ee_project" in out
