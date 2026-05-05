def test_run_script_task_executes_subprocess() -> None:
    from modules.jobs.tasks import run_script

    result = run_script(["echo", "hello"], cwd=".")
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]
    assert result["cmd"] == ["echo", "hello"]
    assert result["cwd"] == "."


def _store_drive_token(monkeypatch, tmp_path, user_id: str = "user-test") -> str:
    from modules.persistence.sqlite_store import SQLiteStore

    db_path = tmp_path / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    store = SQLiteStore(db_path)
    store.ensure_schema()
    with store._connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (
                id, google_sub, email, display_name, created_at, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                f"google-sub-{user_id}",
                f"{user_id}@example.com",
                "Test User",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    store.save_user_oauth_token(
        user_id=user_id,
        token={"access_token": f"token-{user_id}", "scope": "drive"},
    )
    return user_id


def test_task_export_weekly_risk_rasters_runs_script_main_with_args(
    monkeypatch,
) -> None:
    from modules.jobs.tasks import task_export_weekly_risk_rasters

    captured: dict[str, object] = {}

    def fake_main(argv):
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr("scripts.export_weekly_risk_rasters.main", fake_main)

    result = task_export_weekly_risk_rasters(
        {
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": 4,
            "run": False,
            "drive_folder": None,
            "ee_project": "demo-proj",
            "user_id": None,
        }
    )

    assert result["returncode"] == 0
    argv = captured["argv"]
    assert "--stage" in argv
    assert "--dry-run" in argv


def test_task_export_weekly_risk_rasters_requires_drive_folder_when_run() -> None:
    from modules.jobs.tasks import task_export_weekly_risk_rasters

    result = task_export_weekly_risk_rasters(
        {
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": 4,
            "run": True,
            "drive_folder": None,
            "user_id": None,
        }
    )

    assert result["returncode"] == 2
    assert "drive_folder" in str(result["stderr"])


def test_task_export_weekly_risk_rasters_fails_closed_without_user_token(
    monkeypatch, tmp_path
) -> None:
    from modules.jobs.tasks import task_export_weekly_risk_rasters

    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(
        "scripts.export_weekly_risk_rasters.main",
        lambda argv: (_ for _ in ()).throw(
            AssertionError("should not run Google export without user OAuth token")
        ),
    )

    result = task_export_weekly_risk_rasters(
        {
            "stage": "1",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "limit": 4,
            "run": True,
            "drive_folder": "EarthEngine",
            "user_id": "missing-user",
        }
    )

    assert result["returncode"] == 2
    assert "OAuth token" in str(result["stderr"])


def test_task_drive_download_returns_ingest_summary(monkeypatch, tmp_path) -> None:
    from modules.jobs.tasks import task_drive_download

    class FakeFile:
        def __init__(self, file_id: str, name: str, size: int = 10):
            self.id = file_id
            self.name = name
            self.size = size

    user_id = _store_drive_token(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token", lambda token: object()
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.list_folder_files",
        lambda _svc, folder_id: [
            FakeFile("1", "fr_wheat_feat_2021W01-0000000000-0000000000.tif")
        ],
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.download_file", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.ingest_downloaded_geotiffs",
        lambda path: {
            "merged_weeks": [],
            "single_tile_weeks_normalized": ["2021W01"],
            "failed_weeks": [],
            "warnings": [],
            "unknown_files": [],
        },
    )

    result = task_drive_download(
        {"folder_id": "folder", "save_dir": str(tmp_path), "user_id": user_id}
    )

    assert result["single_tile_weeks_normalized"] == ["2021W01"]
    assert "downloaded" in result


def test_task_drive_download_supports_direct_file_ids(monkeypatch, tmp_path) -> None:
    from modules.jobs.tasks import task_drive_download

    class FakeFilesApi:
        def get(self, fileId, supportsAllDrives=True):
            class _Req:
                def execute(self_nonlocal):
                    return {
                        "id": fileId,
                        "name": "fr_wheat_feat_2021W02-0000000000-0000000000.tif",
                        "mimeType": "image/tiff",
                        "size": "10",
                    }

            return _Req()

    class FakeService:
        def files(self):
            return FakeFilesApi()

    user_id = _store_drive_token(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token",
        lambda token: FakeService(),
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.download_file", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.ingest_downloaded_geotiffs",
        lambda path: {
            "merged_weeks": [],
            "single_tile_weeks_normalized": ["2021W02"],
            "failed_weeks": [],
            "warnings": [],
            "unknown_files": [],
        },
    )

    result = task_drive_download(
        {"file_ids": ["file-1"], "save_dir": str(tmp_path), "user_id": user_id}
    )

    assert result["downloaded"] == 1
    assert result["single_tile_weeks_normalized"] == ["2021W02"]


def test_task_drive_download_uses_stored_token_for_clerk_user_id(
    monkeypatch, tmp_path
) -> None:
    from modules.persistence.sqlite_store import SQLiteStore
    from modules.jobs.tasks import task_drive_download

    class FakeFilesApi:
        def get(self, fileId, supportsAllDrives=True):
            class _Req:
                def execute(self_nonlocal):
                    return {
                        "id": fileId,
                        "name": "fr_wheat_feat_2021W03-0000000000-0000000000.tif",
                        "mimeType": "image/tiff",
                        "size": "10",
                    }

            return _Req()

    class FakeService:
        def files(self):
            return FakeFilesApi()

    db_path = tmp_path / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    store = SQLiteStore(db_path)
    target_user = store.get_or_create_user(
        google_sub="google-sub-target",
        email="target@example.com",
        display_name="Target User",
        clerk_user_id="user_clerk_target",
    )
    other_user = store.get_or_create_user(
        google_sub="google-sub-other",
        email="other@example.com",
        display_name="Other User",
        clerk_user_id="user_clerk_other",
    )
    store.save_user_oauth_token(
        user_id=target_user["id"],
        token={"access_token": "target-token", "scope": "drive"},
    )
    store.save_user_oauth_token(
        user_id=other_user["id"],
        token={"access_token": "other-token", "scope": "drive"},
    )

    seen_token: dict[str, object] = {}

    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token",
        lambda token: seen_token.update(token) or FakeService(),
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.download_file", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.ingest_downloaded_geotiffs",
        lambda path: {
            "merged_weeks": [],
            "single_tile_weeks_normalized": ["2021W03"],
            "failed_weeks": [],
            "warnings": [],
            "unknown_files": [],
        },
    )

    result = task_drive_download(
        {
            "file_ids": ["file-1"],
            "save_dir": str(tmp_path),
            "user_id": "user_clerk_target",
        }
    )

    assert result["downloaded"] == 1
    assert result["single_tile_weeks_normalized"] == ["2021W03"]
    assert seen_token["access_token"] == "target-token"


