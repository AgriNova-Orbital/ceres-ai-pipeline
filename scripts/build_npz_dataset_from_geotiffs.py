"""Build sequence NPZ dataset from weekly GeoTIFFs.

Input:
  A directory of weekly GeoTIFFs exported from GEE, one file per week.
  Expected naming: fr_wheat_feat_YYYYWww.tif (e.g. fr_wheat_feat_2025W01.tif)
  Expected band order: 10 feature bands + 1 risk band (risk is last).
  GeoTIFFs with nodata/masked pixels are supported: see --min-valid-ratio.

Output:
  output_dir/
    index.csv          (column: npz_path)
    examples/*.npz     each NPZ contains:
      - X: (T, C+1, H, W) float32  – C feature bands + 1 validity mask channel
      - y: (T,) float32             – mean risk over valid pixels per week (NaN when unavailable)
      - M: (T, 1, H, W) float32    – standalone validity mask (1=valid, 0=invalid/nodata)

  X is always fully finite: invalid/nodata pixels are imputed to 0 and flagged
  via the mask channel so the model can distinguish real observations from fill
  values. A patch is discarded if its mean valid ratio is below --min-valid-ratio.

Notes:
  This format matches modules.wheat_risk.dataset.WheatRiskNpzSequenceDataset and
  scripts/train_wheat_risk_lstm.py (in_channels is inferred automatically from X.shape[1]).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is on sys.path when running as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.services.dataset_service import run_build


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
    p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help=(
            "Optional anchor date (YYYY-MM-DD) used to derive dates when filenames only have "
            "numeric indices like data_001."
        ),
    )
    p.add_argument(
        "--date-step-days",
        type=int,
        default=7,
        help="Cadence in days for date-based timeline padding (default: 7).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help="CPU worker processes for patch extraction (0 = all logical CPUs).",
    )
    p.add_argument(
        "--gdal-cache-mb",
        type=int,
        default=64,
        help="GDAL cache size (MiB) per process to cap memory usage.",
    )
    p.add_argument(
        "--min-valid-ratio",
        type=float,
        default=0.05,
        help=(
            "Minimum fraction of valid (non-masked, finite) pixels required to keep a patch. "
            "Patches below this threshold are discarded. Default: 0.05."
        ),
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

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

    try:
        run_build(
            input_dir=input_dir,
            output_dir=output_dir,
            patch_size=args.patch_size,
            step_size=args.step_size if args.step_size is not None else args.patch_size,
            expected_weeks=args.expected_weeks,
            start_date=args.start_date,
            date_step_days=args.date_step_days,
            workers=args.workers,
            gdal_cache_mb=args.gdal_cache_mb,
            weeks_limit=args.weeks_limit,
            max_patches=args.max_patches,
            seed=args.seed,
            skip_existing=args.skip_existing,
            min_valid_ratio=args.min_valid_ratio,
        )
    except (ValueError, RuntimeError) as e:
        raise SystemExit(str(e)) from e

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
