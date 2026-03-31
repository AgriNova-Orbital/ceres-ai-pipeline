def test_run_script_task_executes_subprocess() -> None:
    from modules.jobs.tasks import run_script

    result = run_script(["echo", "hello"], cwd=".")
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]
    assert result["cmd"] == ["echo", "hello"]
    assert result["cwd"] == "."


def test_task_drive_download_returns_ingest_summary(monkeypatch, tmp_path) -> None:
    from modules.jobs.tasks import task_drive_download

    class FakeFile:
        def __init__(self, file_id: str, name: str, size: int = 10):
            self.id = file_id
            self.name = name
            self.size = size

    monkeypatch.setattr("modules.jobs.tasks.get_drive_service", lambda **_: object())
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

    result = task_drive_download({"folder_id": "folder", "save_dir": str(tmp_path)})

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

    monkeypatch.setattr(
        "modules.jobs.tasks.get_drive_service", lambda **_: FakeService()
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

    result = task_drive_download({"file_ids": ["file-1"], "save_dir": str(tmp_path)})

    assert result["downloaded"] == 1
    assert result["single_tile_weeks_normalized"] == ["2021W02"]


def test_task_drive_download_uses_raw_oauth_token_without_authorized_user_file(
    monkeypatch, tmp_path
) -> None:
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

    monkeypatch.setattr(
        "modules.jobs.tasks.get_drive_service",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("should not use token_json auth path")
        ),
    )
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
            "oauth_token": {
                "access_token": "abc",
                "scope": "openid https://www.googleapis.com/auth/drive",
            },
        }
    )

    assert result["downloaded"] == 1
    assert result["single_tile_weeks_normalized"] == ["2021W03"]


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

    monkeypatch.setattr("modules.jobs.tasks.get_drive_service", lambda **_: object())
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

    task_drive_download({"folder_id": "folder", "save_dir": str(tmp_path)})

    manifest_call = next(call for call in meta_calls if "download_items" in call)
    items = manifest_call["download_items"]
    assert len(items) == 3
    assert items[0]["week"] == "2021W01"
    assert items[2]["week"] == "2021W02"
    summary_call = next(call for call in meta_calls if "merge_summary" in call)
    assert summary_call["merge_summary"]["total_weeks"] == 2



def test_task_drive_download_overwrites_existing_file_and_reports_counts(monkeypatch, tmp_path) -> None:
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
            "oauth_token": {"access_token": "abc", "refresh_token": "ref", "scope": "https://www.googleapis.com/auth/drive.readonly"},
        }
    )

    assert len(download_calls) == 1
    assert target.read_text(encoding="utf-8") == "new"
    assert result["requested"] == 1
    assert result["downloaded"] == 1
    assert result["overwritten"] == 1
    assert result["skipped_existing"] == 0
    assert result["total_size"] == 10
