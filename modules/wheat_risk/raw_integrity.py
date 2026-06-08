from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
import re


RAW_TILE_RE = re.compile(
    r"^fr_wheat_feat_(?P<year>\d{4})W(?P<week>\d{2})"
    r"(?:-(?P<row>\d+)-(?P<col>\d+))?\.tif(?:f)?$",
    re.IGNORECASE,
)
BATCH_CSV_RE = re.compile(r"^batch_(?P<number>\d{6})\.csv$")


@dataclass(frozen=True, slots=True)
class RawTileName:
    relative_path: str
    filename: str
    week_key: str
    year: int
    week: int
    row_offset: int
    col_offset: int
    tile_key: str


@dataclass(frozen=True, slots=True)
class RawScanRecord:
    relative_path: str
    status: str
    size_bytes: int = 0
    modified_time: str = ""
    week_key: str = ""
    tile_key: str = ""
    width: int = 0
    height: int = 0
    band_count: int = 0
    dtypes: str = ""
    crs: str = ""
    nodata: str = ""
    read_sample_status: str = "not_checked"
    error: str = ""


RAW_SCAN_COLUMNS = tuple(field.name for field in fields(RawScanRecord))
BAD_STATUSES = {"open_failed", "metadata_mismatch", "read_sample_failed", "missing", "too_small"}
EXPECTED_WIDTH = 9984
EXPECTED_HEIGHT = 9984
EXPECTED_BAND_COUNT = 11
EXPECTED_DTYPE = "float32"
EXPECTED_CRS = "EPSG:4326"
EXPECTED_NODATA = -32768.0
CURATED_COLUMNS = (
    "original_relative_path",
    "source_relative_path",
    "source_status",
    "size_bytes",
    "week_key",
)


def parse_raw_tile_name(path: Path) -> RawTileName | None:
    match = RAW_TILE_RE.match(path.name)
    if not match:
        return None
    year = int(match.group("year"))
    week = int(match.group("week"))
    row_offset = int(match.group("row") or 0)
    col_offset = int(match.group("col") or 0)
    week_key = f"{year}W{week:02d}"
    tile_key = f"{week_key}-r{row_offset:010d}-c{col_offset:010d}"
    return RawTileName(
        relative_path=path.as_posix(),
        filename=path.name,
        week_key=week_key,
        year=year,
        week=week,
        row_offset=row_offset,
        col_offset=col_offset,
        tile_key=tile_key,
    )


def status_counts(records: list[RawScanRecord]) -> dict[str, int]:
    return dict(Counter(record.status for record in records))


def relative_to_root(path: Path, raw_root: Path) -> str:
    return path.relative_to(raw_root).as_posix()


def choose_batch(
    candidates: Iterable[Path],
    *,
    raw_root: Path,
    completed_relative_paths: set[str],
    batch_size: int,
) -> list[Path]:
    selected: list[Path] = []
    for path in sorted(candidates):
        rel = relative_to_root(path, raw_root)
        if rel in completed_relative_paths:
            continue
        selected.append(path)
        if len(selected) >= batch_size:
            break
    return selected


def truncate_error(exc: BaseException, limit: int = 500) -> str:
    return str(exc).replace("\n", " ")[:limit]


def file_modified_time(path: Path) -> str:
    timestamp = path.stat().st_mtime
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()


def metadata_mismatch_errors(parsed: RawTileName | None, dataset: object) -> list[str]:
    errors: list[str] = []
    if parsed is None:
        errors.append("filename does not match fr_wheat_feat_YYYYWww-row-col.tif")

    width = int(getattr(dataset, "width", 0))
    height = int(getattr(dataset, "height", 0))
    band_count = int(getattr(dataset, "count", 0))
    dtypes = tuple(str(dtype) for dtype in getattr(dataset, "dtypes", ()))
    crs = str(getattr(dataset, "crs", "") or "")
    nodata = getattr(dataset, "nodata", None)

    if width != EXPECTED_WIDTH:
        errors.append(f"width={width} expected {EXPECTED_WIDTH}")
    if height != EXPECTED_HEIGHT:
        errors.append(f"height={height} expected {EXPECTED_HEIGHT}")
    if band_count != EXPECTED_BAND_COUNT:
        errors.append(f"band_count={band_count} expected {EXPECTED_BAND_COUNT}")
    if len(dtypes) != EXPECTED_BAND_COUNT or any(dtype != EXPECTED_DTYPE for dtype in dtypes):
        errors.append(f"dtypes={';'.join(dtypes)} expected {EXPECTED_DTYPE}x{EXPECTED_BAND_COUNT}")
    if crs != EXPECTED_CRS:
        errors.append(f"crs={crs or 'missing'} expected {EXPECTED_CRS}")
    if nodata is None or float(nodata) != EXPECTED_NODATA:
        errors.append(f"nodata={nodata} expected {EXPECTED_NODATA}")
    return errors


