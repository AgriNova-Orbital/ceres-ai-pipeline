# modules/jobs/tasks.py
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from rq import get_current_job

from modules.download_progress import (
    DownloadProgress,
    bytes_to_human,
    estimate_download_size,
)
from modules.drive_oauth import (
    build_drive_service_from_oauth_token,
    download_file,
    get_drive_service,
    list_folder_files,
)
from modules.merge_geotiffs import ingest_downloaded_geotiffs


def _set_job_meta(**fields: Any) -> None:
    try:
        job = get_current_job()
        if job:
            job.meta.update(fields)
            job.save_meta()
    except Exception:
        pass


def _set_progress(step: str, pct: int | None = None) -> None:
    fields: dict[str, Any] = {"step": step}
    if pct is not None:
        fields["progress"] = pct
    _set_job_meta(**fields)


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
        "cmd": cmd,
        "cwd": cwd,
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
    folder_id = kwargs.pop("folder_id", None)
    file_ids = kwargs.pop("file_ids", []) or []
    save_dir = Path(kwargs["save_dir"])

    credentials_json = Path("credentials.json")
    token_json = Path("token.json")

    if not oauth_token:
        # fallback to latest stored Drive token in SQLite
        try:
            from modules.persistence.sqlite_store import SQLiteStore

            store = SQLiteStore(Path(os.environ["APP_DB_PATH"]))
            with store._connect() as conn:
                row = conn.execute(
                    "SELECT token_json FROM user_oauth_tokens ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()
            if row and row["token_json"]:
                oauth_token = json.loads(row["token_json"])
        except Exception:
            oauth_token = None

    _set_progress("connecting to drive", 0)
    if oauth_token:
        svc = build_drive_service_from_oauth_token(oauth_token)
    else:
        svc = get_drive_service(
            credentials_json=credentials_json,
            token_json=token_json,
        )

    if file_ids:
        drive_files = []
        for fid in file_ids:
            meta = svc.files().get(fileId=fid, supportsAllDrives=True).execute()
            if str(meta.get("mimeType", "")).lower().endswith("folder"):
                continue
            name = str(meta.get("name", fid))
            if not name.lower().endswith((".tif", ".tiff")):
                continue
            drive_files.append(
                type(
                    "DriveFileObj",
                    (),
                    {
                        "id": fid,
                        "name": name,
                        "size": int(meta.get("size", 0)) if meta.get("size") else 0,
                    },
                )()
            )
    elif folder_id:
        all_files = list_folder_files(svc, folder_id=folder_id)
        drive_files = [
            f for f in all_files if f.name.lower().endswith((".tif", ".tiff"))
        ]
    else:
        return {"downloaded": 0, "total_size": 0, "warnings": ["no target provided"]}

    total_size = estimate_download_size(
        [{"size": getattr(f, "size", 0) or 0} for f in drive_files]
    )
    bytes_done = 0
    start_ts = time.monotonic()

    def _on_chunk(n_bytes: int, current_file: str = "") -> None:
        nonlocal bytes_done
        bytes_done += n_bytes
        elapsed = max(time.monotonic() - start_ts, 0.001)
        speed_bps = bytes_done / elapsed
        remaining = max(total_size - bytes_done, 0)
        eta_seconds = int(remaining / speed_bps) if speed_bps > 0 else None
        progress = int((bytes_done / total_size) * 100) if total_size > 0 else 100
        _set_job_meta(
            progress=progress,
            step=f"downloading {current_file}" if current_file else "downloading",
            bytes_done=bytes_done,
            total_bytes=total_size,
            speed_bps=round(speed_bps, 2),
            eta_seconds=eta_seconds,
            current_file=current_file,
        )

    save_dir.mkdir(parents=True, exist_ok=True)
    _set_job_meta(
        step=f"downloading {len(drive_files)} files",
        progress=5,
        bytes_done=0,
        total_bytes=total_size,
        speed_bps=0,
        eta_seconds=None,
        total_files=len(drive_files),
        files_done=0,
    )

    with DownloadProgress(total_bytes=total_size, total_files=len(drive_files)) as prog:
        for i, f in enumerate(drive_files):
            dst = save_dir / f.name
            if dst.exists() and dst.stat().st_size == (getattr(f, "size", 0) or 0):
                size = getattr(f, "size", 0) or 0
                prog.on_chunk(size)
                _on_chunk(size, f.name)
                prog.on_file_done(f.name, getattr(f, "size", 0) or 0)
                _set_job_meta(files_done=i + 1)
                continue
            _set_progress(
                f"downloading {f.name}", int(5 + 85 * i / max(len(drive_files), 1))
            )
            prog.on_file_start(f.name, getattr(f, "size", 0) or 0)
            download_file(
                svc,
                file_id=f.id,
                dst_path=dst,
                progress_callback=lambda n, file_name=f.name: (
                    prog.on_chunk(n),
                    _on_chunk(n, file_name),
                )[-1],
            )
            prog.on_file_done(f.name, getattr(f, "size", 0) or 0)
            _set_job_meta(files_done=i + 1)

    _set_progress("ingesting", 95)
    result: dict[str, Any] = {"downloaded": len(drive_files), "total_size": total_size}

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
