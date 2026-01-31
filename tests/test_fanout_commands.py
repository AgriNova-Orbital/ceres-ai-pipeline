from pathlib import Path

from modules.wheat_risk.fanout import (
    build_posix_bash_command,
    build_windows_cmd_command,
)


def test_build_posix_bash_command_includes_cd_and_cmd() -> None:
    cmd = build_posix_bash_command(repo_dir=Path("/tmp/repo"), cmd="git pull")
    assert cmd.argv[:2] == ["bash", "-lc"]
    assert "cd" in cmd.argv[2]
    assert "git pull" in cmd.argv[2]


def test_build_windows_cmd_command_includes_cd_and_cmd() -> None:
    cmd = build_windows_cmd_command(repo_dir=Path(r"C:\repo"), cmd="git pull")
    assert cmd.argv[:2] == ["cmd.exe", "/c"]
    assert "cd /d" in cmd.argv[2].lower()
    assert "git pull" in cmd.argv[2]
