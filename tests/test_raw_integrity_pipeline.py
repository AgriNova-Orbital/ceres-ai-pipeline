from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import modules.wheat_risk.raw_integrity as raw_integrity
from modules.wheat_risk.raw_integrity import (
    RawScanRecord,
    build_curated_manifest,
    build_repair_candidates,
    choose_batch,
    parse_raw_tile_name,
    plan_kaggle_shards,
    scan_raw_batch,
    scan_one_raw_file,
    status_counts,
    write_dict_csv,
    write_scan_csv,
    write_summary_json,
)


class FakeDataset:
    width = 9984
    height = 9984
    count = 11
    dtypes = ("float32",) * 11
    crs = "EPSG:4326"
    nodata = -32768.0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, indexes, window=None):
        return [[1.0]]


class SampleReadFailDataset(FakeDataset):
    def read(self, indexes, window=None):
        raise RuntimeError("sample window unavailable")


class InvalidMetadataDataset(FakeDataset):
    count = 10


def test_parse_raw_tile_name_extracts_week_offsets_and_tile_key() -> None:
    parsed = parse_raw_tile_name(Path("fr_wheat_feat_2025W36-0000009984-0000039936.tif"))

    assert parsed is not None
    assert parsed.week_key == "2025W36"
    assert parsed.year == 2025
    assert parsed.week == 36
    assert parsed.row_offset == 9984
    assert parsed.col_offset == 39936
    assert parsed.tile_key == "2025W36-r0000009984-c0000039936"


def test_status_counts_groups_scan_records_by_status() -> None:
    records = [
        RawScanRecord(relative_path="a.tif", status="ok"),
        RawScanRecord(relative_path="b.tif", status="open_failed"),
        RawScanRecord(relative_path="c.tif", status="ok"),
    ]

    assert status_counts(records) == {"ok": 2, "open_failed": 1}


