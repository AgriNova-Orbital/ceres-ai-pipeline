from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.ee_import import require_ee
from modules.wheat_risk.config import PipelineConfig, StagePreset
from modules.wheat_risk.export_patches import (
    export_patch_tensors_to_drive,
    sample_patch_grid,
)


def _stage_preset_from_cli(stage: int) -> StagePreset:
    if stage == 1:
        return StagePreset.stage1()
    if stage == 2:
        return StagePreset.stage2()
    if stage == 3:
        return StagePreset.stage3()
    raise ValueError(f"Unsupported stage: {stage}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Export wheat risk patches to Google Drive (Earth Engine). "
            "By default this runs in dry-run mode."
        )
    )
    p.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3],
        required=True,
        help="Pipeline stage preset (affects scale/patch size).",
    )
    p.add_argument(
        "--samples",
        type=int,
        metavar="N",
        help="Number of patches to sample (required with --run).",
    )
    p.add_argument(
        "--drive-folder",
        type=str,
        metavar="FOLDER",
        help="Google Drive folder to export into (required with --run).",
    )

    p.add_argument(
        "--ee-project",
        type=str,
        default=os.environ.get("EE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help=(
            "GEE project id for ee.Initialize(project=...). If not set, Earth Engine may error "
            "with 'no project found'. Can also be set via EE_PROJECT env var."
        ),
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--run",
        dest="run",
        action="store_true",
        help="Start Earth Engine export tasks (requires --samples and --drive-folder).",
    )
    mode.add_argument(
        "--dry-run",
        dest="run",
        action="store_false",
        help="Plan-only mode: print what would run and exit (default).",
    )
    p.set_defaults(run=False)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.run:
        missing: list[str] = []
        if args.samples is None:
            missing.append("--samples")
        if args.drive_folder is None:
            missing.append("--drive-folder")
        if missing:
            parser.error(
                "the following arguments are required with --run: " + ", ".join(missing)
            )

    stage = _stage_preset_from_cli(args.stage)
    base = PipelineConfig.default_france_2025(stage)
    cfg = PipelineConfig(
        bbox=base.bbox,
        start_date=base.start_date,
        end_date=base.end_date,
        time_grain=base.time_grain,
        stage=stage,
        sample_count=args.samples,
        drive_folder=args.drive_folder,
    )

    if not args.run:
        print("DRY RUN: no Earth Engine calls will be made")
        print(
            f"stage={args.stage} scale_m={cfg.stage.scale_m} patch_size_px={cfg.stage.patch_size_px}"
        )
        print(f"samples={cfg.sample_count} drive_folder={cfg.drive_folder!r}")
        print(
            f"bbox={cfg.bbox} date_range={cfg.start_date}..{cfg.end_date} time_grain={cfg.time_grain}"
        )
        print(
            "Would: initialize Earth Engine, sample patch grid, and start Drive exports "
            "(pass --run plus required args to run for real)."
        )
        return 0

    try:
        ee = require_ee("wheat risk patch export")
    except RuntimeError as e:
        print(str(e))
        return 2

    try:
        if args.ee_project:
            ee.Initialize(project=args.ee_project)
        else:
            ee.Initialize()
    except Exception as e:
        msg = str(e)
        print(msg)
        if "no project found" in msg.lower():
            print(
                "Hint: pass --ee-project <GCP_PROJECT_ID> (or set EE_PROJECT env var), then re-run."
            )
        return 2

    aoi = ee.Geometry.Rectangle(list(cfg.bbox))
    grid = sample_patch_grid(aoi, cfg)
    export_patch_tensors_to_drive(grid, cfg=cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
