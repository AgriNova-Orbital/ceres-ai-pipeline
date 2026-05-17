from __future__ import annotations

from pathlib import Path
from typing import Any


_LEVEL_SENTINEL = "__CERES_LEVEL_PLACEHOLDER__"


def _path_text(path_like: Any, default: str, *, field: str) -> str:
    if path_like is None:
        return default
    if not isinstance(path_like, str):
        raise ValueError(f"{field} must be a string path")
    return path_like.strip() or default


def normalize_repo_path(
    root: Path | str,
    path_like: Any,
    default: str,
    *,
    field: str = "path",
) -> str:
    raw = _path_text(path_like, default, field=field)
    path = Path(raw)
    if path.is_absolute():
        raise ValueError(f"{field} must be relative to the repository root")

    root_path = Path(root).resolve(strict=False)
    resolved = (root_path / path).resolve(strict=False)
    try:
        resolved.relative_to(root_path)
    except ValueError as e:
        raise ValueError(f"{field} must stay within the repository root") from e
    return str(resolved)


def normalize_repo_template_path(
    root: Path | str,
    path_like: Any,
    default: str,
    *,
    field: str = "path",
) -> str:
    raw = _path_text(path_like, default, field=field)
    unexpected_placeholders = raw.replace("{level}", "")
    if "{" in unexpected_placeholders or "}" in unexpected_placeholders:
        raise ValueError(f"{field} may only use the {{level}} placeholder")

    sentinel_raw = raw.replace("{level}", _LEVEL_SENTINEL)
    sentinel_default = default.replace("{level}", _LEVEL_SENTINEL)
    normalized = normalize_repo_path(
        root,
        sentinel_raw,
        sentinel_default,
        field=field,
    )
    return normalized.replace(_LEVEL_SENTINEL, "{level}")


def resolve_repo_path(
    root: Path | str,
    path_like: Path | str,
    *,
    field: str = "path",
    base: Path | str | None = None,
) -> Path:
    root_path = Path(root).resolve(strict=False)
    path = Path(path_like)
    if path.is_absolute():
        candidate = path
    else:
        base_path = Path(base).resolve(strict=False) if base is not None else root_path
        candidate = base_path / path

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root_path)
    except ValueError as e:
        raise ValueError(f"{field} must stay within the repository root") from e
    return resolved