def test_choose_batch_skips_already_scanned_relative_paths(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    files = [
        raw_root / "fr_wheat_feat_2025W36-0000000000-0000000000.tif",
        raw_root / "fr_wheat_feat_2025W37-0000000000-0000000000.tif",
    ]
    for path in files:
        path.write_text("x", encoding="utf-8")

    selected = choose_batch(files, raw_root=raw_root, completed_relative_paths={files[0].name}, batch_size=10)

    assert [item.name for item in selected] == [files[1].name]


def test_scan_raw_batch_records_metadata_and_open_failures(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    ok_file = raw_root / "fr_wheat_feat_2025W36-0000000000-0000000000.tif"
    bad_file = raw_root / "fr_wheat_feat_2025W36-0000009984-0000039936.tif"
    ok_file.write_text("ok", encoding="utf-8")
    bad_file.write_text("bad", encoding="utf-8")

    def opener(path: Path):
        if path == bad_file:
            raise RuntimeError("not recognized as supported file format")
        return FakeDataset()

    records = scan_raw_batch([ok_file, bad_file], raw_root=raw_root, opener=opener, read_sample=True)

    assert records[0].status == "ok"
    assert records[0].width == 9984
    assert records[0].band_count == 11
    assert records[0].read_sample_status == "ok"
    assert records[1].status == "open_failed"
    assert "not recognized" in records[1].error


def test_scan_raw_batch_marks_sample_read_failures_separately(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    path = raw_root / "fr_wheat_feat_2025W36-0000000000-0000000000.tif"
    path.write_text("ok", encoding="utf-8")

    records = scan_raw_batch([path], raw_root=raw_root, opener=lambda _path: SampleReadFailDataset(), read_sample=True)

    assert records[0].status == "read_sample_failed"
    assert records[0].width == 9984
    assert records[0].band_count == 11
    assert "sample window unavailable" in records[0].error


def test_scan_one_raw_file_marks_invalid_raw_metadata_as_mismatch(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    path = raw_root / "not_a_raw_tile.tif"
    path.write_text("ok", encoding="utf-8")

    record = scan_one_raw_file(path, raw_root=raw_root, opener=lambda _path: InvalidMetadataDataset())

    assert record.status == "metadata_mismatch"
    assert record.band_count == 10
    assert "filename" in record.error
    assert "band_count" in record.error


def test_write_scan_csv_writes_buffered_rows_once(tmp_path: Path) -> None:
    csv_path = tmp_path / "batch_000001.csv"
    records = [
        RawScanRecord(relative_path="a.tif", status="ok"),
        RawScanRecord(relative_path="b.tif", status="open_failed", error="broken"),
    ]

    write_scan_csv(csv_path, records)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["relative_path"] for row in rows] == ["a.tif", "b.tif"]


def test_load_scan_records_combines_existing_batch_csvs(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batches"
    write_scan_csv(batch_dir / "batch_000001.csv", [RawScanRecord(relative_path="a.tif", status="open_failed")])
    write_scan_csv(batch_dir / "batch_000002.csv", [RawScanRecord(relative_path="b.tif", status="ok")])

    records = raw_integrity.load_scan_records(batch_dir)

    assert [(record.relative_path, record.status) for record in records] == [("a.tif", "open_failed"), ("b.tif", "ok")]


def test_next_batch_path_uses_highest_existing_suffix(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batches"
    write_scan_csv(batch_dir / "batch_000001.csv", [RawScanRecord(relative_path="a.tif", status="ok")])
    write_scan_csv(batch_dir / "batch_000003.csv", [RawScanRecord(relative_path="c.tif", status="ok")])

    assert raw_integrity.next_batch_path(batch_dir) == batch_dir / "batch_000004.csv"


def test_build_repair_candidates_includes_known_corrupt_tile() -> None:
    records = [
        RawScanRecord(
            relative_path="fr_wheat_feat_2025W36-0000009984-0000039936.tif",
            status="open_failed",
            week_key="2025W36",
            tile_key="2025W36-r0000009984-c0000039936",
        )
    ]

    candidates = build_repair_candidates(records, week_failure_threshold=3)

    assert candidates == [
        {
            "repair_scope": "tile",
            "week_key": "2025W36",
            "relative_path": "fr_wheat_feat_2025W36-0000009984-0000039936.tif",
            "tile_key": "2025W36-r0000009984-c0000039936",
            "reason": "open_failed",
        }
    ]


def test_build_repair_candidates_escalates_many_failures_to_week() -> None:
    records = [
        RawScanRecord(relative_path=f"bad_{i}.tif", status="open_failed", week_key="2025W40", tile_key=f"tile-{i}")
        for i in range(3)
    ]

    candidates = build_repair_candidates(records, week_failure_threshold=3)

    assert candidates == [
        {
            "repair_scope": "week",
            "week_key": "2025W40",
            "relative_path": "",
            "tile_key": "",
            "reason": "3_failed_files",
        }
    ]


def test_build_curated_manifest_uses_verified_repair_replacement() -> None:
    original = [
        RawScanRecord(relative_path="good.tif", status="ok", size_bytes=10, week_key="2025W36"),
        RawScanRecord(relative_path="bad.tif", status="open_failed", size_bytes=10, week_key="2025W36"),
    ]
    repair_records = [
        RawScanRecord(relative_path="repairs/2025W36/bad.tif", status="ok", size_bytes=12, week_key="2025W36")
    ]
    replacements = {"bad.tif": "repairs/2025W36/bad.tif"}

    curated = build_curated_manifest(original, repair_records=repair_records, replacements=replacements)

    assert curated == [
        {"original_relative_path": "bad.tif", "source_relative_path": "repairs/2025W36/bad.tif", "source_status": "repaired", "size_bytes": "12", "week_key": "2025W36"},
        {"original_relative_path": "good.tif", "source_relative_path": "good.tif", "source_status": "original", "size_bytes": "10", "week_key": "2025W36"},
    ]


def test_build_curated_manifest_fails_on_unresolved_bad_file() -> None:
    original = [RawScanRecord(relative_path="bad.tif", status="open_failed", week_key="2025W36")]

    try:
        build_curated_manifest(original, repair_records=[], replacements={})
    except ValueError as exc:
        assert "Unresolved bad raw files" in str(exc)
    else:
        raise AssertionError("Expected unresolved bad file failure")


def test_plan_kaggle_shards_splits_by_size_limit() -> None:
    curated = [
        {"original_relative_path": "a.tif", "source_relative_path": "a.tif", "source_status": "original", "size_bytes": "80", "week_key": "2025W36"},
        {"original_relative_path": "b.tif", "source_relative_path": "b.tif", "source_status": "original", "size_bytes": "80", "week_key": "2025W36"},
        {"original_relative_path": "c.tif", "source_relative_path": "c.tif", "source_status": "original", "size_bytes": "20", "week_key": "2025W37"},
    ]

    shards = plan_kaggle_shards(curated, max_shard_bytes=100, slug_prefix="ceres-raw")

    assert [shard["dataset_slug"] for shard in shards] == ["ceres-raw-part-001", "ceres-raw-part-002"]
    assert shards[0]["file_count"] == "1"
    assert shards[1]["file_count"] == "2"


def test_plan_kaggle_shards_rejects_unresolved_source_status() -> None:
    curated = [
        {"original_relative_path": "bad.tif", "source_relative_path": "bad.tif", "source_status": "open_failed", "size_bytes": "1", "week_key": "2025W36"}
    ]

    try:
        plan_kaggle_shards(curated, max_shard_bytes=100, slug_prefix="ceres-raw")
    except ValueError as exc:
        assert "source_status" in str(exc)
    else:
        raise AssertionError("Expected invalid source_status failure")


def test_plan_kaggle_shards_rejects_single_file_over_limit() -> None:
    curated = [
        {"original_relative_path": "huge.tif", "source_relative_path": "huge.tif", "source_status": "original", "size_bytes": "101", "week_key": "2025W36"}
    ]

    try:
        plan_kaggle_shards(curated, max_shard_bytes=100, slug_prefix="ceres-raw")
    except ValueError as exc:
        assert "exceeds shard limit" in str(exc)
    else:
        raise AssertionError("Expected oversized file failure")


def test_write_dict_csv_writes_requested_columns(tmp_path: Path) -> None:
    output = tmp_path / "repair_candidates.csv"
    rows = [{"repair_scope": "tile", "week_key": "2025W36", "relative_path": "bad.tif", "tile_key": "tile", "reason": "open_failed"}]

    write_dict_csv(output, rows, columns=("repair_scope", "week_key", "relative_path", "tile_key", "reason"))

    assert output.read_text(encoding="utf-8").splitlines()[0] == "repair_scope,week_key,relative_path,tile_key,reason"


def test_write_summary_json_counts_statuses(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"
    records = [RawScanRecord(relative_path="a.tif", status="ok"), RawScanRecord(relative_path="b.tif", status="open_failed")]

    write_summary_json(output, records)

    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["total_files"] == 2
    assert summary["status_counts"] == {"ok": 1, "open_failed": 1}


def test_scan_raw_integrity_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/scan_raw_integrity_batches.py", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--raw-root" in result.stdout
    assert "--report-root" in result.stdout
    assert "--batch-size" in result.stdout


def test_plan_kaggle_raw_shards_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/plan_kaggle_raw_shards.py", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--curated-manifest" in result.stdout
    assert "--max-shard-gb" in result.stdout
    assert "--slug-prefix" in result.stdout