def default_rasterio_opener(path: Path):
    import rasterio

    return rasterio.open(path)


def scan_one_raw_file(
    path: Path,
    *,
    raw_root: Path,
    opener: Callable[[Path], object] = default_rasterio_opener,
    read_sample: bool = False,
) -> RawScanRecord:
    rel = relative_to_root(path, raw_root)
    parsed = parse_raw_tile_name(Path(rel))
    if not path.exists():
        return RawScanRecord(relative_path=rel, status="missing")
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        return RawScanRecord(relative_path=rel, status="too_small", size_bytes=size_bytes)

    try:
        with opener(path) as dataset:
            width = int(dataset.width)
            height = int(dataset.height)
            band_count = int(dataset.count)
            dtypes = ";".join(str(dtype) for dtype in dataset.dtypes)
            crs = str(dataset.crs or "")
            nodata = "" if dataset.nodata is None else str(dataset.nodata)
            metadata_errors = metadata_mismatch_errors(parsed, dataset)
            if metadata_errors:
                return RawScanRecord(
                    relative_path=rel,
                    status="metadata_mismatch",
                    size_bytes=size_bytes,
                    modified_time=file_modified_time(path),
                    week_key=parsed.week_key if parsed else "",
                    tile_key=parsed.tile_key if parsed else "",
                    width=width,
                    height=height,
                    band_count=band_count,
                    dtypes=dtypes,
                    crs=crs,
                    nodata=nodata,
                    error="; ".join(metadata_errors),
                )

            read_sample_status = "not_checked"
            if read_sample:
                try:
                    dataset.read(1, window=((0, 1), (0, 1)))
                    read_sample_status = "ok"
                except Exception as exc:
                    return RawScanRecord(
                        relative_path=rel,
                        status="read_sample_failed",
                        size_bytes=size_bytes,
                        modified_time=file_modified_time(path),
                        week_key=parsed.week_key if parsed else "",
                        tile_key=parsed.tile_key if parsed else "",
                        width=width,
                        height=height,
                        band_count=band_count,
                        dtypes=dtypes,
                        crs=crs,
                        nodata=nodata,
                        read_sample_status="failed",
                        error=truncate_error(exc),
                    )
            return RawScanRecord(
                relative_path=rel,
                status="ok",
                size_bytes=size_bytes,
                modified_time=file_modified_time(path),
                week_key=parsed.week_key if parsed else "",
                tile_key=parsed.tile_key if parsed else "",
                width=width,
                height=height,
                band_count=band_count,
                dtypes=dtypes,
                crs=crs,
                nodata=nodata,
                read_sample_status=read_sample_status,
            )
    except Exception as exc:
        return RawScanRecord(
            relative_path=rel,
            status="open_failed",
            size_bytes=size_bytes,
            modified_time=file_modified_time(path),
            week_key=parsed.week_key if parsed else "",
            tile_key=parsed.tile_key if parsed else "",
            error=truncate_error(exc),
        )


def scan_raw_batch(
    paths: Iterable[Path],
    *,
    raw_root: Path,
    opener: Callable[[Path], object] = default_rasterio_opener,
    read_sample: bool = False,
) -> list[RawScanRecord]:
    return [scan_one_raw_file(path, raw_root=raw_root, opener=opener, read_sample=read_sample) for path in paths]


