#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tarfile
from pathlib import Path


def _import_zstandard():
    try:
        import zstandard as zstd  # type: ignore

        return zstd
    except ImportError as e:
        raise SystemExit(
            "zstandard is required. Install with: UV_PYTHON=3.12 uv sync --dev --extra distributed"
        ) from e


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Pack a dataset directory into a .tar.zst archive for Ray workers to download. "
            "Expected layout: <dir>/index.csv and <dir>/shards/*.npz"
        )
    )
    p.add_argument("--dataset-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="Output .tar.zst path")
    p.add_argument(
        "--root-name",
        default=None,
        help="Top-level folder name inside archive (default: dataset-dir name)",
    )
    p.add_argument("--level", type=int, default=10, help="Zstd compression level")
    args = p.parse_args(argv)

    ds_dir = args.dataset_dir.resolve()
    if not ds_dir.is_dir():
        raise SystemExit(f"dataset-dir not found: {ds_dir}")

    if not (ds_dir / "index.csv").exists():
        raise SystemExit(f"missing {ds_dir / 'index.csv'}")

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    root_name = args.root_name or ds_dir.name

    zstd = _import_zstandard()
    cctx = zstd.ZstdCompressor(level=int(args.level))

    tmp = out.with_suffix(out.suffix + ".partial")
    if tmp.exists():
        tmp.unlink()

    with tmp.open("wb") as f:
        with cctx.stream_writer(f) as compressor:
            with tarfile.open(fileobj=compressor, mode="w|") as tar:
                for path in ds_dir.rglob("*"):
                    rel = path.relative_to(ds_dir)
                    arcname = os.path.join(root_name, str(rel))
                    tar.add(path, arcname=arcname)

    tmp.replace(out)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
