from __future__ import annotations

import io
import json
import os
from redis import Redis
from rq import Queue
from authlib.integrations.flask_client import OAuth

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
    session,
    url_for,
)

from modules.google_user_oauth import (
    DEFAULT_SCOPES,
    discover_google_oauth_client_secret_file,
    get_google_oauth_redirect_uri,
    get_google_web_client_config,
)
from modules.google_user_oauth import build_google_credentials_from_oauth_token
from modules.persistence.sqlite_store import SQLiteStore


_FAKE_REDIS_SERVER = None


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: str
    section: str
    action: str
    command: list[str]
    status: str
    enqueued_at: str


def _make_redis_conn(*, decode_responses: bool) -> Redis:
    if os.environ.get("USE_FAKEREDIS") == "1":
        try:
            from fakeredis import FakeServer, FakeStrictRedis

            global _FAKE_REDIS_SERVER
            if _FAKE_REDIS_SERVER is None:
                _FAKE_REDIS_SERVER = FakeServer()
            return FakeStrictRedis(
                server=_FAKE_REDIS_SERVER,
                decode_responses=decode_responses,
            )
        except ImportError:
            pass
    return Redis(decode_responses=decode_responses)


def get_redis_conn() -> Redis:
    return _make_redis_conn(decode_responses=True)


def get_queue_redis_conn() -> Redis:
    return _make_redis_conn(decode_responses=False)


def get_queue_conn() -> Queue:
    return Queue(connection=get_queue_redis_conn())