def write_scan_csv(path: Path, records: list[RawScanRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_SCAN_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({key: getattr(record, key) for key in RAW_SCAN_COLUMNS})


def scan_record_from_csv_row(row: dict[str, str]) -> RawScanRecord:
    values: dict[str, object] = {}
    for column in RAW_SCAN_COLUMNS:
        value = row.get(column, "")
        if column in {"size_bytes", "width", "height", "band_count"}:
            values[column] = int(value or 0)
        else:
            values[column] = value
    return RawScanRecord(**values)  # type: ignore[arg-type]


def load_scan_records(batch_dir: Path) -> list[RawScanRecord]:
    records: list[RawScanRecord] = []
    for csv_path in sorted(batch_dir.glob("batch_*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            records.extend(scan_record_from_csv_row(row) for row in csv.DictReader(handle))
    return records


def next_batch_path(batch_dir: Path) -> Path:
    highest = 0
    for csv_path in batch_dir.glob("batch_*.csv"):
        match = BATCH_CSV_RE.match(csv_path.name)
        if match:
            highest = max(highest, int(match.group("number")))
    return batch_dir / f"batch_{highest + 1:06d}.csv"


def build_repair_candidates(
    records: list[RawScanRecord],
    *,
    week_failure_threshold: int = 5,
) -> list[dict[str, str]]:
    failed_by_week: dict[str, list[RawScanRecord]] = {}
    for record in records:
        if record.status not in BAD_STATUSES:
            continue
        week_key = record.week_key or "unknown"
        failed_by_week.setdefault(week_key, []).append(record)

    candidates: list[dict[str, str]] = []
    for week_key in sorted(failed_by_week):
        failed = failed_by_week[week_key]
        if len(failed) >= week_failure_threshold:
            candidates.append(
                {
                    "repair_scope": "week",
                    "week_key": week_key,
                    "relative_path": "",
                    "tile_key": "",
                    "reason": f"{len(failed)}_failed_files",
                }
            )
            continue
        for record in sorted(failed, key=lambda item: item.relative_path):
            candidates.append(
                {
                    "repair_scope": "tile",
                    "week_key": week_key,
                    "relative_path": record.relative_path,
                    "tile_key": record.tile_key,
                    "reason": record.status,
                }
            )
    return candidates


def build_curated_manifest(
    original_records: list[RawScanRecord],
    *,
    repair_records: list[RawScanRecord],
    replacements: dict[str, str],
) -> list[dict[str, str]]:
    repair_by_path = {record.relative_path: record for record in repair_records if record.status == "ok"}
    curated: list[dict[str, str]] = []
    unresolved: list[str] = []

    for record in sorted(original_records, key=lambda item: item.relative_path):
        if record.status == "ok":
            curated.append(
                {
                    "original_relative_path": record.relative_path,
                    "source_relative_path": record.relative_path,
                    "source_status": "original",
                    "size_bytes": str(record.size_bytes),
                    "week_key": record.week_key,
                }
            )
            continue

        replacement_path = replacements.get(record.relative_path)
        replacement = repair_by_path.get(replacement_path or "")
        if replacement is None:
            unresolved.append(record.relative_path)
            continue
        curated.append(
            {
                "original_relative_path": record.relative_path,
                "source_relative_path": replacement.relative_path,
                "source_status": "repaired",
                "size_bytes": str(replacement.size_bytes),
                "week_key": replacement.week_key or record.week_key,
            }
        )

    if unresolved:
        raise ValueError(f"Unresolved bad raw files: {', '.join(unresolved[:10])}")
    return curated


def plan_kaggle_shards(
    curated_rows: list[dict[str, str]],
    *,
    max_shard_bytes: int,
    slug_prefix: str,
) -> list[dict[str, str]]:
    if max_shard_bytes <= 0:
        raise ValueError("max_shard_bytes must be positive")

    shards: list[dict[str, str]] = []
    current_rows: list[dict[str, str]] = []
    current_bytes = 0

    def flush() -> None:
        nonlocal current_rows, current_bytes
        if not current_rows:
            return
        part_number = len(shards) + 1
        weeks = sorted({row.get("week_key", "") for row in current_rows if row.get("week_key", "")})
        shards.append(
            {
                "dataset_slug": f"{slug_prefix}-part-{part_number:03d}",
                "part_number": str(part_number),
                "file_count": str(len(current_rows)),
                "total_bytes": str(current_bytes),
                "week_keys": ";".join(weeks),
            }
        )
        current_rows = []
        current_bytes = 0

    for row in curated_rows:
        if row.get("source_status") not in {"original", "repaired"}:
            raise ValueError(f"Invalid source_status for Kaggle shard: {row.get('source_status')}")
        size_bytes = int(row.get("size_bytes") or "0")
        if size_bytes > max_shard_bytes:
            raise ValueError(f"{row.get('source_relative_path')} exceeds shard limit")
        if current_rows and current_bytes + size_bytes > max_shard_bytes:
            flush()
        current_rows.append(row)
        current_bytes += size_bytes
    flush()
    return shards


def write_dict_csv(path: Path, rows: list[dict[str, str]], *, columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_summary_json(path: Path, records: list[RawScanRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_files": len(records),
        "status_counts": status_counts(records),
    }
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
