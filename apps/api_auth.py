"""Auth API Blueprint - JSON endpoints for Next.js frontend."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

api_auth = Blueprint("api_auth", __name__)


def register_auth_api(app, sqlite_store) -> None:
    @api_auth.post("/api/auth/login")
    def api_login():
        data = request.get_json(silent=True) or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        if not username or not password:
            return jsonify(error="Username and password required"), 400
        if sqlite_store.verify_admin(username, password):
            session["user"] = {"username": username}
            return jsonify(
                user={"username": username},
                requiresPasswordChange=sqlite_store.is_default_password(),
            )
        return jsonify(error="Invalid username or password"), 401

    @api_auth.post("/api/auth/logout")
    def api_logout():
        session.clear()
        return jsonify(ok=True)

    @api_auth.post("/api/auth/change-password")
    def api_change_password():
        if "user" not in session:
            return jsonify(error="Not authenticated"), 401
        data = request.get_json(silent=True) or {}
        new_pw = data.get("new_password", "")
        confirm = data.get("confirm_password", "")
        if not new_pw or len(new_pw) < 4:
            return jsonify(error="Password must be at least 4 characters"), 400
        if new_pw != confirm:
            return jsonify(error="Passwords do not match"), 400
        sqlite_store.change_admin_password(new_pw)
        return jsonify(ok=True)

    @api_auth.get("/api/auth/me")
    def api_me():
        if "user" not in session:
            return jsonify(error="Not authenticated"), 401
        return jsonify(
            user=session["user"],
            requiresPasswordChange=sqlite_store.is_default_password(),
        )

    app.register_blueprint(api_auth)
