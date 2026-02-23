from __future__ import annotations

import io
import subprocess
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
    id: int
    section: str
    action: str
    command: list[str]
    returncode: int
    started_at: str
    ended_at: str
    stdout: str
    stderr: str


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
    app.config["NEXT_JOB_ID"] = 1

    def _append_job(
        *,
        section: str,
        action: str,
        command: list[str],
        returncode: int,
        started_at: str,
        ended_at: str,
        stdout: str,
        stderr: str,
    ) -> None:
        jid = int(app.config["NEXT_JOB_ID"])
        app.config["NEXT_JOB_ID"] = jid + 1
        rec = JobRecord(
            id=jid,
            section=section,
            action=action,
            command=command,
            returncode=int(returncode),
            started_at=started_at,
            ended_at=ended_at,
            stdout=stdout,
            stderr=stderr,
        )
        app.config["JOB_HISTORY"].insert(0, rec)
        app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]

    def _run_job(section: str, action: str, cmd: list[str]) -> JobRecord:
        started = _now_iso()
        proc = subprocess.run(
            cmd,
            cwd=str(app.config["REPO_ROOT"]),
            text=True,
            capture_output=True,
            check=False,
        )
        ended = _now_iso()
        _append_job(
            section=section,
            action=action,
            command=cmd,
            returncode=int(proc.returncode),
            started_at=started,
            ended_at=ended,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
        return app.config["JOB_HISTORY"][0]

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
        rows = [
            {
                "id": j.id,
                "section": j.section,
                "action": j.action,
                "command": " ".join(j.command),
                "returncode": j.returncode,
                "started_at": j.started_at,
                "ended_at": j.ended_at,
            }
            for j in app.config["JOB_HISTORY"]
        ]
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
        elif action == "refresh_inventory":
            cmd = [
                "uv",
                "run",
                "scripts/inventory_wheat_dates.py",
                "--input-dir",
                raw_dir,
                "--output-dir",
                "reports",
                "--start-date",
                start_date,
                "--cadence-days",
                "7",
            ]
        else:
            flash(f"Unknown downloader action: {action}", "error")
            return redirect(url_for("home"))

        rec = _run_job("downloader", action, cmd)
        if rec.returncode == 0:
            flash(f"Downloader action '{action}' finished successfully.", "success")
        else:
            flash(
                f"Downloader action '{action}' failed (code {rec.returncode}).", "error"
            )
        return redirect(url_for("home"))

    @app.post("/run/build")
    def run_build() -> Response:
        action = request.form.get("action", "build_level").strip()
        stage = request.form.get("level", "1").strip()
        raw_dir = request.form.get("raw_dir", "data/raw/france_2025_weekly").strip()
        max_patches = request.form.get("max_patches", "12000").strip()

        def _cmd_for_level(level: str) -> list[str]:
            patch = {"1": "64", "2": "32", "4": "16"}.get(level, "64")
            return [
                "uv",
                "run",
                "scripts/build_npz_dataset_from_geotiffs.py",
                "--input-dir",
                raw_dir,
                "--output-dir",
                f"data/wheat_risk/staged/L{level}",
                "--patch-size",
                patch,
                "--step-size",
                patch,
                "--expected-weeks",
                "46",
                "--max-patches",
                max_patches,
            ]

        if action == "build_level":
            rec = _run_job("build", action, _cmd_for_level(stage))
            flash(
                f"Build L{stage} {'ok' if rec.returncode == 0 else 'failed'}.",
                "success" if rec.returncode == 0 else "error",
            )
            return redirect(url_for("home"))

        if action == "build_all":
            fail = 0
            for lv in ["1", "2", "4"]:
                rec = _run_job("build", f"build_L{lv}", _cmd_for_level(lv))
                if rec.returncode != 0:
                    fail += 1
            flash(
                "Build all completed."
                if fail == 0
                else f"Build all finished with {fail} failure(s).",
                "success" if fail == 0 else "error",
            )
            return redirect(url_for("home"))

        flash(f"Unknown build action: {action}", "error")
        return redirect(url_for("home"))

    @app.post("/run/train")
    def run_train_matrix() -> Response:
        action = request.form.get("action", "dry_run").strip()
        levels = request.form.get("levels", "1,2,4").strip()
        steps = request.form.get("steps", "100,500,2000").strip()

        cmd = [
            "uv",
            "run",
            "scripts/run_staged_training_matrix.py",
            "--levels",
            levels,
            "--steps",
            steps,
            "--base-patch",
            "64",
        ]
        if action == "dry_run":
            cmd.append("--dry-run")
        else:
            cmd.extend(
                [
                    "--run",
                    "--execute-train",
                    "--index-csv-template",
                    "./data/wheat_risk/staged/L{level}/index.csv",
                    "--root-dir-template",
                    "./data/wheat_risk/staged/L{level}",
                    "--device",
                    "cuda",
                ]
            )

        rec = _run_job("train", action, cmd)
        flash(
            f"Training action '{action}' {'ok' if rec.returncode == 0 else 'failed'}.",
            "success" if rec.returncode == 0 else "error",
        )
        return redirect(url_for("home"))

    @app.post("/run/eval")
    def run_eval() -> Response:
        cmd = [
            "uv",
            "run",
            "scripts/eval_staged_training_matrix.py",
            "--summary-csv",
            "runs/staged_final/summary.csv",
            "--index-csv-template",
            "./data/wheat_risk/staged/L{level}/index.csv",
            "--root-dir-template",
            "./data/wheat_risk/staged/L{level}",
            "--output-csv",
            "runs/staged_final/eval_metrics.csv",
            "--best-json",
            "runs/staged_final/best_model.json",
            "--device",
            "cuda",
        ]
        rec = _run_job("eval", "eval_matrix", cmd)
        flash(
            f"Evaluation {'ok' if rec.returncode == 0 else 'failed'}.",
            "success" if rec.returncode == 0 else "error",
        )
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
