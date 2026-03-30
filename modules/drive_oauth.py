from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


@dataclass(frozen=True, slots=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None
    modified_time: str | None


def _import_google() -> Any:
    try:
        import googleapiclient.discovery  # type: ignore
        import googleapiclient.http  # type: ignore
        import google_auth_oauthlib.flow  # type: ignore

        return googleapiclient, google_auth_oauthlib
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Google Drive API client is required. Install extras: "
            "`uv sync --extra drive` (or `uv pip install google-api-python-client google-auth-oauthlib`)"
        ) from e


def _import_google_auth() -> Any:
    try:
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore

        return Request, Credentials
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "google-auth is required. Install extras: `uv sync --extra drive`"
        ) from e


def get_drive_service(
    *,
    credentials_json: Path,
    token_json: Path,
) -> Any:
    """Create an authenticated Google Drive v3 service using OAuth.

    credentials_json: OAuth client secrets JSON (downloaded from Google Cloud console)
    token_json: cached user token (will be created/updated)
    """

    googleapiclient, google_auth_oauthlib = _import_google()
    Request, Credentials = _import_google_auth()

    creds = None
    if token_json.exists():
        creds = Credentials.from_authorized_user_file(str(token_json), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                str(credentials_json), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_json.parent.mkdir(parents=True, exist_ok=True)
        token_json.write_text(creds.to_json(), encoding="utf-8")

    return googleapiclient.discovery.build("drive", "v3", credentials=creds)


def build_drive_service_from_oauth_token(oauth_token: dict[str, Any]) -> Any:
    """Build Drive service directly from an OAuth token dict.

    This avoids requiring the token to be stored in Google's
    `authorized_user_file` JSON format.
    """
    googleapiclient, _ = _import_google()
    from modules.google_user_oauth import build_google_credentials_from_oauth_token

    creds = build_google_credentials_from_oauth_token(oauth_token, scopes=SCOPES)
    return googleapiclient.discovery.build("drive", "v3", credentials=creds)


def list_folder_files(
    service: Any, *, folder_id: str, page_size: int = 1000
) -> list[DriveFile]:
    q = f"'{folder_id}' in parents and trashed = false"
    fields = "nextPageToken, files(id, name, mimeType, size, modifiedTime)"

    out: list[DriveFile] = []
    token = None
    while True:
        resp = (
            service.files()
            .list(
                q=q,
                fields=fields,
                pageSize=page_size,
                pageToken=token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        for f in resp.get("files", []):
            out.append(
                DriveFile(
                    id=str(f.get("id", "")),
                    name=str(f.get("name", "")),
                    mime_type=str(f.get("mimeType", "")),
                    size=int(f["size"]) if "size" in f else None,
                    modified_time=str(f.get("modifiedTime"))
                    if f.get("modifiedTime")
                    else None,
                )
            )
        token = resp.get("nextPageToken")
        if not token:
            break
    return out


def download_file(
    service: Any,
    *,
    file_id: str,
    dst_path: Path,
    chunk_size: int = 1024 * 1024,
    progress_callback: Any | None = None,
) -> int:
    googleapiclient, _ = _import_google()

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    bytes_written = 0
    with dst_path.open("wb") as f:
        downloader = googleapiclient.http.MediaIoBaseDownload(
            f, request, chunksize=chunk_size
        )
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status is not None and progress_callback is not None:
                n = int(status.total_size * status.progress()) - bytes_written
                if n > 0:
                    bytes_written += n
                    progress_callback(n)
    return bytes_written


def ensure_files_downloaded(
    service: Any,
    *,
    files: Iterable[DriveFile],
    out_dir: Path,
    skip_existing: bool = True,
    progress: Any | None = None,
) -> list[Path]:
    out: list[Path] = []
    for f in files:
        p = out_dir / f.name
        if progress is not None:
            progress.on_file_start(f.name, f.size or 0)
        if skip_existing and p.exists():
            if progress is not None:
                progress.on_chunk(f.size or 0)
                progress.on_file_done(f.name, f.size or 0)
            out.append(p)
            continue
        download_file(
            service,
            file_id=f.id,
            dst_path=p,
            progress_callback=progress.on_chunk if progress is not None else None,
        )
        if progress is not None:
            progress.on_file_done(f.name, f.size or 0)
        out.append(p)
    return out
