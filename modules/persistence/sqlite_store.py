from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class SQLiteStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    initialized INTEGER NOT NULL DEFAULT 0,
                    admin_username TEXT NOT NULL DEFAULT 'admin',
                    admin_password_hash TEXT NOT NULL DEFAULT '',
                    oauth_client_secret_path TEXT,
                    redirect_base_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # WIP: OAuth tables - kept for future use
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    display_name TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_oauth_tokens (
                    user_id TEXT PRIMARY KEY,
                    token_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            cur = conn.execute("SELECT id FROM app_settings WHERE id = 1")
            row = cur.fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO app_settings (
                        id, initialized, admin_username, admin_password_hash,
                        oauth_client_secret_path, redirect_base_url,
                        created_at, updated_at
                    ) VALUES (1, 1, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (
                        DEFAULT_ADMIN_USERNAME,
                        _hash_password(DEFAULT_ADMIN_PASSWORD),
                        now,
                        now,
                    ),
                )

    # ── Auth ─────────────────────────────────────────────

    def verify_admin(self, username: str, password: str) -> bool:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT admin_username, admin_password_hash FROM app_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            return False
        return row["admin_username"] == username and row[
            "admin_password_hash"
        ] == _hash_password(password)

    def change_admin_password(self, new_password: str) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE app_settings
                SET admin_password_hash = ?, updated_at = ?
                WHERE id = 1
                """,
                (_hash_password(new_password), _now_iso()),
            )

    def is_default_password(self) -> bool:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT admin_password_hash FROM app_settings WHERE id = 1"
            ).fetchone()
        return row is not None and row["admin_password_hash"] == _hash_password(
            DEFAULT_ADMIN_PASSWORD
        )

    # ── Settings (WIP: OAuth) ────────────────────────────

    def get_settings(self) -> dict[str, Any]:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT initialized, admin_username, oauth_client_secret_path, redirect_base_url "
                "FROM app_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("app_settings row missing after bootstrap")
        return {
            "initialized": bool(row["initialized"]),
            "admin_username": row["admin_username"],
            "oauth_client_secret_path": row["oauth_client_secret_path"],
            "redirect_base_url": row["redirect_base_url"],
        }

    def save_settings(
        self,
        *,
        initialized: bool,
        oauth_client_secret_path: str | None = None,
        redirect_base_url: str | None = None,
    ) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE app_settings
                SET initialized = ?,
                    oauth_client_secret_path = ?,
                    redirect_base_url = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    1 if initialized else 0,
                    oauth_client_secret_path,
                    redirect_base_url,
                    _now_iso(),
                ),
            )

    # ── WIP: OAuth user management ───────────────────────

    def get_user_by_google_sub(self, google_sub: str) -> dict[str, Any] | None:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, google_sub, email, display_name, created_at, last_login_at "
                "FROM users WHERE google_sub = ?",
                (google_sub,),
            ).fetchone()
        return dict(row) if row else None

    def get_or_create_user(
        self,
        *,
        google_sub: str,
        email: str,
        display_name: str | None,
    ) -> dict[str, Any]:
        existing = self.get_user_by_google_sub(google_sub)
        now = _now_iso()
        if existing is not None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET email=?, display_name=?, last_login_at=? WHERE google_sub=?",
                    (email, display_name, now, google_sub),
                )
            updated = self.get_user_by_google_sub(google_sub)
            if updated is None:
                raise RuntimeError("user disappeared after update")
            return updated
        user_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (id, google_sub, email, display_name, created_at, last_login_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, google_sub, email, display_name, now, now),
            )
        created = self.get_user_by_google_sub(google_sub)
        if created is None:
            raise RuntimeError("user missing after insert")
        return created

    def save_user_oauth_token(self, *, user_id: str, token: dict[str, Any]) -> None:
        payload = json.dumps(token, sort_keys=True)
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT user_id FROM user_oauth_tokens WHERE user_id = ?", (user_id,)
            )
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO user_oauth_tokens (user_id, token_json, created_at, updated_at) VALUES (?,?,?,?)",
                    (user_id, payload, now, now),
                )
            else:
                conn.execute(
                    "UPDATE user_oauth_tokens SET token_json=?, updated_at=? WHERE user_id=?",
                    (payload, now, user_id),
                )

    def get_user_oauth_token(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token_json FROM user_oauth_tokens WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return json.loads(row["token_json"]) if row and row["token_json"] else None

    def delete_user_oauth_token(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_oauth_tokens WHERE user_id = ?", (user_id,))
