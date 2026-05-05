from __future__ import annotations

import sqlite3
from pathlib import Path


def test_sqlite_store_bootstraps_schema(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()

    settings = store.get_settings()
    assert settings["initialized"] is True
    assert settings["oauth_client_secret_path"] is None
    assert settings["redirect_base_url"] is None


def test_sqlite_store_persists_settings(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    store.save_settings(
        initialized=True,
        oauth_client_secret_path="/app/state/client_secret.json",
        redirect_base_url="http://127.0.0.1:5055",
    )

    settings = store.get_settings()
    assert settings["initialized"] is True
    assert settings["oauth_client_secret_path"] == "/app/state/client_secret.json"
    assert settings["redirect_base_url"] == "http://127.0.0.1:5055"


def test_sqlite_store_creates_user_with_uuid(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )

    assert user["id"]
    assert len(user["id"]) == 36
    assert user["google_sub"] == "sub-123"
    assert user["email"] == "user@example.com"


def test_sqlite_store_reuses_same_user_for_same_google_sub(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user1 = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )
    user2 = store.get_or_create_user(
        google_sub="sub-123",
        email="user2@example.com",
        display_name="Updated Name",
    )

    assert user1["id"] == user2["id"]
    assert user2["email"] == "user2@example.com"
    assert user2["display_name"] == "Updated Name"


def test_create_app_bootstraps_sqlite_store_from_app_db_path(
    monkeypatch, tmp_path: Path
):
    db_path = tmp_path / "state" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)

    assert app.config["APP_DB_PATH"] == db_path
    assert app.config["SQLITE_STORE"].get_settings()["initialized"] is True
    assert db_path.exists()


def test_sqlite_store_persists_user_oauth_token(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )

    token = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "scope": "openid email profile",
    }

    store.save_user_oauth_token(user_id=user["id"], token=token)
    retrieved = store.get_user_oauth_token(user["id"])
    assert retrieved == token

    # Test update
    token2 = token.copy()
    token2["access_token"] = "access-789"
    store.save_user_oauth_token(user_id=user["id"], token=token2)
    retrieved2 = store.get_user_oauth_token(user["id"])
    assert retrieved2 == token2

    store.delete_user_oauth_token(user_id=user["id"])
    assert store.get_user_oauth_token(user["id"]) is None


def test_sqlite_store_maps_clerk_user_to_google_oauth_token(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="google-sub-123",
        email="user@example.com",
        display_name="Demo User",
        clerk_user_id="user_clerk_123",
    )
    token = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "scope": "openid email profile",
    }

    store.save_user_oauth_token(user_id=user["id"], token=token)

    assert store.get_user_by_clerk_user_id("user_clerk_123")["id"] == user["id"]
    assert store.get_user_oauth_token_for_principal("user_clerk_123") == token


def test_sqlite_store_rejects_oauth_token_for_missing_user(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()

    try:
        store.save_user_oauth_token(
            user_id="missing-user",
            token={"access_token": "orphan-token"},
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("expected SQLite foreign key check to reject orphan token")


def test_sqlite_store_deleting_user_cascades_oauth_token(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="google-sub-123",
        email="user@example.com",
        display_name="Demo User",
    )
    store.save_user_oauth_token(
        user_id=user["id"],
        token={"access_token": "access-123"},
    )

    with store._connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))

    assert store.get_user_oauth_token(user["id"]) is None


def test_sqlite_store_migration_preserves_orphan_oauth_tokens_in_backup(
    tmp_path: Path,
):
    from modules.persistence.sqlite_store import SQLiteStore

    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
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
            CREATE TABLE user_oauth_tokens (
                user_id TEXT PRIMARY KEY,
                token_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                id, google_sub, email, display_name, created_at, last_login_at
            ) VALUES (
                'valid-user', 'google-sub-valid', 'valid@example.com',
                'Valid User', '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO user_oauth_tokens (
                user_id, token_json, created_at, updated_at
            ) VALUES
                ('valid-user', '{"access_token":"valid-token"}', '2026-01-01', '2026-01-01'),
                ('orphan-user', '{"access_token":"orphan-token"}', '2026-01-01', '2026-01-01')
            """
        )

    store = SQLiteStore(db_path)
    store.ensure_schema()

    assert store.get_user_oauth_token("valid-user") == {"access_token": "valid-token"}
    with store._connect() as conn:
        backup = conn.execute(
            "SELECT user_id, token_json FROM user_oauth_tokens_orphaned"
        ).fetchall()

    assert [dict(row) for row in backup] == [
        {"user_id": "orphan-user", "token_json": '{"access_token":"orphan-token"}'}
    ]