def get_oauth_client(oauth: OAuth):
    return getattr(oauth, "google", oauth)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_allowed_preview_path(repo_root: Path, raw_path: str) -> Path:
    allowed_roots = [
        (repo_root / "data").resolve(),
        (repo_root / "reports").resolve(),
        (repo_root / "runs").resolve(),
    ]
    path = Path(raw_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    if not any(path == root or root in path.parents for root in allowed_roots):
        raise PermissionError(raw_path)
    return path


def _normalize_channel(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    finite = np.isfinite(x)
    if not bool(np.any(finite)):
        return np.zeros_like(x, dtype=np.uint8)  # Return black if all NaN
    vals = x[finite]
    lo = float(np.percentile(vals, 2.0))
    hi = float(np.percentile(vals, 98.0))
    if hi <= lo:
        hi = lo + 1e-6
    y = np.where(finite, (x - lo) / (hi - lo), 0.0)  # Map NaN to 0
    y = np.clip(y, 0.0, 1.0)
    return (y * 255.0).astype(np.uint8)


def _to_rgb(chw: np.ndarray) -> np.ndarray:
    if chw.ndim != 3:
        raise ValueError("Expected CHW array")
    c, h, w = chw.shape
    if c <= 0:
        raise ValueError("No channels to render")

    # Handle fully NaN / zero case by returning a distinct color (e.g. dark red grid or blank)
    if not np.isfinite(chw).any():
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        # Add a cross pattern or checkerboard to indicate "Missing Data" instead of just black
        rgb[::2, ::2, 0] = 128
        rgb[1::2, 1::2, 0] = 128
        return rgb

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
    plt.imsave(buf, rgb_u8, format="png")
    buf.seek(0)
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
    secret_key = os.environ.get("WEBUI_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("WEBUI_SECRET_KEY environment variable is required")
    app.config["SECRET_KEY"] = secret_key
    app.config["REPO_ROOT"] = root
    app.config["JOB_HISTORY"] = []
    app_db_path = Path(os.environ.get("APP_DB_PATH", str(root / "instance" / "app.db")))
    sqlite_store = SQLiteStore(app_db_path)
    sqlite_store.ensure_schema()
    app.config["APP_DB_PATH"] = app_db_path
    app.config["SQLITE_STORE"] = sqlite_store
    app_settings = sqlite_store.get_settings()
    app.config["APP_SETTINGS"] = app_settings

    if app_settings["initialized"]:
        secret_path = app_settings.get("oauth_client_secret_path")
        redirect_base = app_settings.get("redirect_base_url")
        if secret_path and not os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE"):
            os.environ["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = str(secret_path)
        if redirect_base and not os.environ.get("GOOGLE_OAUTH_REDIRECT_URI"):
            os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = (
                str(redirect_base).rstrip("/") + "/auth/callback"
            )
    elif os.environ.get("ALLOW_ENV_BOOTSTRAP") == "1":
        if not os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE"):
            discovered_secret = discover_google_oauth_client_secret_file([root])
            if discovered_secret is not None:
                os.environ["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = str(discovered_secret)

    try:
        client_id, client_secret, project_id = get_google_web_client_config()
    except Exception:
        client_id, client_secret, project_id = "dummy_id", "dummy_secret", None

    if project_id and not os.environ.get("GOOGLE_PROJECT_ID"):
        os.environ["GOOGLE_PROJECT_ID"] = project_id

    oauth = OAuth(app)
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": " ".join(DEFAULT_SCOPES)},
    )

    @app.route("/login")
    def login() -> Response:
        if not app.config["APP_SETTINGS"]["initialized"]:
            return redirect(url_for("setup"))
        redirect_base = app.config["APP_SETTINGS"].get("redirect_base_url")
        if redirect_base:
            redirect_uri = str(redirect_base).rstrip("/") + "/auth/callback"
        else:
            redirect_uri = get_google_oauth_redirect_uri() or url_for(
                "auth", _external=True
            )
        return get_oauth_client(oauth).authorize_redirect(redirect_uri)

    @app.route("/setup", methods=["GET", "POST"])
    def setup() -> Response | str:
        step = request.args.get("step", "1")
        if request.method == "POST":
            step = request.form.get("step", "1")
            if step == "3":
                secret_path = request.form.get("oauth_client_secret_path", "").strip()
                uploaded_secret = request.files.get("oauth_client_secret_upload")
                redirect_base = (
                    request.form.get("redirect_base_url", "").strip().rstrip("/")
                )
                if uploaded_secret and uploaded_secret.filename:
                    state_dir = app.config["APP_DB_PATH"].parent
                    state_dir.mkdir(parents=True, exist_ok=True)
                    uploaded_name = (
                        Path(uploaded_secret.filename).name or "client_secret.json"
                    )
                    secret_path = str(state_dir / uploaded_name)
                    uploaded_secret.save(secret_path)

                if not secret_path or not Path(secret_path).exists():
                    flash("OAuth client secret path is missing or invalid.", "error")
                    return render_template(
                        "setup.html", step=2, db_ok=True, redis_ok=True
                    )
                if not redirect_base:
                    flash("Redirect base URL is required.", "error")
                    return render_template(
                        "setup.html", step=2, db_ok=True, redis_ok=True
                    )

                sqlite_store.save_settings(
                    initialized=True,
                    oauth_client_secret_path=secret_path,
                    redirect_base_url=redirect_base,
                )
                app.config["APP_SETTINGS"] = sqlite_store.get_settings()
                os.environ["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = secret_path
                os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = (
                    redirect_base + "/auth/callback"
                )
                flash("Initialization saved.", "success")
                return render_template("setup.html", step=3, db_ok=True, redis_ok=True)

        if step == "2":
            return render_template("setup.html", step=2, db_ok=True, redis_ok=True)

        # Step 1 - System Checks
        db_ok = app.config["APP_DB_PATH"].exists() or True
        redis_ok = False
        try:
            redis = get_redis_conn()
            redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

        return render_template("setup.html", step=1, db_ok=True, redis_ok=redis_ok)

    @app.route("/auth/callback")
    def auth() -> Response:
        token = get_oauth_client(oauth).authorize_access_token()
        user = token.get("userinfo") or {}
        google_sub = str(user.get("sub") or "")
        email = str(user.get("email") or "")
        display_name = user.get("name")
        if google_sub:
            local_user = sqlite_store.get_or_create_user(
                google_sub=google_sub,
                email=email,
                display_name=str(display_name) if display_name else None,
            )
            sqlite_store.save_user_oauth_token(user_id=local_user["id"], token=token)
            session["user_id"] = local_user["id"]
        session["user"] = user
        return redirect(url_for("home"))

    @app.route("/logout")
    def logout() -> Response:
        session.pop("user", None)
        user_id = session.pop("user_id", None)
        if user_id:
            sqlite_store.delete_user_oauth_token(user_id)
        return redirect(url_for("login"))

    @app.before_request
    def require_login() -> Response | None:
        allowed_endpoints = {
            "home",
            "setup",
            "login",
            "auth",
            "logout",
            "static",
        }
        if request.endpoint in allowed_endpoints:
            return None
        if request.endpoint is None:
            return None
        if not app.config["APP_SETTINGS"]["initialized"]:
            return redirect(url_for("setup"))
        if "user" not in session:
            return redirect(url_for("login"))
        return None

    def get_raw_data_dirs() -> list[str]:
        raw_base = Path(app.config["REPO_ROOT"]) / "data" / "raw"
        if not raw_base.exists() or not raw_base.is_dir():
            return ["data/raw (Not Found)"]

        dirs = []
        for p in sorted(raw_base.iterdir()):
            if p.is_dir() and any(p.glob("*.tif*")):
                # Return path relative to REPO_ROOT for simplicity in forms
                dirs.append(f"data/raw/{p.name}")

        if not dirs:
            return ["data/raw (Empty)"]
        return dirs

    def get_scanned_raw_tif_paths(limit: int = 100) -> list[str]:
        raw_base = Path(app.config["REPO_ROOT"]) / "data" / "raw"
        if not raw_base.exists() or not raw_base.is_dir():
            return []

        files: list[str] = []
        for p in sorted(raw_base.rglob("*.tif*")):
            if p.is_file():
                files.append(str(p.relative_to(app.config["REPO_ROOT"])))
            if len(files) >= limit:
                break
        return files

    def get_scanned_patch_npz_paths(limit: int = 100) -> list[str]:
        candidates = [
            Path(app.config["REPO_ROOT"]) / "data" / "wheat_risk",
            Path(app.config["REPO_ROOT"]) / "runs",
        ]
        files: list[str] = []
        for base in candidates:
            if not base.exists() or not base.is_dir():
                continue
            for p in sorted(base.rglob("*.npz")):
                if p.is_file():
                    files.append(str(p.relative_to(app.config["REPO_ROOT"])))
                if len(files) >= limit:
                    return files
        return files

    def resolve_path_input(selected_value: str | None, custom_value: str | None) -> str:
        custom = (custom_value or "").strip()
        if custom:
            return custom
        return (selected_value or "").strip()

    @app.get("/")
    def home() -> str:
        mode = request.args.get("mode", "basic").strip().lower()
        if mode not in {"basic", "advanced"}:
            mode = "basic"

        is_authenticated = "user" in session
        if not app.config["APP_SETTINGS"]["initialized"]:
            return redirect(url_for("setup"))
        raw_dirs = get_raw_data_dirs()
        default_raw_dir = raw_dirs[0]
        raw_tif_paths = get_scanned_raw_tif_paths()
        patch_npz_paths = get_scanned_patch_npz_paths()
        default_raw_tif = raw_tif_paths[0] if raw_tif_paths else ""
        default_patch_npz = patch_npz_paths[0] if patch_npz_paths else ""

        return render_template(
            "wheat_risk_webui.html",
            is_authenticated=is_authenticated,
            mode=mode,
            jobs=app.config["JOB_HISTORY"],
            repo_root=str(app.config["REPO_ROOT"]),
            raw_dirs=raw_dirs,
            default_raw_dir=default_raw_dir,
            raw_tif_paths=raw_tif_paths,
            default_raw_tif=default_raw_tif,
            patch_npz_paths=patch_npz_paths,
            default_patch_npz=default_patch_npz,
        )

    @app.get("/api/jobs")
    def jobs_json() -> Response:
        try:
            queue = get_queue_conn()
            jobs = queue.jobs
            rows = []
            for j in jobs:
                rows.append(
                    {
                        "id": str(getattr(j, "id", "")),
                        "action": j.func_name,
                        "status": j.get_status() or "unknown",
                        "started_at": str(j.started_at) if j.started_at else "",
                        "ended_at": str(j.ended_at) if j.ended_at else "",
                    }
                )
            return jsonify(rows)
        except Exception as e:
            return jsonify([{"error": str(e)}])

    @app.post("/run/downloader")
    def run_downloader() -> Response:
        action = request.form.get("action", "preview_export")
        lock_key = f"lock:downloader:{action}"

        try:
            redis = get_redis_conn()
            if redis.get(lock_key):
                flash(f"Downloader action '{action}' is already running.", "error")
                return redirect(url_for("home"))
        except Exception:
            pass  # Fail open if redis is unavailable

        stage = request.form.get("stage", "1").strip()
        start_date = request.form.get("start_date", "2025-01-01").strip()
        end_date = request.form.get("end_date", "2025-12-31").strip()
        limit = request.form.get("limit", "4").strip()
        ee_project = request.form.get("ee_project", "").strip()
        drive_folder = request.form.get("drive_folder", "").strip()
        raw_dir = resolve_path_input(
            request.form.get("raw_dir", "data/raw/france_2025_weekly"),
            request.form.get("raw_dir_custom"),
        )

        queue = get_queue_conn()

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
                "modules.jobs.tasks.task_run_script_for_user",
                args=(
                    {
                        "user_id": session.get("user_id"),
                        "cmd": cmd,
                        "cwd": str(app.config["REPO_ROOT"]),
                    },
                ),
                job_timeout="1h",
                result_ttl="7d",
                description=f"downloader: {action}",
            )
            try:
                redis.set(lock_key, job.id, ex=3600)
            except Exception:
                pass
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
                "start_date_str": start_date,
                "cadence_days": 7,
                "user_id": session.get("user_id"),
            }
            job = queue.enqueue(
                "modules.jobs.tasks.task_run_inventory",
                args=(job_kwargs,),
                job_timeout="1h",
                result_ttl="7d",
                description=f"downloader: {action}",
            )
            try:
                redis.set(lock_key, job.id, ex=3600)
            except Exception:
                pass
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

        lock_key = f"lock:build:{action}:{stage}"
        if action == "build_all":
            lock_key = "lock:build:build_all"

        try:
            redis = get_redis_conn()
            if redis.get(lock_key):
                flash(
                    f"Build action '{action}' for level {stage} is already running.",
                    "error",
                )
                return redirect(url_for("home"))
        except Exception:
            pass

        raw_dir = resolve_path_input(
            request.form.get("raw_dir", "data/raw/france_2025_weekly"),
            request.form.get("raw_dir_custom"),
        )
        max_patches = request.form.get("max_patches", "12000").strip()

        queue = get_queue_conn()

        def _enqueue_build_level(lv: str):
            patch = {"1": "64", "2": "32", "4": "16"}.get(lv, "64")
            job_kwargs = {
                "input_dir": raw_dir,
                "output_dir": f"data/wheat_risk/staged/L{lv}",
                "patch_size": int(patch),
                "step_size": int(patch),
                "expected_weeks": 46,
                "max_patches": int(max_patches),
                "user_id": session.get("user_id"),
            }
            job = queue.enqueue(
                "modules.jobs.tasks.task_build_dataset",
                args=(job_kwargs,),
                job_timeout="1h",
                result_ttl="7d",
                description=f"build: build_L{lv}",
            )
            try:
                redis.set(lock_key, job.id, ex=3600)
            except Exception:
                pass
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
        lock_key = f"lock:train:{action}"

        try:
            redis = get_redis_conn()
            if redis.get(lock_key):
                flash(f"Training action '{action}' is already running.", "error")
                return redirect(url_for("home"))
        except Exception:
            pass

        levels = request.form.get("levels", "1,2,4").strip()
        steps = request.form.get("steps", "100,500,2000").strip()

        queue = get_queue_conn()

        level_list = [x.strip() for x in levels.split(",") if x.strip()]
        steps_list = [int(x.strip()) for x in steps.split(",") if x.strip()]

        job_kwargs = {
            "levels": level_list,
            "steps": steps_list,
            "base_patch": 64,
            "dry_run": action == "dry_run",
            "runs_dir": "runs",
            "train_script": "scripts/train_wheat_risk_lstm.py",
            "user_id": session.get("user_id"),
        }

        if action != "dry_run":
            job_kwargs["execute_train"] = True
            job_kwargs["index_csv_template"] = (
                "./data/wheat_risk/staged/L{level}/index.csv"
            )
            job_kwargs["root_dir_template"] = "./data/wheat_risk/staged/L{level}"
            job_kwargs["device"] = "cuda"
            job_kwargs["epochs"] = 10
            job_kwargs["batch_size"] = 8
            job_kwargs["lr"] = 1e-3
            job_kwargs["embed_dim"] = 64
            job_kwargs["hidden_dim"] = 128
            job_kwargs["num_workers"] = 0
            job_kwargs["seed_base"] = 42

        job = queue.enqueue(
            "modules.jobs.tasks.task_run_matrix",
            args=(job_kwargs,),
            job_timeout="1h",
            result_ttl="7d",
            description=f"train: {action}",
        )
        try:
            redis.set(lock_key, job.id, ex=3600)
        except Exception:
            pass
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
        lock_key = "lock:eval:eval_matrix"
        try:
            redis = get_redis_conn()
            if redis.get(lock_key):
                flash("Evaluation is already running.", "error")
                return redirect(url_for("home"))
        except Exception:
            pass

        queue = get_queue_conn()

        job_kwargs = {
            "summary_csv": "runs/staged_final/summary.csv",
            "index_csv_template": "./data/wheat_risk/staged/L{level}/index.csv",
            "root_dir_template": "./data/wheat_risk/staged/L{level}",
            "output_csv": "runs/staged_final/eval_metrics.csv",
            "best_json": "runs/staged_final/best_model.json",
            "device": "cuda",
            "user_id": session.get("user_id"),
        }

        job = queue.enqueue(
            "modules.jobs.tasks.task_run_eval",
            args=(job_kwargs,),
            job_timeout="1h",
            result_ttl="7d",
            description=f"eval: eval_matrix",
        )
        try:
            redis.set(lock_key, job.id, ex=3600)
        except Exception:
            pass
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

    def _build_drive_service() -> Any:
        google_token = session.get("google_token")
        if not google_token:
            return None
        try:
            import googleapiclient.discovery  # type: ignore

            creds = build_google_credentials_from_oauth_token(google_token)
            return googleapiclient.discovery.build("drive", "v3", credentials=creds)
        except Exception:
            return None

    @app.get("/api/drive/list")
    def drive_list() -> Response:
        svc = _build_drive_service()
        if svc is None:
            return jsonify({"error": "Not authenticated with Drive"}), 401
        folder_id = request.args.get("id", "root")
        try:
            q_folders = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed = false"
            resp = (
                svc.files()
                .list(
                    q=q_folders,
                    fields="files(id, name, mimeType)",
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            folders = [
                {"id": f["id"], "name": f["name"], "type": "folder"}
                for f in resp.get("files", [])
            ]
            q_files = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed = false"
            resp_files = (
                svc.files()
                .list(
                    q=q_files,
                    fields="files(id, name, mimeType, size)",
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            files = []
            for f in resp_files.get("files", []):
                files.append(
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "type": "file",
                        "size": int(f["size"]) if "size" in f else None,
                    }
                )
            return jsonify({"folder_id": folder_id, "folders": folders, "files": files})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/drive/estimate")
    def drive_estimate() -> Response:
        svc = _build_drive_service()
        if svc is None:
            return jsonify({"error": "Not authenticated with Drive"}), 401
        folder_id = request.args.get("folder_id", "")
        if not folder_id:
            return jsonify({"error": "folder_id required"}), 400
        try:
            from modules.drive_oauth import list_folder_files

            all_files = list_folder_files(svc, folder_id=folder_id)
            tif_files = [
                f for f in all_files if f.name.lower().endswith((".tif", ".tiff"))
            ]
            total_size = sum(f.size or 0 for f in tif_files)
            return jsonify(
                {
                    "folder_id": folder_id,
                    "total_files": len(all_files),
                    "tif_files": len(tif_files),
                    "total_size": total_size,
                    "total_size_human": _human_bytes(total_size),
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/drive/download")
    def drive_download() -> Response:
        svc = _build_drive_service()
        if svc is None:
            return jsonify({"error": "Not authenticated with Drive"}), 401
        folder_id = request.form.get("folder_id", "").strip()
        save_dir = request.form.get("save_dir", "data/raw/drive_download").strip()
        if not folder_id:
            return jsonify({"error": "folder_id required"}), 400

        queue = get_queue_conn()
        job_kwargs = {
            "folder_id": folder_id,
            "save_dir": save_dir,
            "oauth_token": session.get("google_token"),
        }
        job = queue.enqueue(
            "modules.jobs.tasks.task_drive_download",
            args=(job_kwargs,),
            job_timeout="2h",
            result_ttl="7d",
            description=f"drive_download: {folder_id}",
        )
        rec = JobRecord(
            id=job.id,
            section="drive",
            action="download",
            command=["task_drive_download"],
            status="enqueued",
            enqueued_at=_now_iso(),
        )
        app.config["JOB_HISTORY"].insert(0, rec)
        app.config["JOB_HISTORY"] = app.config["JOB_HISTORY"][:100]
        flash(f"Drive download enqueued (job {job.id}).", "success")
        return redirect(url_for("home"))

    def _human_bytes(n: float) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(n) < 1024:
                return f"{n:.2f} {unit}"
            n /= 1024
        return f"{n:.2f} PB"

    @app.get("/plots/evaluation.png")
    def evaluation_plot() -> Response:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        fig = Figure(figsize=(6, 3))
        ax = fig.subplots()
        ax.set_title("Evaluation Metrics Preview")
        ax.set_xlabel("No data loaded")
        ax.set_yticks([])
        ax.set_xticks([])
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        return Response(buf.getvalue(), mimetype="image/png")

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

        try:
            path = _resolve_allowed_preview_path(app.config["REPO_ROOT"], p)
        except PermissionError:
            return Response("Forbidden", status=403)
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

        try:
            path = _resolve_allowed_preview_path(app.config["REPO_ROOT"], p)
        except PermissionError:
            return Response("Forbidden", status=403)
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
