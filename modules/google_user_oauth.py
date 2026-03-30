from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/drive",
]


def _load_client_config_from_file(path: Path) -> tuple[str, str, str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    web = data.get("web") or {}
    client_id = str(web.get("client_id") or "")
    client_secret = str(web.get("client_secret") or "")
    project_id = web.get("project_id")
    if not client_id or not client_secret:
        raise ValueError("OAuth client config file is missing client_id/client_secret")
    return client_id, client_secret, str(project_id) if project_id else None


def discover_google_oauth_client_secret_file(
    search_roots: Sequence[Path] | None = None,
) -> Path | None:
    if search_roots is not None:
        roots = list(search_roots)
    else:
        roots = [Path.cwd()]
        app_db_path = os.environ.get("APP_DB_PATH")
        if app_db_path:
            roots.append(Path(app_db_path).resolve().parent)
        roots.append(Path.cwd() / "state")
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if root in seen or not root.exists() or not root.is_dir():
            continue
        seen.add(root)
        matches = sorted(root.glob("client_secret_*.json"))
        if matches:
            return matches[0]
        plain = root / "client_secret.json"
        if plain.exists():
            return plain
    return None


def get_google_oauth_redirect_uri() -> str | None:
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    if redirect_uri:
        return redirect_uri

    secret_file = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    if not secret_file:
        discovered = discover_google_oauth_client_secret_file()
        if discovered is not None:
            secret_file = str(discovered)
    if secret_file:
        data = json.loads(Path(secret_file).read_text(encoding="utf-8"))
        web = data.get("web") or {}
        redirect_uris = web.get("redirect_uris") or []
        if redirect_uris:
            return str(redirect_uris[0])
    return None


def get_google_web_client_config() -> tuple[str, str, str | None]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    project_id = os.environ.get("GOOGLE_PROJECT_ID")
    if client_id and client_secret:
        return client_id, client_secret, project_id

    secret_file = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    if not secret_file:
        discovered = discover_google_oauth_client_secret_file()
        if discovered is not None:
            secret_file = str(discovered)
    if secret_file:
        return _load_client_config_from_file(Path(secret_file))

    raise ValueError(
        "Missing Google OAuth client config. Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET "
        "or GOOGLE_OAUTH_CLIENT_SECRET_FILE."
    )


def build_google_credentials_from_oauth_token(
    oauth_token: Mapping[str, Any],
    *,
    scopes: Sequence[str] | None = None,
):
    from google.oauth2.credentials import Credentials  # type: ignore

    access_token = oauth_token.get("access_token")
    if not access_token:
        raise ValueError("oauth_token is missing access_token")

    client_id, client_secret, _ = get_google_web_client_config()

    scope_value = oauth_token.get("scope")
    resolved_scopes: Sequence[str]
    if scopes is not None:
        resolved_scopes = list(scopes)
    elif isinstance(scope_value, str) and scope_value.strip():
        resolved_scopes = scope_value.split()
    else:
        resolved_scopes = DEFAULT_SCOPES

    return Credentials(
        token=str(access_token),
        refresh_token=oauth_token.get("refresh_token"),
        token_uri=str(oauth_token.get("token_uri") or DEFAULT_TOKEN_URI),
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(resolved_scopes),
    )


def load_google_credentials_from_env(
    *,
    env_var: str = "GOOGLE_OAUTH_TOKEN_JSON",
    scopes: Sequence[str] | None = None,
):
    payload = os.environ.get(env_var)
    if not payload:
        return None
    token = json.loads(payload)
    if not isinstance(token, dict):
        raise ValueError(f"{env_var} must contain a JSON object")
    return build_google_credentials_from_oauth_token(token, scopes=scopes)
