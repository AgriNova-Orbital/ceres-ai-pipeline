from pathlib import Path


def test_sqlite_store_get_or_create_user(tmp_path: Path):
    from modules.persistence.sqlite_store import SQLiteStore

    store = SQLiteStore(tmp_path / "app.db")
    store.ensure_schema()
    user = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )
    assert user["google_sub"] == "sub-123"
    assert user["email"] == "user@example.com"
    assert user["display_name"] == "Demo User"
    assert "id" in user

    user2 = store.get_or_create_user(
        google_sub="sub-123",
        email="user@example.com",
        display_name="Demo User",
    )
    assert user["id"] == user2["id"]


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
    assert store.get_user_oauth_token(user["id"]) == token
