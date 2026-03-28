# modules/jobs/tasks.py
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from rq import get_current_job

from modules.download_progress import (
    DownloadProgress,
    bytes_to_human,
    estimate_download_size,
)
from modules.drive_oauth import download_file, get_drive_service, list_folder_files
from modules.merge_geotiffs import ingest_downloaded_geotiffs


def _set_progress(step: str, pct: int | None = None) -> None:
    """Update job meta with progress info."""
    try:
        job = get_current_job()
        if job:
            job.meta["step"] = step
            if pct is not None:
                job.meta["progress"] = pct
            job.save_meta()
    except Exception:
        pass


def run_script(
    cmd: list[str],
    cwd: str,
    env_overrides: dict[str, str] | None = None,
) -> dict:
    _set_progress("running script", 10)
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
    _set_progress("done" if proc.returncode == 0 else "failed", 100)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
    }


def task_run_script_for_user(kwargs: dict[str, Any]) -> dict:
    user_id = kwargs.pop("user_id", None)
    cmd = kwargs.pop("cmd")
    cwd = kwargs.pop("cwd", ".")
    _set_progress(f"preparing: {cmd[0] if cmd else '?'}", 0)
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
    _set_progress("building dataset", 0)
    kwargs["input_dir"] = Path(kwargs["input_dir"])
    kwargs["output_dir"] = Path(kwargs["output_dir"])
    run_build(**kwargs)
    _set_progress("done", 100)


def task_run_matrix(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.training_matrix_service import run_matrix

    kwargs.pop("user_id", None)
    _set_progress("running training matrix", 0)
    kwargs["runs_dir"] = Path(kwargs["runs_dir"])
    if kwargs.get("index_csv"):
        kwargs["index_csv"] = Path(kwargs["index_csv"])
    if kwargs.get("root_dir"):
        kwargs["root_dir"] = Path(kwargs["root_dir"])
    kwargs["train_script"] = Path(kwargs["train_script"])
    result = run_matrix(**kwargs)
    _set_progress("done", 100)
    return {"failures": result}


def task_run_eval(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.evaluation_service import run_evaluation

    kwargs.pop("user_id", None)
    _set_progress("running evaluation", 0)
    kwargs["summary_csv"] = Path(kwargs["summary_csv"])
    kwargs["output_csv"] = Path(kwargs["output_csv"])
    kwargs["best_json"] = Path(kwargs["best_json"])
    try:
        result = run_evaluation(**kwargs)
        _set_progress("done", 100)
        return result
    except SystemExit as e:
        _set_progress("failed", 100)
        return {"error": str(e)}


def task_run_inventory(kwargs: dict[str, Any]) -> dict[str, Any]:
    from modules.services.inventory_service import run_inventory

    kwargs.pop("user_id", None)
    _set_progress("refreshing inventory", 0)
    kwargs["input_dir"] = Path(kwargs["input_dir"])
    kwargs["output_dir"] = Path(kwargs["output_dir"])
    result = run_inventory(**kwargs)
    _set_progress("done", 100)
    return result


def task_drive_download(kwargs: dict[str, Any]) -> dict[str, Any]:
    oauth_token = kwargs.pop("oauth_token", None)
    folder_id = kwargs["folder_id"]
    save_dir = Path(kwargs["save_dir"])

    credentials_json = Path("credentials.json")
    token_json = Path("token.json")

    if oauth_token:
        import json
        import os

        token_json = Path(os.environ.get("OAUTH_TOKEN_CACHE", "token.json"))
        token_json.write_text(json.dumps(oauth_token), encoding="utf-8")

    _set_progress("connecting to drive", 0)
    svc = get_drive_service(
        credentials_json=credentials_json,
        token_json=token_json,
    )

    all_files = list_folder_files(svc, folder_id=folder_id)
    tif_files = [f for f in all_files if f.name.lower().endswith((".tif", ".tiff"))]
    total_size = estimate_download_size([{"size": f.size or 0} for f in tif_files])

    save_dir.mkdir(parents=True, exist_ok=True)
    _set_progress(f"downloading {len(tif_files)} files", 5)

    with DownloadProgress(total_bytes=total_size, total_files=len(tif_files)) as prog:
        for i, f in enumerate(tif_files):
            dst = save_dir / f.name
            if dst.exists() and dst.stat().st_size == (f.size or 0):
                prog.on_chunk(f.size or 0)
                prog.on_file_done(f.name, f.size or 0)
                continue
            _set_progress(
                f"downloading {f.name}", int(5 + 85 * i / max(len(tif_files), 1))
            )
            prog.on_file_start(f.name, f.size or 0)
            download_file(
                svc,
                file_id=f.id,
                dst_path=dst,
                progress_callback=prog.on_chunk,
            )
            prog.on_file_done(f.name, f.size or 0)

    _set_progress("ingesting", 95)
    result: dict[str, Any] = {"downloaded": len(tif_files), "total_size": total_size}

    try:
        ingest_summary = ingest_downloaded_geotiffs(save_dir)
    except ImportError as e:
        ingest_summary = {
            "merged_weeks": [],
            "single_tile_weeks_normalized": [],
            "failed_weeks": [],
            "warnings": [str(e)],
            "unknown_files": [],
        }

    result.update(ingest_summary)
    _set_progress("done", 100)
    return result
