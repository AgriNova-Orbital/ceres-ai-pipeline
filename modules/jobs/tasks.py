# modules/jobs/tasks.py
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def run_script(
    cmd: list[str],
    cwd: str,
    env_overrides: dict[str, str] | None = None,
) -> dict:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def task_run_script_for_user(kwargs: dict[str, Any]) -> dict:
    user_id = kwargs.pop("user_id", None)
    cmd = kwargs.pop("cmd")
    cwd = kwargs.pop("cwd", ".")
    env_overrides: dict[str, str] = {}
    if user_id:
        from modules.persistence.sqlite_store import SQLiteStore

        store = SQLiteStore(Path(os.environ["APP_DB_PATH"]))
        token = store.get_user_oauth_token(user_id)
        if token:
            env_overrides["GOOGLE_OAUTH_TOKEN_JSON"] = json.dumps(token)
    return run_script(cmd=cmd, cwd=cwd, env_overrides=env_overrides or None)


def task_build_dataset(kwargs: dict[str, Any]) -> None:
    from modules.services.dataset_service import run_build

    kwargs.pop("oauth_token", None)
    kwargs.pop("user_id", None)

    # Convert string paths back to Path objects
    kwargs["input_dir"] = Path(kwargs["input_dir"])
    kwargs["output_dir"] = Path(kwargs["output_dir"])
    run_build(**kwargs)


def task_run_matrix(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.training_matrix_service import run_matrix

    kwargs.pop("user_id", None)

    # Convert concrete string paths back to Path objects, leave templates as strings
    kwargs["runs_dir"] = Path(kwargs["runs_dir"])
    if kwargs.get("index_csv"):
        kwargs["index_csv"] = Path(kwargs["index_csv"])
    if kwargs.get("root_dir"):
        kwargs["root_dir"] = Path(kwargs["root_dir"])
    kwargs["train_script"] = Path(kwargs["train_script"])
    result = run_matrix(**kwargs)
    return {"failures": result}


def task_run_eval(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.evaluation_service import run_evaluation

    kwargs.pop("user_id", None)

    # Convert string paths back to Path objects
    kwargs["summary_csv"] = Path(kwargs["summary_csv"])
    kwargs["output_csv"] = Path(kwargs["output_csv"])
    kwargs["best_json"] = Path(kwargs["best_json"])
    return run_evaluation(**kwargs)


def task_run_inventory(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.inventory_service import run_inventory

    kwargs.pop("user_id", None)

    # Convert string paths back to Path objects
    kwargs["input_dir"] = Path(kwargs["input_dir"])
    kwargs["output_dir"] = Path(kwargs["output_dir"])
    return run_inventory(**kwargs)