def test_task_drive_download_ignores_client_supplied_oauth_token(
    monkeypatch, tmp_path
) -> None:
    from modules.jobs.tasks import task_drive_download
    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token",
        lambda token: (_ for _ in ()).throw(
            AssertionError("should not trust client-supplied OAuth token")
        ),
    )

    result = task_drive_download(
        {
            "file_ids": ["file-1"],
            "save_dir": str(tmp_path),
            "oauth_token": {"access_token": "client-token"},
        }
    )

    assert result["downloaded"] == 0
    assert "OAuth token" in result["warnings"][0]


def test_task_drive_download_sets_download_manifest_in_job_meta(
    monkeypatch, tmp_path
) -> None:
    from modules.jobs.tasks import task_drive_download

    class FakeFile:
        def __init__(self, file_id: str, name: str, size: int = 10):
            self.id = file_id
            self.name = name
            self.size = size

    meta_calls: list[dict[str, object]] = []

    user_id = _store_drive_token(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token", lambda token: object()
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.list_folder_files",
        lambda _svc, folder_id: [
            FakeFile("1", "fr_wheat_feat_2021W01-0000000000-0000000000.tif", 11),
            FakeFile("2", "fr_wheat_feat_2021W01-0000009984-0000000000.tif", 22),
            FakeFile("3", "fr_wheat_feat_2021W02-0000000000-0000000000.tif", 33),
        ],
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.download_file", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "modules.jobs.tasks.ingest_downloaded_geotiffs",
        lambda path, progress_callback=None: {
            "merged_weeks": ["2021W01"],
            "single_tile_weeks_normalized": ["2021W02"],
            "failed_weeks": [],
            "warnings": [],
            "unknown_files": [],
        },
    )
    monkeypatch.setattr(
        "modules.jobs.tasks._set_job_meta", lambda **fields: meta_calls.append(fields)
    )

    task_drive_download(
        {"folder_id": "folder", "save_dir": str(tmp_path), "user_id": user_id}
    )

    manifest_call = next(call for call in meta_calls if "download_items" in call)
    items = manifest_call["download_items"]
    assert len(items) == 3
    assert items[0]["week"] == "2021W01"
    assert items[2]["week"] == "2021W02"
    summary_call = next(call for call in meta_calls if "merge_summary" in call)
    assert summary_call["merge_summary"]["total_weeks"] == 2


def test_task_drive_download_overwrites_existing_file_and_reports_counts(
    monkeypatch, tmp_path
) -> None:
    from modules.jobs.tasks import task_drive_download

    class FakeFilesApi:
        def get(self, fileId, supportsAllDrives=True):
            class _Req:
                def execute(self_nonlocal):
                    return {
                        "id": fileId,
                        "name": "fr_wheat_feat_2021W04-0000000000-0000000000.tif",
                        "mimeType": "image/tiff",
                        "size": "10",
                    }

            return _Req()

    class FakeService:
        def files(self):
            return FakeFilesApi()

    target = tmp_path / "fr_wheat_feat_2021W04-0000000000-0000000000.tif"
    target.write_text("old", encoding="utf-8")

    download_calls = []

    def fake_download_file(service, file_id, dst_path, progress_callback=None):
        download_calls.append((file_id, str(dst_path)))
        dst_path.write_text("new", encoding="utf-8")
        if progress_callback:
            progress_callback(10)
        return 10

    user_id = _store_drive_token(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "modules.jobs.tasks.build_drive_service_from_oauth_token",
        lambda token: FakeService(),
    )
    monkeypatch.setattr("modules.jobs.tasks.download_file", fake_download_file)
    monkeypatch.setattr(
        "modules.jobs.tasks.ingest_downloaded_geotiffs",
        lambda path, progress_callback=None: {
            "merged_weeks": [],
            "single_tile_weeks_normalized": ["2021W04"],
            "failed_weeks": [],
            "warnings": [],
            "unknown_files": [],
        },
    )

    result = task_drive_download(
        {
            "file_ids": ["file-1"],
            "save_dir": str(tmp_path),
            "user_id": user_id,
        }
    )

    assert len(download_calls) == 1
    assert target.read_text(encoding="utf-8") == "new"
    assert result["requested"] == 1
    assert result["downloaded"] == 1
    assert result["overwritten"] == 1
    assert result["skipped_existing"] == 0
    assert result["total_size"] == 10
