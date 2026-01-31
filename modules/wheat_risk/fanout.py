from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlatformCommand:
    argv: list[str]


def _quote_cd_path(path: Path) -> str:
    # Safe enough for basic paths; we keep to ASCII and avoid complex quoting.
    s = str(path)
    return s.replace('"', '"')


def build_posix_bash_command(*, repo_dir: Path, cmd: str) -> PlatformCommand:
    cd = _quote_cd_path(repo_dir)
    # bash -lc ensures consistent parsing and supports env var prefixes.
    return PlatformCommand(argv=["bash", "-lc", f'cd "{cd}" && {cmd}'])


def build_windows_cmd_command(*, repo_dir: Path, cmd: str) -> PlatformCommand:
    cd = _quote_cd_path(repo_dir)
    # cmd.exe doesn't support POSIX env var prefixes like UV_PYTHON=3.12.
    return PlatformCommand(argv=["cmd.exe", "/c", f'cd /d "{cd}" && {cmd}'])
