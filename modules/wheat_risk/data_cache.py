from __future__ import annotations

import os
import tarfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatasetCache:
    cache_root: Path

    def dataset_dir(self, name: str) -> Path:
        if not name:
            raise ValueError("name must be non-empty")
        return self.cache_root / name


def _import_filelock():
    try:
        from filelock import FileLock  # type: ignore

        return FileLock
    except ImportError as e:
        raise RuntimeError(
            "filelock is required for dataset caching. Install project dependencies with uv."
        ) from e


def _import_zstandard():
    try:
        import zstandard as zstd  # type: ignore

        return zstd
    except ImportError as e:
        raise RuntimeError(
            "zstandard is required to extract .tar.zst datasets. Install it with: "
            "`uv sync --dev --extra distributed` (and on GPU workers: also `--extra ml`)."
        ) from e


def _download_to(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    if tmp.exists():
        tmp.unlink()

    with urllib.request.urlopen(url) as r, tmp.open("wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    tmp.replace(dest)


def _safe_extract_tar(tar: tarfile.TarFile, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    abs_dst = dst.resolve()

    # Iterate over the tar file (stream-friendly) instead of getmembers()
    for m in tar:
        target = (dst / m.name).resolve()
        if not str(target).startswith(str(abs_dst)):
            raise RuntimeError(f"Unsafe path in tar: {m.name}")
        tar.extract(m, dst)


def extract_tar_zst(archive_path: Path, dst_dir: Path) -> None:
    if not archive_path.exists():
        raise FileNotFoundError(str(archive_path))

    zstd = _import_zstandard()

    with archive_path.open("rb") as f:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                _safe_extract_tar(tar, dst_dir)


def ensure_dataset_cached(
    *,
    data_url: str,
    dataset_name: str,
    cache_root: Path,
    expected_index_relpath: str = "index.csv",
) -> Path:
    """Ensure dataset exists locally; download+extract if missing.

    Returns the dataset root directory.

    Dataset directory layout (recommended):
    - <cache_root>/<dataset_name>/index.csv
    - <cache_root>/<dataset_name>/shards/*.npz
    """

    if not data_url:
        raise ValueError("data_url must be non-empty")

    cache = DatasetCache(cache_root=cache_root)
    ds_dir = cache.dataset_dir(dataset_name)
    archive_path = cache.dataset_dir(dataset_name + "_archive")

    FileLock = _import_filelock()
    lock_path = ds_dir.with_suffix(".lock")

    with FileLock(str(lock_path)):
        # Fast path: if the dataset is already present (direct or wrapped)
        existing_root = _detect_dataset_root(ds_dir, expected_index_relpath)
        if existing_root is not None and (existing_root / ".ready").exists():
            return existing_root

        # Clean partial directory if present
        if (
            ds_dir.exists()
            and _detect_dataset_root(ds_dir, expected_index_relpath) is None
        ):
            # best-effort cleanup
            for root, dirs, files in os.walk(ds_dir, topdown=False):
                for name in files:
                    Path(root, name).unlink(missing_ok=True)
                for name in dirs:
                    Path(root, name).rmdir()
            ds_dir.rmdir()

        # Determine archive filename
        parsed = urllib.parse.urlparse(data_url)
        filename = Path(parsed.path).name
        if not filename:
            filename = f"{dataset_name}.tar.zst"
        archive_file = archive_path / filename

        _download_to(data_url, archive_file)

        if filename.endswith(".tar.zst"):
            extract_tar_zst(archive_file, ds_dir)
        elif filename.endswith(".tar"):
            with tarfile.open(archive_file, mode="r") as tar:
                _safe_extract_tar(tar, ds_dir)
        else:
            raise RuntimeError(f"Unsupported dataset archive: {filename}")

        ds_root = _detect_dataset_root(ds_dir, expected_index_relpath)
        if ds_root is None:
            raise RuntimeError(
                f"Dataset extracted but missing expected index: {expected_index_relpath}. "
                f"Extracted into: {ds_dir}. Check your archive contents."
            )

        (ds_root / ".ready").write_text("ok")
        return ds_root


def _detect_dataset_root(extract_dir: Path, expected_index_relpath: str) -> Path | None:
    """Return dataset root inside extract_dir.

    Supports both layouts:
    - extract_dir/index.csv
    - extract_dir/<single_dir>/index.csv
    """

    direct = extract_dir / expected_index_relpath
    if direct.exists():
        return extract_dir

    if not extract_dir.exists():
        return None

    subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(subdirs) != 1:
        return None

    wrapped = subdirs[0] / expected_index_relpath
    if wrapped.exists():
        return subdirs[0]

    return None
