"""OAuth API Blueprint - Google OAuth with fresh client per request."""

from __future__ import annotations

import json
import os
from pathlib import Path

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, jsonify, redirect, request, session

from modules.google_user_oauth import (
    DEFAULT_SCOPES,
    get_google_web_client_config,
)

api_oauth = Blueprint("api_oauth", __name__)

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def register_oauth_api(app, sqlite_store) -> None:
    api_oauth = Blueprint("api_oauth", __name__)
    """Register OAuth API routes.

    Key design: Creates a FRESH OAuth() + client per request to avoid
    authlib's in-memory client cache (which breaks multi-worker setups).
    """

    def _create_google_client() -> OAuth | None:
        """Create a fresh OAuth client, or None if not configured."""
        settings = sqlite_store.get_settings()
        secret_path = settings.get("oauth_client_secret_path")
        if not secret_path or not Path(secret_path).exists():
            # Try auto-discovery
            from modules.google_user_oauth import (
                discover_google_oauth_client_secret_file,
            )

            root = Path(app.config["REPO_ROOT"])
            discovered = discover_google_oauth_client_secret_file([root])
            if discovered:
                secret_path = str(discovered)
                sqlite_store.save_settings(
                    initialized=True,
                    oauth_client_secret_path=secret_path,
                    redirect_base_url=settings.get("redirect_base_url"),
                )
            else:
                return None

        try:
            os.environ["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = secret_path
            cid, csecret, _ = get_google_web_client_config()
            if cid == "dummy_id":
                return None
        except Exception:
            return None

        # Fresh OAuth instance per call — no shared cache
        oauth = OAuth(app)
        oauth.register(
            name="google",
            client_id=cid,
            client_secret=csecret,
            server_metadata_url=GOOGLE_METADATA,
            client_kwargs={"scope": " ".join(DEFAULT_SCOPES)},
        )
        return oauth

    @api_oauth.get("/api/oauth/login")
    def oauth_login():
        oauth = _create_google_client()
        if oauth is None:
            return jsonify(
                error="Google OAuth not configured. Upload client_secret.json in Settings."
            ), 400

        settings = sqlite_store.get_settings()
        base = settings.get("redirect_base_url") or request.host_url.rstrip("/")
        redirect_uri = f"{base}/api/oauth/callback"
        return oauth.google.authorize_redirect(
            redirect_uri,
            access_type="offline",
            prompt="consent",
        )

    @api_oauth.get("/api/oauth/callback")
    def oauth_callback():
        oauth = _create_google_client()
        if oauth is None:
            return redirect("/login?error=oauth_not_configured")

        try:
            token = oauth.google.authorize_access_token()
        except Exception as e:
            return redirect(f"/login?error=oauth_failed&detail={str(e)[:100]}")

        user = token.get("userinfo") or {}
        google_sub = str(user.get("sub") or "")
        email = str(user.get("email") or "")
        display_name = user.get("name")

        if not google_sub:
            return redirect("/login?error=no_userinfo")

        # Store user in DB (for Drive access tracking)
        local_user = sqlite_store.get_or_create_user(
            google_sub=google_sub,
            email=email,
            display_name=str(display_name) if display_name else None,
        )

        # Preserve refresh_token if Google doesn't resend it on re-auth
        existing_token = sqlite_store.get_user_oauth_token(local_user["id"])
        if (
            existing_token
            and existing_token.get("refresh_token")
            and not token.get("refresh_token")
        ):
            token["refresh_token"] = existing_token["refresh_token"]

        # Store token in DB (server-side, for Drive API access)
        sqlite_store.save_user_oauth_token(user_id=local_user["id"], token=token)

        # Redirect to Drive page (not login - OAuth is for Drive, not auth)
        return redirect("/drive?connected=1")

    @api_oauth.get("/api/oauth/status")
    def oauth_status():
        """Check if OAuth is configured."""
        settings = sqlite_store.get_settings()
        secret_path = settings.get("oauth_client_secret_path")
        configured = bool(secret_path and Path(secret_path).exists())
        if not configured:
            from modules.google_user_oauth import (
                discover_google_oauth_client_secret_file,
            )

            root = Path(app.config["REPO_ROOT"])
            configured = discover_google_oauth_client_secret_file([root]) is not None
        return jsonify(
            configured=configured, redirect_base=settings.get("redirect_base_url")
        )

    @api_oauth.post("/api/oauth/upload-secret")
    def oauth_upload_secret():
        """Upload client_secret.json."""
        if "user" not in session:
            return jsonify(error="Not authenticated"), 401

        file = request.files.get("file")
        redirect_base = request.form.get("redirect_base_url", "").strip().rstrip("/")

        if file and file.filename:
            state_dir = Path(app.config["APP_DB_PATH"]).parent
            state_dir.mkdir(parents=True, exist_ok=True)
            dest = state_dir / "client_secret.json"
            file.save(str(dest))

            settings = sqlite_store.get_settings()
            sqlite_store.save_settings(
                initialized=True,
                oauth_client_secret_path=str(dest),
                redirect_base_url=redirect_base or settings.get("redirect_base_url"),
            )
            return jsonify(ok=True, path=str(dest))

        return jsonify(error="No file provided"), 400

    @api_oauth.post("/api/oauth/disconnect")
    def oauth_disconnect():
        """Remove OAuth configuration."""
        if "user" not in session:
            return jsonify(error="Not authenticated"), 401
        sqlite_store.save_settings(
            initialized=True,
            oauth_client_secret_path=None,
            redirect_base_url=None,
        )
        return jsonify(ok=True)

    app.register_blueprint(api_oauth)
