"""Run API Blueprint - JSON wrappers for job submission."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

api_runs = Blueprint("api_runs", __name__)


def register_runs_api(
    app, sqlite_store, redis_conn, job_history, get_queue_conn, get_raw_data_dirs
) -> None:
    from datetime import datetime, timezone
    from rq import Queue

    def _now_iso():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _enqueue(task_name, kwargs, description):
        queue = get_queue_conn()
        job = queue.enqueue(
            task_name,
            args=(kwargs,),
            job_timeout="2h",
            result_ttl="7d",
            description=description,
        )
        rec = {
            "id": job.id,
            "section": task_name.split(".")[-1],
            "action": kwargs.get("action", "unknown"),
            "status": "enqueued",
            "enqueued_at": _now_iso(),
        }
        job_history.insert(0, rec)
        if len(job_history) > 100:
            job_history.pop()
        return job.id

    # ── Downloader ───────────────────────────────────────

    @api_runs.post("/api/run/downloader")
    def api_run_downloader():
        data = request.get_json(silent=True) or {}
        action = data.get("action", "preview_export")
        raw_dir = data.get("raw_dir") or "data/raw/france_2025_weekly"
        root = Path(app.config["REPO_ROOT"])
        out_dir = str(root / raw_dir)

        if action == "preview_export":
            cmd = [
                "python",
                "-u",
                "scripts/export_weekly_risk_rasters.py",
                "--stage",
                data.get("stage", "1"),
                "--start-date",
                data.get("start_date", "2025-01-01"),
                "--end-date",
                data.get("end_date", "2025-12-31"),
                "--limit",
                data.get("limit", "4"),
                "--dry-run",
            ]
            if data.get("ee_project"):
                cmd += ["--ee-project", data["ee_project"]]
        elif action == "refresh_inventory":
            cmd = [
                "python",
                "-u",
                "scripts/export_weekly_risk_rasters.py",
                "--stage",
                "1",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-12-31",
                "--dry-run",
            ]
        elif action == "download_all":
            cmd = [
                "python",
                "-u",
                "scripts/export_weekly_risk_rasters.py",
                "--stage",
                data.get("stage", "1"),
                "--start-date",
                data.get("start_date", "2025-01-01"),
                "--end-date",
                data.get("end_date", "2025-12-31"),
                "--output-dir",
                out_dir,
            ]
            if data.get("ee_project"):
                cmd += ["--ee-project", data["ee_project"]]
        else:
            return jsonify(error=f"Unknown action: {action}"), 400

        job_id = _enqueue(
            "modules.jobs.tasks.task_run_script_for_user",
            {"user_id": None, "cmd": cmd, "cwd": str(root)},
            f"downloader: {action}",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Build Dataset ────────────────────────────────────

    @api_runs.post("/api/run/build")
    def api_run_build():
        data = request.get_json(silent=True) or {}
        action = data.get("action", "build_level")
        root = Path(app.config["REPO_ROOT"])
        level = data.get("level", "1")
        raw_dir = data.get("raw_dir") or "data/raw/france_2025_weekly"
        max_patches = data.get("max_patches", "12000")

        if action == "dry_run":
            cmd = ["python", "-u", "scripts/build_staged_dataset.py", "--dry-run"]
        else:
            cmd = [
                "python",
                "-u",
                "scripts/build_staged_dataset.py",
                "--input-dir",
                str(root / raw_dir),
                "--output-dir",
                str(root / "data" / "wheat_risk" / "staged" / f"L{level}"),
                "--patch-size",
                "64",
                "--step-size",
                "64",
                "--expected-weeks",
                "46",
                "--max-patches",
                str(max_patches),
            ]

        job_id = _enqueue(
            "modules.jobs.tasks.task_run_script_for_user",
            {"user_id": None, "cmd": cmd, "cwd": str(root)},
            f"build: {action}",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Training ─────────────────────────────────────────

    @api_runs.post("/api/run/train")
    def api_run_train():
        data = request.get_json(silent=True) or {}
        action = data.get("action", "dry_run")
        root = Path(app.config["REPO_ROOT"])

        if action == "dry_run":
            cmd = ["python", "-u", "scripts/train_wheat_risk_lstm.py", "--dry-run"]
        elif action == "train":
            cmd = [
                "python",
                "-u",
                "scripts/train_wheat_risk_lstm.py",
                "--index-csv",
                data.get("index_csv", "./data/wheat_risk/staged/L1/index.csv"),
                "--root-dir",
                data.get("root_dir", "./data/wheat_risk/staged/L1"),
                "--device",
                data.get("device", "cpu"),
                "--epochs",
                str(data.get("epochs", 10)),
                "--batch-size",
                str(data.get("batch_size", 8)),
                "--lr",
                str(data.get("lr", "1e-3")),
                "--runs-dir",
                "runs",
            ]
        elif action == "run_matrix":
            levels = data.get("levels", "1,2,4")
            steps = data.get("steps", "100,500,2000")
            cmd = [
                "python",
                "-u",
                "scripts/train_wheat_risk_lstm.py",
                "--matrix",
                "--levels",
                levels,
                "--steps",
                steps,
                "--dry-run" if data.get("dry_run", True) else "",
            ]
            cmd = [c for c in cmd if c]
        else:
            return jsonify(error=f"Unknown action: {action}"), 400

        job_id = _enqueue(
            "modules.jobs.tasks.task_run_script_for_user",
            {"user_id": None, "cmd": cmd, "cwd": str(root)},
            f"train: {action}",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Evaluation ───────────────────────────────────────

    @api_runs.post("/api/run/eval")
    def api_run_eval():
        data = request.get_json(silent=True) or {}
        root = Path(app.config["REPO_ROOT"])
        cmd = ["python", "-u", "scripts/evaluate_model.py"]

        job_id = _enqueue(
            "modules.jobs.tasks.task_run_script_for_user",
            {"user_id": None, "cmd": cmd, "cwd": str(root)},
            "eval: run_eval",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Jobs List ────────────────────────────────────────

    @api_runs.get("/api/jobs")
    def api_jobs():
        try:
            queue = Queue(connection=redis_conn)
            queued = queue.get_job_ids()
        except Exception:
            queued = []
        return jsonify(
            history=job_history[:50],
            queued=queued,
        )

    # ── Data Dirs ────────────────────────────────────────

    @api_runs.get("/api/data-dirs")
    def api_data_dirs():
        return jsonify(dirs=get_raw_data_dirs())

    app.register_blueprint(api_runs)
