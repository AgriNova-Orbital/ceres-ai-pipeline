from __future__ import annotations

from typing import Any, Callable

from tqdm import tqdm


def bytes_to_human(n: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def estimate_download_size(files: list[dict[str, Any]]) -> int:
    total = 0
    for f in files:
        size = f.get("size")
        if size is not None:
            total += int(size)
    return total


def make_pacman_bar(
    total: int,
    *,
    desc: str = "Downloading",
    unit: str = "B",
    unit_scale: bool = True,
) -> tqdm:
    bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
    return tqdm(
        total=total,
        desc=desc,
        unit=unit,
        unit_scale=unit_scale,
        bar_format=bar_format,
        ascii=" C.",
        leave=True,
    )


def make_file_bar(total_files: int, *, desc: str = "Files") -> tqdm:
    return tqdm(
        total=total_files,
        desc=desc,
        unit="file",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ascii=" C.",
        leave=True,
    )


class DownloadProgress:
    def __init__(
        self,
        *,
        total_bytes: int = 0,
        total_files: int = 0,
        on_file_start: Callable[[str, int], None] | None = None,
        on_file_done: Callable[[str, int], None] | None = None,
    ) -> None:
        self._total_bytes = total_bytes
        self._total_files = total_files
        self._on_file_start = on_file_start
        self._on_file_done = on_file_done
        self._bytes_bar: tqdm | None = None
        self._file_bar: tqdm | None = None

    def __enter__(self) -> DownloadProgress:
        if self._total_bytes > 0:
            self._bytes_bar = make_pacman_bar(self._total_bytes)
        if self._total_files > 0:
            self._file_bar = make_file_bar(self._total_files)
        return self

    def __exit__(self, *_: Any) -> None:
        if self._bytes_bar is not None:
            self._bytes_bar.close()
        if self._file_bar is not None:
            self._file_bar.close()

    def on_file_start(self, name: str, size: int) -> None:
        if self._on_file_start is not None:
            self._on_file_start(name, size)

    def on_chunk(self, n_bytes: int) -> None:
        if self._bytes_bar is not None:
            self._bytes_bar.update(n_bytes)

    def on_file_done(self, name: str, size: int) -> None:
        if self._file_bar is not None:
            self._file_bar.update(1)
        if self._on_file_done is not None:
            self._on_file_done(name, size)

    def update_bytes(self, n_bytes: int) -> None:
        if self._bytes_bar is not None:
            self._bytes_bar.update(n_bytes)
