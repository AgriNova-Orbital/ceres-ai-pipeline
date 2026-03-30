"""Admin API Blueprint - system info, job queue, worker status."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from flask import Blueprint, jsonify


def register_admin_api(app, sqlite_store, redis_conn, job_history) -> None:
    api_admin = Blueprint("api_admin", __name__)
    @api_admin.get("/api/admin/system")
    def system_info():
        disk = shutil.disk_usage("/app")
        return jsonify(
            cpu_count=os.cpu_count(),
            load_avg=list(os.getloadavg()),
            disk_total_gb=round(disk.total / 1e9, 1),
            disk_used_gb=round(disk.used / 1e9, 1),
            disk_free_gb=round(disk.free / 1e9, 1),
            disk_percent=round(disk.used / disk.total * 100, 1),
        )

    @api_admin.get("/api/admin/workers")
    def worker_status():
        try:
            from rq import Worker

            workers = Worker.all(connection=redis_conn)
            return jsonify(
                workers=[
                    {
                        "name": w.name,
                        "state": w.get_state(),
                        "current_job": w.get_current_job_id(),
                        "birth_date": w.birth_date.isoformat()
                        if w.birth_date
                        else None,
                    }
                    for w in workers
                ]
            )
        except Exception as e:
            return jsonify(workers=[], error=str(e))

    @api_admin.get("/api/admin/queue")
    def queue_status():
        try:
            from rq import Queue

            q = Queue(connection=redis_conn)
            return jsonify(
                name=q.name,
                length=len(q),
                failed_count=q.failed_job_registry.count
                if hasattr(q, "failed_job_registry")
                else 0,
            )
        except Exception as e:
            return jsonify(error=str(e))

    @api_admin.get("/api/admin/jobs")
    def job_history_list():
        return jsonify(jobs=[vars(j) for j in job_history[:50]])

    @api_admin.get("/api/admin/data")
    def data_overview():
        root = Path("/app")
        data = {}
        for name in ["data", "runs", "reports", "logs"]:
            p = root / name
            if p.exists():
                files = list(p.rglob("*"))
                data[name] = {
                    "path": str(p),
                    "total_files": len([f for f in files if f.is_file()]),
                    "total_dirs": len([d for d in files if d.is_dir()]),
                    "size_mb": round(
                        sum(f.stat().st_size for f in files if f.is_file()) / 1e6, 1
                    ),
                }
            else:
                data[name] = {
                    "path": str(p),
                    "total_files": 0,
                    "total_dirs": 0,
                    "size_mb": 0,
                }
        return jsonify(data)

    @api_admin.get("/api/admin/database")
    def database_info():
        db_path = Path(os.environ.get("APP_DB_PATH", "/app/state/app.db"))
        info = {
            "path": str(db_path),
            "exists": db_path.exists(),
            "size_kb": round(db_path.stat().st_size / 1024, 1)
            if db_path.exists()
            else 0,
        }
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            info["tables"] = [t[0] for t in tables]
            info["user_count"] = (
                conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                if any(t[0] == "users" for t in tables)
                else 0
            )
            conn.close()
        except Exception:
            pass
        return jsonify(info)

    @api_admin.get("/api/admin/redis")
    def redis_info():
        try:
            info = redis_conn.info()
            return jsonify(
                connected=True,
                used_memory_mb=round(info.get("used_memory", 0) / 1e6, 1),
                connected_clients=info.get("connected_clients", 0),
                uptime_days=round(info.get("uptime_in_seconds", 0) / 86400, 1),
                total_commands=info.get("total_commands_processed", 0),
            )
        except Exception as e:
            return jsonify(connected=False, error=str(e))

    app.register_blueprint(api_admin)
