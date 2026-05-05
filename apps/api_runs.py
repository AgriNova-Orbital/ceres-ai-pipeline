"""Run API Blueprint - JSON wrappers for job submission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, g, jsonify, request, session


def register_runs_api(
    app, sqlite_store, redis_conn, job_history, get_queue_conn, get_raw_data_dirs
) -> None:
    api_runs = Blueprint("api_runs", __name__)
    from datetime import datetime, timezone
    from rq import Queue

    def _now_iso():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _current_user_id() -> str | None:
        clerk_user = getattr(g, "clerk_user", None)
        if isinstance(clerk_user, dict) and clerk_user.get("sub"):
            return str(clerk_user["sub"])
        user_id = session.get("user_id")
        return str(user_id) if user_id else None

    def _job_info(j) -> dict:
        """Extract useful info from an RQ job."""
        info = {
            "id": j.id,
            "description": j.description or "",
            "section": (j.description or "").split(":")[0].strip(),
            "action": (j.description or "").split(":")[-1].strip(),
            "status": "unknown",
            "enqueued_at": "",
            "started_at": "",
            "ended_at": "",
        }
        # Safe accessors
        try:
            info["status"] = j.get_status()
        except Exception:
            pass
        try:
            info["enqueued_at"] = j.enqueued_at.isoformat() if j.enqueued_at else ""
        except Exception:
            pass
        try:
            info["started_at"] = j.started_at.isoformat() if j.started_at else ""
        except Exception:
            pass
        try:
            info["ended_at"] = j.ended_at.isoformat() if j.ended_at else ""
        except Exception:
            pass
        try:
            info["meta"] = dict(j.meta) if j.meta else {}
        except Exception:
            info["meta"] = {}
        try:
            if j.result is not None:
                if isinstance(j.result, dict):
                    info["result"] = {k: str(v)[:200] for k, v in j.result.items()}
                elif isinstance(j.result, bytes):
                    info["result"] = f"[binary {len(j.result)} bytes]"
                else:
                    info["result"] = str(j.result)[:500]
        except Exception:
            info["result"] = "[unable to read result]"
        try:
            if j.exc_info:
                info["error"] = str(j.exc_info)[-500:]
        except Exception:
            pass
        return info

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

    def _parse_int_list(csv_like: str, *, field: str) -> list[int]:
        out: list[int] = []
        for token in str(csv_like).split(","):
            t = token.strip()
            if not t:
                continue
            try:
                v = int(t)
            except ValueError as e:
                raise ValueError(f"{field} must be comma-separated integers") from e
            if v <= 0:
                raise ValueError(f"{field} values must be > 0")
            out.append(v)
        if not out:
            raise ValueError(f"{field} must not be empty")
        return out

    def _normalize_path(root: Path, path_like: str | None, default: str) -> str:
        raw = (path_like or default).strip()
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str(root / raw)

    # ── Downloader ───────────────────────────────────────

    @api_runs.post("/api/run/downloader")
    def api_run_downloader():
        data = request.get_json(silent=True) or {}
        action = data.get("action", "preview_export")
        root = Path(app.config["REPO_ROOT"])

        if action in {"preview_export", "run_export", "download_all"}:
            run_flag = action in {"run_export", "download_all"}
            drive_folder = (data.get("drive_folder") or "").strip() or None
            if run_flag and not drive_folder:
                return jsonify(
                    error="drive_folder is required when action runs export"
                ), 400

            payload: dict[str, Any] = {
                "user_id": _current_user_id(),
                "stage": str(data.get("stage", "1")),
                "start_date": str(data.get("start_date", "2025-01-01")),
                "end_date": str(data.get("end_date", "2025-12-31")),
                "limit": int(data.get("limit", 4)),
                "run": run_flag,
                "drive_folder": drive_folder,
                "ee_project": (data.get("ee_project") or "").strip() or None,
            }
            job_id = _enqueue(
                "modules.jobs.tasks.task_export_weekly_risk_rasters",
                payload,
                f"downloader: {action}",
            )
            return jsonify(job_id=job_id, status="enqueued")

        if action == "refresh_inventory":
            raw_dir = _normalize_path(
                root,
                data.get("raw_dir"),
                "data/raw/france_2025_weekly",
            )
            payload = {
                "user_id": _current_user_id(),
                "input_dir": raw_dir,
                "output_dir": str(root / "reports"),
                "start_date_str": str(data.get("start_date", "2025-01-01")),
                "cadence_days": int(data.get("cadence_days", 7)),
            }
            job_id = _enqueue(
                "modules.jobs.tasks.task_run_inventory",
                payload,
                "downloader: refresh_inventory",
            )
            return jsonify(job_id=job_id, status="enqueued")

        return jsonify(error=f"Unknown action: {action}"), 400

    # ── Build Dataset ────────────────────────────────────

    @api_runs.post("/api/run/build")
    def api_run_build():
        data = request.get_json(silent=True) or {}
        action = data.get("action", "build_level")
        root = Path(app.config["REPO_ROOT"])
        level = data.get("level", "1")
        raw_dir = _normalize_path(
            root, data.get("raw_dir"), "data/raw/france_2025_weekly"
        )
        max_patches = int(data.get("max_patches", 12000))

        if action not in {"build_level", "dry_run"}:
            return jsonify(error=f"Unknown action: {action}"), 400

        patch = {"1": 64, "2": 32, "4": 16}.get(str(level), 64)
        payload = {
            "user_id": _current_user_id(),
            "input_dir": raw_dir,
            "output_dir": str(root / "data" / "wheat_risk" / "staged" / f"L{level}"),
            "patch_size": patch,
            "step_size": patch,
            "expected_weeks": int(data.get("expected_weeks", 46)),
            "max_patches": 1 if action == "dry_run" else max_patches,
            "workers": int(data.get("workers", 0)),
            "skip_existing": bool(data.get("skip_existing", False)),
        }

        job_id = _enqueue(
            "modules.jobs.tasks.task_build_dataset",
            payload,
            f"build: {action}",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Training ─────────────────────────────────────────

    @api_runs.post("/api/run/train")
    def api_run_train():
        data = request.get_json(silent=True) or {}
        action = str(data.get("action", "dry_run")).strip()
        if action == "execute_train":
            action = "run_matrix"
        root = Path(app.config["REPO_ROOT"])

        if action == "dry_run":
            payload = {
                "user_id": _current_user_id(),
                "levels": _parse_int_list(
                    str(data.get("levels", "1,2,4")), field="levels"
                ),
                "steps": _parse_int_list(
                    str(data.get("steps", "100,500,2000")), field="steps"
                ),
                "base_patch": int(data.get("base_patch", 64)),
                "dry_run": True,
                "execute_train": False,
                "runs_dir": Path(str(data.get("runs_dir", "runs"))),
                "index_csv": None,
                "index_csv_template": None,
                "root_dir": None,
                "root_dir_template": None,
                "train_script": Path(
                    str(data.get("train_script", "scripts/train_wheat_risk_lstm.py"))
                ),
                "epochs": int(data.get("epochs", 10)),
                "batch_size": int(data.get("batch_size", 8)),
                "lr": float(data.get("lr", 1e-3)),
                "embed_dim": int(data.get("embed_dim", 64)),
                "hidden_dim": int(data.get("hidden_dim", 128)),
                "num_workers": int(data.get("num_workers", 0)),
                "device": str(data.get("device", "cpu")),
                "seed_base": int(data.get("seed_base", 42)),
            }
            job_id = _enqueue(
                "modules.jobs.tasks.task_run_matrix", payload, "train: dry_run"
            )
            return jsonify(job_id=job_id, status="enqueued")

        if action == "run_matrix":
            payload = {
                "user_id": _current_user_id(),
                "levels": _parse_int_list(
                    str(data.get("levels", "1,2,4")), field="levels"
                ),
                "steps": _parse_int_list(
                    str(data.get("steps", "100,500,2000")), field="steps"
                ),
                "base_patch": int(data.get("base_patch", 64)),
                "dry_run": bool(data.get("dry_run", False)),
                "execute_train": True,
                "runs_dir": Path(str(data.get("runs_dir", "runs"))),
                "index_csv": None,
                "index_csv_template": str(
                    data.get(
                        "index_csv_template",
                        "./data/wheat_risk/staged/L{level}/index.csv",
                    )
                ),
                "root_dir": None,
                "root_dir_template": str(
                    data.get("root_dir_template", "./data/wheat_risk/staged/L{level}")
                ),
                "train_script": Path(
                    str(data.get("train_script", "scripts/train_wheat_risk_lstm.py"))
                ),
                "epochs": int(data.get("epochs", 10)),
                "batch_size": int(data.get("batch_size", 8)),
                "lr": float(data.get("lr", 1e-3)),
                "embed_dim": int(data.get("embed_dim", 64)),
                "hidden_dim": int(data.get("hidden_dim", 128)),
                "num_workers": int(data.get("num_workers", 0)),
                "device": str(data.get("device", "cpu")),
                "seed_base": int(data.get("seed_base", 42)),
            }
            job_id = _enqueue(
                "modules.jobs.tasks.task_run_matrix",
                payload,
                "train: run_matrix",
            )
            return jsonify(job_id=job_id, status="enqueued")

        return jsonify(error=f"Unknown action: {action}"), 400

    # ── Evaluation ───────────────────────────────────────

    @api_runs.post("/api/run/eval")
    def api_run_eval():
        data = request.get_json(silent=True) or {}
        payload = {
            "user_id": _current_user_id(),
            "summary_csv": Path(
                str(data.get("summary_csv", "runs/staged_final/summary.csv"))
            ),
            "index_csv_template": str(
                data.get(
                    "index_csv_template", "./data/wheat_risk/staged/L{level}/index.csv"
                )
            ),
            "root_dir_template": str(
                data.get("root_dir_template", "./data/wheat_risk/staged/L{level}")
            ),
            "output_csv": Path(
                str(data.get("output_csv", "runs/staged_final/eval_metrics.csv"))
            ),
            "best_json": Path(
                str(data.get("best_json", "runs/staged_final/best_model.json"))
            ),
            "label_threshold": float(data.get("label_threshold", 0.5)),
            "precision_floor": float(data.get("precision_floor", 0.35)),
            "pred_threshold_min": float(data.get("pred_threshold_min", 0.05)),
            "pred_threshold_max": float(data.get("pred_threshold_max", 0.95)),
            "pred_threshold_step": float(data.get("pred_threshold_step", 0.01)),
            "eval_ratio": float(data.get("eval_ratio", 0.2)),
            "eval_min": int(data.get("eval_min", 128)),
            "seed": int(data.get("seed", 42)),
            "batch_size": int(data.get("batch_size", 8)),
            "num_workers": int(data.get("num_workers", 0)),
            "device": str(data.get("device", "cuda")),
            "embed_dim": int(data.get("embed_dim", 64)),
            "hidden_dim": int(data.get("hidden_dim", 128)),
            "levels": None,
        }
        if data.get("levels"):
            payload["levels"] = _parse_int_list(str(data.get("levels")), field="levels")

        job_id = _enqueue(
            "modules.jobs.tasks.task_run_eval",
            payload,
            "eval: run_eval",
        )
        return jsonify(job_id=job_id, status="enqueued")

    # ── Jobs ──────────────────────────────────────────────

    @api_runs.get("/api/jobs/<job_id>")
    def api_job_detail(job_id: str):
        try:
            queue = Queue(connection=redis_conn)
            job = queue.fetch_job(job_id)
        except Exception as e:
            return jsonify(error=str(e)), 500

        if job is None:
            return jsonify(error="Job not found"), 404

        return jsonify(job=_job_info(job))

    @api_runs.get("/api/jobs")
    def api_jobs():
        jobs = []
        workers = []
        limit_arg = request.args.get("limit", "100").strip()
        all_arg = request.args.get("all", "0").strip()
        try:
            queue = Queue(connection=redis_conn)

            # Collect all RQ job IDs from all registries
            seen_ids = set()

            def _add_rq_job(jid, status_override=None):
                if jid in seen_ids:
                    return
                seen_ids.add(jid)
                try:
                    j = queue.fetch_job(jid)
                    if j:
                        info = _job_info(j)
                        if status_override:
                            info["status"] = status_override
                        jobs.append(info)
                except Exception:
                    pass

            for jid in queue.get_job_ids():
                _add_rq_job(jid, "queued")
            for jid in queue.started_job_registry.get_job_ids():
                _add_rq_job(jid, "running")
            for jid in queue.finished_job_registry.get_job_ids():
                _add_rq_job(jid, "finished")
            for jid in queue.failed_job_registry.get_job_ids():
                _add_rq_job(jid, "failed")

            # Workers
            try:
                for w in Worker.all(connection=redis_conn):
                    try:
                        workers.append(
                            {
                                "name": w.name.split(".")[0][:12],
                                "state": w.get_state(),
                                "current_job": w.get_current_job_id(),
                            }
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception as e:
            return jsonify(jobs=jobs, workers=[], error=str(e))

        # Sort by enqueued time
        jobs.sort(key=lambda x: x.get("enqueued_at", ""), reverse=True)
        total_jobs = len(jobs)

        if all_arg == "1":
            visible_jobs = jobs
        else:
            try:
                limit = max(1, int(limit_arg))
            except ValueError:
                limit = 100
            visible_jobs = jobs[:limit]

        return jsonify(jobs=visible_jobs, workers=workers, total=total_jobs)

    # ── Data Dirs ────────────────────────────────────────

    @api_runs.get("/api/data-dirs")
    def api_data_dirs():
        return jsonify(dirs=get_raw_data_dirs())

    @api_runs.get("/api/scan/raw")
    def api_scan_raw():
        limit = int(request.args.get("limit", "200"))
        root = Path(app.config["REPO_ROOT"])
        raw_base = root / "data" / "raw"
        files = []
        if raw_base.exists():
            for p in sorted(raw_base.rglob("*.tif*")):
                if p.is_file():
                    files.append(
                        {
                            "path": str(p.relative_to(root)),
                            "name": p.name,
                            "size_mb": round(p.stat().st_size / 1e6, 1),
                            "dir": str(p.parent.relative_to(root)),
                        }
                    )
                if len(files) >= limit:
                    break
        return jsonify(files=files, total=len(files))

    @api_runs.get("/api/scan/patches")
    def api_scan_patches():
        limit = int(request.args.get("limit", "200"))
        root = Path(app.config["REPO_ROOT"])
        candidates = [root / "data" / "wheat_risk", root / "runs"]
        files = []
        for base in candidates:
            if not base.exists():
                continue
            for p in sorted(base.rglob("*.npz")):
                if p.is_file():
                    files.append(
                        {
                            "path": str(p.relative_to(root)),
                            "name": p.name,
                            "size_mb": round(p.stat().st_size / 1e6, 1),
                            "dir": str(p.parent.relative_to(root)),
                        }
                    )
                if len(files) >= limit:
                    break
        return jsonify(files=files, total=len(files))

    @api_runs.get("/api/scan/reports")
    def api_scan_reports():
        root = Path(app.config["REPO_ROOT"])
        reports_dir = root / "reports"
        files = []
        if reports_dir.exists():
            for p in sorted(reports_dir.rglob("*")):
                if p.is_file():
                    files.append(
                        {
                            "path": str(p.relative_to(root)),
                            "name": p.name,
                            "size_mb": round(p.stat().st_size / 1e6, 1),
                        }
                    )
        return jsonify(files=files, total=len(files))

    @api_runs.get("/api/scan/runs")
    def api_scan_runs():
        root = Path(app.config["REPO_ROOT"])
        runs_dir = root / "runs"
        entries = []
        if runs_dir.exists():
            for p in sorted(runs_dir.iterdir()):
                if p.is_dir():
                    sub_files = list(p.rglob("*"))
                    entries.append(
                        {
                            "name": p.name,
                            "files": len([f for f in sub_files if f.is_file()]),
                            "size_mb": round(
                                sum(f.stat().st_size for f in sub_files if f.is_file())
                                / 1e6,
                                1,
                            ),
                        }
                    )
        return jsonify(runs=entries)

    @api_runs.get("/api/ingest/status")
    def api_ingest_status():
        from modules.merge_geotiffs import group_split_files, _PAT_WEEK

        root = Path(app.config["REPO_ROOT"])
        raw_base = root / "data" / "raw"
        result = {}
        if raw_base.exists():
            for d in sorted(raw_base.iterdir()):
                if not d.is_dir():
                    continue
                groups = group_split_files(d)
                canonical = 0
                single = 0
                multi = 0
                for key, files in groups.items():
                    if any(_PAT_WEEK.match(f.name) for f in files):
                        canonical += 1
                    elif len(files) == 1:
                        single += 1
                    else:
                        multi += 1
                result[d.name] = {
                    "path": str(d),
                    "total_files": len(list(d.glob("*.tif*"))),
                    "total_groups": len(groups),
                    "canonical": canonical,
                    "needs_normalize": single,
                    "needs_merge": multi,
                }
        return jsonify(datasets=result)

    app.register_blueprint(api_runs)
