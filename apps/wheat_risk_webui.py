from __future__ import annotations

import io
from redis import Redis
from rq import Queue

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: str
    section: str
    action: str
    command: list[str]
    status: str
    enqueued_at: str


def get_queue() -> Queue:
    # In a real app, this would be configured
    return Queue(connection=Redis())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_channel(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    finite = np.isfinite(x)
    if not bool(np.any(finite)):
        return np.zeros_like(x, dtype=np.uint8)
    vals = x[finite]
    lo = float(np.percentile(vals, 2.0))
    hi = float(np.percentile(vals, 98.0))
    if hi <= lo:
        hi = lo + 1e-6
    y = np.nan_to_num(x, nan=lo, posinf=hi, neginf=lo)
    y = np.clip((y - lo) / (hi - lo), 0.0, 1.0)
    return (y * 255.0).astype(np.uint8)


def _to_rgb(chw: np.ndarray) -> np.ndarray:
    if chw.ndim != 3:
        raise ValueError("Expected CHW array")
    c = int(chw.shape[0])
    if c <= 0:
        raise ValueError("No channels to render")

    if c == 1:
        c0 = _normalize_channel(chw[0])
        return np.stack([c0, c0, c0], axis=-1)
    if c == 2:
        c0 = _normalize_channel(chw[0])
        c1 = _normalize_channel(chw[1])
        return np.stack([c0, c1, c0], axis=-1)
    c0 = _normalize_channel(chw[0])
    c1 = _normalize_channel(chw[1])
    c2 = _normalize_channel(chw[2])
    return np.stack([c0, c1, c2], axis=-1)


def _downsample_chw(chw: np.ndarray, max_size: int) -> np.ndarray:
    if max_size <= 0:
        return chw
    _, h, w = chw.shape
    scale = int(np.ceil(max(h, w) / float(max_size)))
    if scale <= 1:
        return chw
    return chw[:, ::scale, ::scale]


def _render_png(rgb: np.ndarray) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    rgb_u8 = np.asarray(rgb, dtype=np.uint8)
    buf = io.BytesIO()
    plt.imsave(buf, rgb_u8)
    return buf.getvalue()


def _parse_int_csv(text: str, *, one_based: bool = False) -> list[int]:
    out: list[int] = []
    for p in str(text).split(","):
        p2 = p.strip()
        if not p2:
            continue
        n = int(p2)
        if one_based:
            if n <= 0:
                raise ValueError("Band indices must be >= 1")
        else:
            if n < 0:
                raise ValueError("Indices must be >= 0")
        out.append(n)
    if not out:
        raise ValueError("At least one index is required")
    return out


def create_app(repo_root: Path | str | None = None) -> Flask:
    app_root = Path(__file__).resolve().parent
    root = Path(repo_root) if repo_root is not None else app_root.parent

    app = Flask(
        __name__,
        template_folder=str(app_root / "templates"),
        static_folder=str(app_root / "static"),
    )
    app.config["SECRET_KEY"] = "wheat-risk-webui-dev"
    app.config["REPO_ROOT"] = root
    app.config["JOB_HISTORY"] = []

    @app.get("/")
    def home() -> str:
        mode = request.args.get("mode", "basic").strip().lower()
        if mode not in {"basic", "advanced"}:
            mode = "basic"
        return render_template(
            "wheat_risk_webui.html",
            mode=mode,
            jobs=app.config["JOB_HISTORY"],
            repo_root=str(app.config["REPO_ROOT"]),
        )

    @app.get("/api/jobs")
    def jobs_json() -> Response:
        q = get_queue()
        rows = []
        for rec in app.config["JOB_HISTORY"]:
            job = q.fetch_job(rec.id)
            status = job.get_status() if job else "unknown"
            rows.append(
                {
                    "id": rec.id,
                    "section": rec.section,
                    "action": rec.action,
                    "command": " ".join(rec.command),
                    "status": status,
                    "enqueued_at": rec.enqueued_at,
                }
            )
        return jsonify(rows)

    @app.post("/run/downloader")
    def run_downloader() -> Response:
        action = request.form.get("action", "preview_export")
        stage = request.form.get("stage", "1").strip()
        start_date = request.form.get("start_date", "2025-01-01").strip()
        end_date = request.form.get("end_date", "2025-12-31").strip()
        limit = request.form.get("limit", "4").strip()
        ee_project = request.form.get("ee_project", "").strip()
        drive_folder = request.form.get("drive_folder", "").strip()
        raw_dir = request.form.get("raw_dir", "data/raw/france_2025_weekly").strip()

        queue = get_queue()

        if action in {"preview_export", "run_export"}:
            cmd = [
                "uv",
                "run",
                "scripts/export_weekly_risk_rasters.py",
                "--stage",
                stage,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--limit",
                limit,
            ]
            if ee_project:
                cmd.extend(["--ee-project", ee_project])
            if drive_folder:
                cmd.extend(["--drive-folder", drive_folder])
            if action == "preview_export":
                cmd.append("--dry-run")
            else:
                cmd.append("--run")

            job = queue.enqueue(
                "modules.jobs.tasks.run_script",
                args=(cmd,),
                job_timeout="1h",
                result_ttl="7d",
                kwargs={"cwd": str(app.config["REPO_ROOT"])},
                description=f"downloader: {action}",
            )
            rec = JobRecord(
                id=job.id,
                section="downloader",
                action=action,
                command=cmd,
                status="enqueued",
                enqueued_at=_now_iso(),
            )
            app.config["JOB_HISTORY"].insert(0, rec)
            app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]

        elif action == "refresh_inventory":
            job_kwargs = {
                "input_dir": raw_dir,
                "output_dir": "reports",
                "start_date": start_date,
                "cadence_days": 7,
            }
            job = queue.enqueue(
                "modules.jobs.tasks.task_run_inventory",
                args=(job_kwargs,),
                job_timeout="1h",
                result_ttl="7d",
                description=f"downloader: {action}",
            )
            rec = JobRecord(
                id=job.id,
                section="downloader",
                action=action,
                command=["task_run_inventory"],
                status="enqueued",
                enqueued_at=_now_iso(),
            )
            app.config["JOB_HISTORY"].insert(0, rec)
            app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]
        else:
            flash(f"Unknown downloader action: {action}", "error")
            return redirect(url_for("home"))

        flash(f"Downloader action '{action}' enqueued.", "success")
        return redirect(url_for("home"))

    @app.post("/run/build")
    def run_build() -> Response:
        action = request.form.get("action", "build_level").strip()
        stage = request.form.get("level", "1").strip()
        raw_dir = request.form.get("raw_dir", "data/raw/france_2025_weekly").strip()
        max_patches = request.form.get("max_patches", "12000").strip()

        queue = get_queue()

        def _enqueue_build_level(lv: str):
            patch = {"1": "64", "2": "32", "4": "16"}.get(lv, "64")
            job_kwargs = {
                "input_dir": raw_dir,
                "output_dir": f"data/wheat_risk/staged/L{lv}",
                "patch_size": int(patch),
                "step_size": int(patch),
                "expected_weeks": 46,
                "max_patches": int(max_patches),
            }
            job = queue.enqueue(
                "modules.jobs.tasks.task_build_dataset",
                args=(job_kwargs,),
                job_timeout="1h",
                result_ttl="7d",
                description=f"build: build_L{lv}",
            )
            rec = JobRecord(
                id=job.id,
                section="build",
                action=f"build_L{lv}" if action == "build_all" else action,
                command=["task_build_dataset"],
                status="enqueued",
                enqueued_at=_now_iso(),
            )
            app.config["JOB_HISTORY"].insert(0, rec)
            app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]

        if action == "build_level":
            _enqueue_build_level(stage)
            flash(f"Build L{stage} enqueued.", "success")
            return redirect(url_for("home"))

        if action == "build_all":
            for lv in ["1", "2", "4"]:
                _enqueue_build_level(lv)
            flash("Build all enqueued.", "success")
            return redirect(url_for("home"))

        flash(f"Unknown build action: {action}", "error")
        return redirect(url_for("home"))

    @app.post("/run/train")
    def run_train_matrix() -> Response:
        action = request.form.get("action", "dry_run").strip()
        levels = request.form.get("levels", "1,2,4").strip()
        steps = request.form.get("steps", "100,500,2000").strip()

        queue = get_queue()

        level_list = [x.strip() for x in levels.split(",") if x.strip()]
        steps_list = [int(x.strip()) for x in steps.split(",") if x.strip()]

        job_kwargs = {
            "levels": level_list,
            "steps": steps_list,
            "base_patch": 64,
            "dry_run": action == "dry_run",
            "runs_dir": "runs",
            "train_script": "scripts/train_staged_model.py",
        }

        if action != "dry_run":
            job_kwargs["execute_train"] = True
            job_kwargs["index_csv"] = "./data/wheat_risk/staged/L{level}/index.csv"
            job_kwargs["root_dir"] = "./data/wheat_risk/staged/L{level}"
            job_kwargs["device"] = "cuda"

        job = queue.enqueue(
            "modules.jobs.tasks.task_run_matrix",
            args=(job_kwargs,),
            job_timeout="1h",
            result_ttl="7d",
            description=f"train: {action}",
        )
        rec = JobRecord(
            id=job.id,
            section="train",
            action=action,
            command=["task_run_matrix"],
            status="enqueued",
            enqueued_at=_now_iso(),
        )
        app.config["JOB_HISTORY"].insert(0, rec)
        app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]

        flash(f"Training action '{action}' enqueued.", "success")
        return redirect(url_for("home"))

    @app.post("/run/eval")
    def run_eval() -> Response:
        queue = get_queue()

        job_kwargs = {
            "summary_csv": "runs/staged_final/summary.csv",
            "index_csv_template": "./data/wheat_risk/staged/L{level}/index.csv",
            "root_dir_template": "./data/wheat_risk/staged/L{level}",
            "output_csv": "runs/staged_final/eval_metrics.csv",
            "best_json": "runs/staged_final/best_model.json",
            "device": "cuda",
        }

        job = queue.enqueue(
            "modules.jobs.tasks.task_run_eval",
            args=(job_kwargs,),
            job_timeout="1h",
            result_ttl="7d",
            description=f"eval: eval_matrix",
        )
        rec = JobRecord(
            id=job.id,
            section="eval",
            action="eval_matrix",
            command=["task_run_eval"],
            status="enqueued",
            enqueued_at=_now_iso(),
        )
        app.config["JOB_HISTORY"].insert(0, rec)
        app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]

        flash("Evaluation enqueued.", "success")
        return redirect(url_for("home"))

    @app.get("/api/preview/raw")
    def preview_raw() -> Response:
        rasterio = __import__("rasterio")
        p = request.args.get("path", "").strip()
        if not p:
            return Response("Missing path", status=400)
        bands_txt = request.args.get("bands", "1,2,3")
        max_size = int(request.args.get("max_size", "512"))
        try:
            band_idx = _parse_int_csv(bands_txt, one_based=True)
        except Exception as e:
            return Response(f"Invalid bands: {e}", status=400)

        path = Path(p)
        if not path.exists():
            return Response(f"Not found: {path}", status=404)

        with rasterio.open(path) as ds:
            arr = ds.read(indexes=band_idx).astype(np.float32, copy=False)
        arr = _downsample_chw(arr, max_size=max_size)
        rgb = _to_rgb(arr)
        return Response(_render_png(rgb), mimetype="image/png")

    @app.get("/api/preview/patch")
    def preview_patch() -> Response:
        p = request.args.get("path", "").strip()
        if not p:
            return Response("Missing path", status=400)
        t = int(request.args.get("t", "0"))
        channels_txt = request.args.get("channels", "0,1,2")
        max_size = int(request.args.get("max_size", "512"))
        try:
            ch_idx = _parse_int_csv(channels_txt, one_based=False)
        except Exception as e:
            return Response(f"Invalid channels: {e}", status=400)

        path = Path(p)
        if not path.exists():
            return Response(f"Not found: {path}", status=404)

        with np.load(path, allow_pickle=False) as z:
            if "X" not in z:
                return Response("NPZ missing X", status=400)
            x = z["X"].astype(np.float32, copy=False)

        if x.ndim != 4:
            return Response("X must be (T,C,H,W)", status=400)
        if t < 0 or t >= int(x.shape[0]):
            return Response(f"t out of range [0,{x.shape[0] - 1}]", status=400)

        cmax = int(x.shape[1])
        for c in ch_idx:
            if c >= cmax:
                return Response(f"channel {c} out of range [0,{cmax - 1}]", status=400)

        chw = x[t, ch_idx, :, :]
        chw = _downsample_chw(chw, max_size=max_size)
        rgb = _to_rgb(chw)
        return Response(_render_png(rgb), mimetype="image/png")

    return app


def main() -> int:
    app = create_app()
    app.run(host="0.0.0.0", port=5055, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
