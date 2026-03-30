def test_run_script_task_executes_subprocess() -> None:
    from modules.jobs.tasks import run_script

    result = run_script(["echo", "hello"], cwd=".")
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


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

    monkeypatch.setattr("modules.jobs.tasks.get_drive_service", lambda **_: FakeService())
    monkeypatch.setattr("modules.jobs.tasks.download_file", lambda *args, **kwargs: None)
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
