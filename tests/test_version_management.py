from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-(?:alpha|beta)\.\d+)?$")


def read_version(root: Path = ROOT) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def test_version_file_is_semver() -> None:
    version = read_version()

    assert SEMVER_RE.match(version)


def test_python_and_frontend_versions_match_version_file() -> None:
    from scripts.bump_version import product_version_to_python

    version = read_version()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == product_version_to_python(version)
    assert package["version"] == version
    assert lock["version"] == version
    assert lock["packages"][""]["version"] == version


def test_bump_version_supports_semver_parts_and_explicit_versions() -> None:
    from scripts.bump_version import bump_version, product_version_to_python, release_channel

    assert bump_version("1.2.3", "patch") == "1.2.4"
    assert bump_version("1.2.3", "minor") == "1.3.0"
    assert bump_version("1.2.3", "major") == "2.0.0"
    assert bump_version("1.2.3", "1.4.0") == "1.4.0"
    assert bump_version("1.2.3", "alpha") == "1.2.4-alpha.1"
    assert bump_version("1.2.4-alpha.1", "alpha") == "1.2.4-alpha.2"
    assert bump_version("1.2.4-alpha.2", "beta") == "1.2.4-beta.1"
    assert bump_version("1.2.4-beta.1", "beta") == "1.2.4-beta.2"
    assert bump_version("1.2.4-beta.2", "release") == "1.2.4"
    assert bump_version("1.2.3", "1.3.0-alpha.1") == "1.3.0-alpha.1"
    assert product_version_to_python("1.3.0-alpha.1") == "1.3.0a1"
    assert product_version_to_python("1.3.0-beta.2") == "1.3.0b2"
    assert release_channel("1.3.0-alpha.1") == "alpha"
    assert release_channel("1.3.0-beta.1") == "beta"
    assert release_channel("1.3.0") == "release"


def test_replace_version_in_files_updates_project_metadata(tmp_path: Path) -> None:
    from scripts.bump_version import replace_version_in_files

    (tmp_path / "frontend").mkdir()
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps({"name": "demo-frontend", "version": "1.2.3"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "frontend" / "package-lock.json").write_text(
        json.dumps({"name": "demo-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
        encoding="utf-8",
    )

    replace_version_in_files(tmp_path, "1.3.0")

    assert (tmp_path / "VERSION").read_text(encoding="utf-8") == "1.3.0\n"
    assert 'version = "1.3.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.3.0"' in (tmp_path / "uv.lock").read_text(encoding="utf-8")
    package = json.loads((tmp_path / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((tmp_path / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert package["version"] == "1.3.0"
    assert lock["version"] == "1.3.0"
    assert lock["packages"][""]["version"] == "1.3.0"


def test_replace_version_in_files_converts_prerelease_for_python_metadata(tmp_path: Path) -> None:
    from scripts.bump_version import replace_version_in_files

    (tmp_path / "frontend").mkdir()
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps({"name": "demo-frontend", "version": "1.2.3"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "frontend" / "package-lock.json").write_text(
        json.dumps({"name": "demo-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
        encoding="utf-8",
    )

    replace_version_in_files(tmp_path, "1.3.0-beta.1")

    assert (tmp_path / "VERSION").read_text(encoding="utf-8") == "1.3.0-beta.1\n"
    assert 'version = "1.3.0b1"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.3.0b1"' in (tmp_path / "uv.lock").read_text(encoding="utf-8")
    package = json.loads((tmp_path / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((tmp_path / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert package["version"] == "1.3.0-beta.1"
    assert lock["version"] == "1.3.0-beta.1"


def test_release_metadata_defaults_match_version_file() -> None:
    version = read_version()
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert f"APP_VERSION={version}" in env_example
    assert f"SENTRY_RELEASE={version}" in env_example
    assert f"NEXT_PUBLIC_SENTRY_RELEASE={version}" in env_example
    assert f"APP_VERSION:-{version}" in compose
    assert f"SENTRY_RELEASE:-{version}" in compose
    assert f"NEXT_PUBLIC_SENTRY_RELEASE:-{version}" in compose


def test_dockerfiles_define_image_version_metadata() -> None:
    version = read_version()

    for rel in ["Dockerfile", "frontend/Dockerfile"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert f"ARG APP_VERSION={version}" in text
        assert "org.opencontainers.image.version=$APP_VERSION" in text

    frontend_dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert f"ARG SENTRY_RELEASE={version}" in frontend_dockerfile
    assert f"ARG NEXT_PUBLIC_SENTRY_RELEASE={version}" in frontend_dockerfile


def test_release_versioning_rules_are_documented() -> None:
    doc = (ROOT / "docs" / "release-versioning.md").read_text(encoding="utf-8")

    for token in ["alpha", "beta", "release", "VERSION", "scripts/bump_version.py"]:
        assert token in doc
