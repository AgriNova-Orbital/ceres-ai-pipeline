from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_version(root: Path = ROOT) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def test_version_file_is_semver() -> None:
    version = read_version()

    assert SEMVER_RE.match(version)


def test_python_and_frontend_versions_match_version_file() -> None:
    version = read_version()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == version
    assert package["version"] == version
    assert lock["version"] == version
    assert lock["packages"][""]["version"] == version
