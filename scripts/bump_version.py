from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_version(version: str) -> tuple[int, int, int]:
    if not SEMVER_RE.match(version):
        raise ValueError(f"Invalid SemVer version: {version}")
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def bump_version(current: str, target: str) -> str:
    major, minor, patch = parse_version(current)
    if target == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if target == "minor":
        return f"{major}.{minor + 1}.0"
    if target == "major":
        return f"{major + 1}.0.0"
    parse_version(target)
    return target


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        raise ValueError(f"Version pattern not found in {path}")
    path.write_text(updated, encoding="utf-8")


def _replace_all_existing(path: Path, replacements: list[tuple[str, str]]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    updated = text
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated)
    path.write_text(updated, encoding="utf-8")


def _update_json_version(path: Path, version: str, *, update_lock_root: bool = False) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    if update_lock_root:
        data.setdefault("packages", {}).setdefault("", {})["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def replace_version_in_files(root: Path, version: str) -> None:
    parse_version(version)
    project_name = _project_name(root)
    root.joinpath("VERSION").write_text(f"{version}\n", encoding="utf-8")
    _replace_once(root / "pyproject.toml", r'^(version\s*=\s*)"[^"]+"', rf'\1"{version}"')
    _replace_once(
        root / "uv.lock",
        rf'((?:\[\[package\]\]\nname = "{re.escape(project_name)}"\n)version\s*=\s*)"[^"]+"',
        rf'\1"{version}"',
    )
    _update_json_version(root / "frontend" / "package.json", version)
    _update_json_version(root / "frontend" / "package-lock.json", version, update_lock_root=True)

    _replace_all_existing(
        root / ".env.example",
        [
            (r"^APP_VERSION=.*$", f"APP_VERSION={version}"),
            (r"^SENTRY_RELEASE=.*$", f"SENTRY_RELEASE={version}"),
            (r"^NEXT_PUBLIC_SENTRY_RELEASE=.*$", f"NEXT_PUBLIC_SENTRY_RELEASE={version}"),
        ],
    )
    _replace_all_existing(
        root / "docker-compose.yml",
        [
            (r"APP_VERSION:-[^}]+", f"APP_VERSION:-{version}"),
            (r"SENTRY_RELEASE:-[^}]+", f"SENTRY_RELEASE:-{version}"),
            (r"NEXT_PUBLIC_SENTRY_RELEASE:-[^}]+", f"NEXT_PUBLIC_SENTRY_RELEASE:-{version}"),
        ],
    )
    for dockerfile in [root / "Dockerfile", root / "frontend" / "Dockerfile"]:
        _replace_all_existing(
            dockerfile,
            [
                (r"ARG APP_VERSION=[^\n]+", f"ARG APP_VERSION={version}"),
                (r"ARG SENTRY_RELEASE=[^\n]+", f"ARG SENTRY_RELEASE={version}"),
                (r"ARG NEXT_PUBLIC_SENTRY_RELEASE=[^\n]+", f"ARG NEXT_PUBLIC_SENTRY_RELEASE={version}"),
            ],
        )


def _project_name(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        raise ValueError("Project name not found in pyproject.toml")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump and sync the Ceres product version.")
    parser.add_argument("target", help="patch, minor, major, or an explicit X.Y.Z version")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    current = args.root.joinpath("VERSION").read_text(encoding="utf-8").strip()
    new_version = bump_version(current, args.target)
    replace_version_in_files(args.root, new_version)
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
