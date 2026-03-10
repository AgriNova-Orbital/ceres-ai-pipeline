from __future__ import annotations


def test_run_script_accepts_env_overrides(tmp_path):
    from modules.jobs.tasks import run_script

    result = run_script(
        [
            "python",
            "-c",
            "import os; print(os.environ.get('FOO', ''))",
        ],
        cwd=str(tmp_path),
        env_overrides={"FOO": "bar"},
    )

    assert result["returncode"] == 0
    assert result["stdout"].strip() == "bar"
