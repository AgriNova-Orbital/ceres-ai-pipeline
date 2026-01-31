"""Build sequence NPZ dataset from weekly GeoTIFFs.

Input:
  A directory of weekly GeoTIFFs exported from GEE, one file per week.
  Expected naming: fr_wheat_feat_YYYYWww.tif (e.g. fr_wheat_feat_2025W01.tif)
  Expected band order: 10 feature bands + 1 risk band (risk is last).

Output:
  output_dir/
    index.csv          (column: npz_path)
    examples/*.npz     each NPZ contains:
      - X: (T, C, H, W) float32
      - y: (T,) float32   (mean risk over the patch per week)

Notes:
  This format matches modules.wheat_risk.dataset.WheatRiskNpzSequenceDataset and
  scripts/train_wheat_risk_lstm.py.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is on sys.path when running as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


try:
    import rasterio
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "rasterio is required for this script. Install it (e.g. `uv pip install rasterio`)."
    ) from e


WEEK_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})W(\d{2})\.tif(?:f)?$", re.IGNORECASE)
DATA_PATTERN = re.compile(r"fr_wheat_feat_(\d{4})_data_(.+)\.tif(?:f)?$", re.IGNORECASE)
WEEK_IN_SUFFIX = re.compile(r"\bW(\d{2})\b", re.IGNORECASE)
NUM_IN_SUFFIX = re.compile(r"\b(\d{1,3})\b")


def fill_missing_weeks(
    items: list[tuple[int, object]], *, expected_len: int
) -> tuple[list[object | None], np.ndarray]:
    """Pad a reverse-indexed week sequence to a fixed length.

    We use reverse numeric indices where -1 is newest, -N is oldest.
    This returns values ordered oldest->newest (i.e. -expected_len..-1).

    Returns:
      (values, mask)
        values: length expected_len, missing weeks filled with None
        mask: bool array True where week exists
    """

    if expected_len <= 0:
        raise ValueError("expected_len must be > 0")

    by_idx: dict[int, object] = {int(k): v for k, v in items}

    values: list[object | None] = []
    mask = np.zeros((expected_len,), dtype=bool)
    for i, week_idx in enumerate(range(-expected_len, 0)):
        if week_idx in by_idx:
            values.append(by_idx[week_idx])
            mask[i] = True
        else:
            values.append(None)
    return values, mask


def _parse_week_filename(filename: str) -> tuple[int, int] | None:
    m = WEEK_PATTERN.match(filename)
    if not m:
        m2 = DATA_PATTERN.match(filename)
        if not m2:
            return None
        year = int(m2.group(1))
        suffix = m2.group(2)
        w = WEEK_IN_SUFFIX.search(suffix)
        if w:
            return year, int(w.group(1))

        # Support numeric suffix like fr_wheat_feat_2025_data_001.tif
        n = NUM_IN_SUFFIX.search(suffix)
        if n:
            # Numeric suffix is likely ascending index: 001 is Week 1.
            return year, int(n.group(1))

        # Unknown suffix ordering.
        return year, 0
    return int(m.group(1)), int(m.group(2))


def _find_geotiffs(input_dir: Path) -> list[tuple[str, Path]]:
    tifs: list[tuple[str, Path]] = []
    for p in input_dir.glob("*.tif*"):
        parsed = _parse_week_filename(p.name)
        if parsed:
            key = f"{parsed[0]:04d}W{parsed[1]:02d}"
            tifs.append((key, p))
    tifs.sort(key=lambda x: x[0])
    return tifs


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    return int(v) if v else default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build (T,C,H,W) NPZ sequences from weekly GeoTIFFs exported from GEE."
    )
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument(
        "--drive-folder-id",
        type=str,
        default="",
        help="If set, download GeoTIFFs from this Google Drive folder ID into --input-dir first.",
    )
    p.add_argument(
        "--drive-credentials-json",
        type=Path,
        default=Path(os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT", ""))
        if os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT")
        else None,
        help="OAuth client secrets JSON. Can also set GOOGLE_DRIVE_OAUTH_CLIENT env var.",
    )
    p.add_argument(
        "--drive-token-json",
        type=Path,
        default=Path(os.environ.get("GOOGLE_DRIVE_TOKEN", ""))
        if os.environ.get("GOOGLE_DRIVE_TOKEN")
        else None,
        help="OAuth token cache JSON. Can also set GOOGLE_DRIVE_TOKEN env var.",
    )
    p.add_argument(
        "--drive-skip-existing",
        action="store_true",
        help="When downloading from Drive, skip files that already exist in --input-dir.",
    )
    p.add_argument("--patch-size", type=int, default=_env_int("PATCH_SIZE", 32))
    p.add_argument(
        "--step-size",
        type=int,
        default=None,
        help="Sliding window step in pixels (default: patch-size).",
    )
    p.add_argument(
        "--max-patches",
        type=int,
        default=None,
        help="If set, randomly sample N patch locations.",
    )
    p.add_argument("--seed", type=int, default=_env_int("RANDOM_SEED", 42))
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip building if output index.csv already exists.",
    )
    p.add_argument(
        "--weeks-limit",
        type=int,
        default=None,
        help="Limit to first N weeks (for quick tests).",
    )
    p.add_argument(
        "--expected-weeks",
        type=int,
        default=None,
        help=(
            "If set, pad the time axis to this many weeks (oldest->newest). Missing weeks get "
            "X=0 and y=NaN so training can mask them out."
        ),
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    index_csv = output_dir / "index.csv"
    examples_dir = output_dir / "examples"

    if not input_dir.exists():
        if args.drive_folder_id:
            input_dir.mkdir(parents=True, exist_ok=True)
        else:
            raise SystemExit(f"Input directory does not exist: {input_dir}")

    if args.drive_folder_id:
        if (
            args.drive_credentials_json is None
            or str(args.drive_credentials_json) == ""
        ):
            raise SystemExit(
                "--drive-credentials-json is required when using --drive-folder-id "
                "(or set GOOGLE_DRIVE_OAUTH_CLIENT env var)"
            )

        token_json = args.drive_token_json
        if token_json is None or str(token_json) == "":
            token_json = Path(".cache/drive_token.json")

        from modules.drive_download import filter_weekly_geotiffs
        from modules.drive_oauth import (
            DriveFile,
            ensure_files_downloaded,
            get_drive_service,
            list_folder_files,
        )

        service = get_drive_service(
            credentials_json=args.drive_credentials_json,
            token_json=token_json,
        )
        files = list_folder_files(service, folder_id=str(args.drive_folder_id))
        files_dicts = [
            {"id": f.id, "name": f.name, "mimeType": f.mime_type}
            for f in files
            if f.name
        ]
        selected = filter_weekly_geotiffs(files_dicts)
        if not selected:
            raise SystemExit("No matching GeoTIFFs found in the Drive folder")

        by_id = {f.id: f for f in files}
        to_dl: list[DriveFile] = []
        for d in selected:
            fid = str(d.get("id", ""))
            if fid in by_id:
                to_dl.append(by_id[fid])
        print(f"Downloading {len(to_dl)} GeoTIFFs from Drive -> {input_dir}")
        ensure_files_downloaded(
            service,
            files=to_dl,
            out_dir=input_dir,
            skip_existing=bool(args.drive_skip_existing),
        )
    if args.skip_existing and index_csv.exists():
        print(f"Skipping: {index_csv} already exists")
        return 0
    if args.patch_size <= 0:
        raise SystemExit("--patch-size must be > 0")

    tifs = _find_geotiffs(input_dir)
    if not tifs:
        raise SystemExit(f"No matching GeoTIFFs found in {input_dir}")

    # Convert to (week_idx, path) where week_idx is increasing for oldest->newest.
    items: list[tuple[int, Path]] = []
    for _, p in tifs:
        parsed = _parse_week_filename(p.name)
        if parsed is None:
            continue
        _, week_idx = parsed
        items.append((int(week_idx), p))

    if not items:
        raise SystemExit(f"No parseable weekly GeoTIFFs found in {input_dir}")

    # Infer expected length from reverse-index scheme if not provided.
    inferred_expected: int | None = None
    min_week = min(k for k, _ in items)
    max_week = max(k for k, _ in items)
    if min_week < 0:
        inferred_expected = abs(int(min_week))
    else:
        inferred_expected = int(max_week)

    expected_len = (
        int(args.expected_weeks)
        if args.expected_weeks is not None
        else int(inferred_expected)
    )
    if expected_len <= 0:
        raise SystemExit("expected weeks must be > 0")

    # If reverse-indexed (-N..-1), pad with missing weeks.
    padded_paths: list[Path | None]
    if min_week < 0:
        padded_vals, _mask = fill_missing_weeks(
            [(k, v) for k, v in items], expected_len=expected_len
        )
        padded_paths = [p if isinstance(p, Path) else None for p in padded_vals]
    else:
        # For forward scheme 1..N: build ordered list.
        by_week = {int(k): v for k, v in items}
        padded_paths = [by_week.get(i) for i in range(1, expected_len + 1)]

    if args.weeks_limit is not None:
        if args.weeks_limit <= 0:
            raise SystemExit("--weeks-limit must be > 0")
        padded_paths = padded_paths[: int(args.weeks_limit)]
        expected_len = len(padded_paths)

    present = sum(1 for p in padded_paths if p is not None)
    missing = expected_len - present
    print(f"Weeks: expected={expected_len} present={present} missing={missing}")

    # Open all present weeks once; keep None for missing.
    srcs: list[Any | None] = []
    for p in padded_paths:
        if p is None:
            srcs.append(None)
        else:
            srcs.append(rasterio.open(p))
    try:
        first = next((s for s in srcs if s is not None), None)
        if first is None:
            raise SystemExit("All weeks are missing; nothing to build")
        h = first.height
        w = first.width
        band_count = first.count
        for s in srcs:
            if s is None:
                continue
            if s.height != h or s.width != w or s.count != band_count:
                raise SystemExit("GeoTIFFs must have same width/height/band-count")

        if band_count < 2:
            raise SystemExit(f"Expected >=2 bands, got {band_count}")
        feature_bands = list(range(1, band_count))
        risk_band = band_count

        step = (
            int(args.step_size) if args.step_size is not None else int(args.patch_size)
        )
        rows = list(range(0, h - args.patch_size + 1, step))
        cols = list(range(0, w - args.patch_size + 1, step))
        if not rows or not cols:
            raise SystemExit("Patch/grid is empty: check patch-size vs raster size")

        coords = [(r, c) for r in rows for c in cols]
        if args.max_patches is not None:
            if args.max_patches <= 0:
                raise SystemExit("--max-patches must be > 0")
            if args.max_patches < len(coords):
                rng = np.random.default_rng(int(args.seed))
                idx = rng.choice(len(coords), size=int(args.max_patches), replace=False)
                coords = [coords[int(i)] for i in idx]
        print(f"Patch locations: {len(coords)}")

        output_dir.mkdir(parents=True, exist_ok=True)
        examples_dir.mkdir(parents=True, exist_ok=True)

        index_rows: list[dict[str, str]] = []

        for row, col in tqdm(coords, desc="Building patches", unit="patch", mininterval=1.0):
            x_seq: list[np.ndarray] = []
            y_seq: list[np.float32] = []

            ps = int(args.patch_size)
            win = ((row, row + ps), (col, col + ps))
            for s in srcs:
                if s is None:
                    # Missing week: keep X=0 and y=NaN. Training should mask NaNs.
                    x_seq.append(
                        np.zeros((len(feature_bands), ps, ps), dtype=np.float32)
                    )
                    y_seq.append(np.float32(np.nan))
                    continue

                # Features: (C,H,W)
                feat = s.read(indexes=feature_bands, window=win).astype(
                    np.float32, copy=False
                )
                x_seq.append(feat)

                risk = s.read(indexes=risk_band, window=win).astype(
                    np.float32, copy=False
                )
                y_seq.append(np.float32(np.nanmean(risk)))

            X = np.stack(x_seq, axis=0)  # (T,C,H,W)
            y = np.asarray(y_seq, dtype=np.float32)  # (T,)

            # Check for data quality: If >50% of features are NaN, skip this patch
            if np.isnan(X).mean() > 0.5:
                continue

            npz_name = f"patch_r{row:05d}_c{col:05d}.npz"
            npz_rel = f"examples/{npz_name}"
            np.savez_compressed(examples_dir / npz_name, X=X, y=y)
            index_rows.append({"npz_path": npz_rel})

        with index_csv.open("w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=["npz_path"])
            wtr.writeheader()
            wtr.writerows(index_rows)

        print(f"Wrote {index_csv} with {len(index_rows)} examples")
        return 0
    finally:
        for s in srcs:
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
