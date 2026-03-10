from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.ee_import import require_ee
from modules.google_user_oauth import (
    get_google_web_client_config,
    load_google_credentials_from_env,
)
from modules.wheat_risk.config import PipelineConfig, StagePreset
from modules.wheat_risk.labels import risk_weekly
from modules.wheat_risk.masks import (
    build_aoi,
    cropland_mask_dynamicworld,
    cropland_mask_worldcover,
)
from modules.wheat_risk.timebins import week_bins


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
            "Export weekly wheat risk rasters to Google Drive (Earth Engine). "
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

    p.add_argument(
        "--start-date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Inclusive start date (ISO, overrides preset).",
    )
    p.add_argument(
        "--end-date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Inclusive end date (ISO, overrides preset).",
    )
    p.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help=(
            "AOI bounding box: MIN_LON MIN_LAT MAX_LON MAX_LAT "
            "(lon in [-180, 180], lat in [-90, 90])."
        ),
    )

    p.add_argument(
        "--use-dynamicworld",
        action="store_true",
        help="Use Dynamic World cropland mask instead of WorldCover.",
    )
    p.add_argument(
        "--max-cloud",
        type=float,
        metavar="PCT",
        help="Max S2 cloudy pixel percentage (passed into label builder).",
    )

    p.add_argument(
        "--limit",
        type=int,
        default=4,
        metavar="N",
        help="Export at most N weekly bins (default: 4)",
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--run",
        dest="run",
        action="store_true",
        help="Start Earth Engine export tasks (requires --drive-folder).",
    )
    mode.add_argument(
        "--dry-run",
        dest="run",
        action="store_false",
        help="Plan-only mode: print what would run and exit (default).",
    )
    p.set_defaults(run=False)
    return p


def _export_name_for_bin(bin_start: str) -> str:
    y, w, _ = date.fromisoformat(bin_start).isocalendar()
    return f"fr_wheat_risk_{y}W{w:02d}"


def _initialize_ee_for_export(ee: object, *, ee_project: str | None) -> str | None:
    creds = load_google_credentials_from_env()
    resolved_project = ee_project
    if resolved_project is None:
        try:
            _, _, project_id = get_google_web_client_config()
            if project_id:
                resolved_project = project_id
        except Exception:
            resolved_project = ee_project

    if creds is not None and resolved_project:
        ee.Initialize(project=resolved_project, credentials=creds)
        return resolved_project
    if creds is not None:
        ee.Initialize(credentials=creds)
        return resolved_project
    if resolved_project:
        ee.Initialize(project=resolved_project)
        return resolved_project
    ee.Initialize()
    return resolved_project


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.limit < 0:
        parser.error("--limit must be >= 0")

    if args.run and not args.drive_folder:
        parser.error("--drive-folder is required with --run")

    stage = _stage_preset_from_cli(args.stage)
    base = PipelineConfig.default_france_2025(stage)
    try:
        cfg = PipelineConfig(
            bbox=tuple(args.bbox) if args.bbox is not None else base.bbox,
            start_date=args.start_date or base.start_date,
            end_date=args.end_date or base.end_date,
            time_grain=base.time_grain,
            stage=stage,
            drive_folder=args.drive_folder,
            max_cloud=args.max_cloud,
            use_dynamicworld=bool(args.use_dynamicworld),
        )
    except ValueError as e:
        parser.error(str(e))

    bins = week_bins(cfg.start_date, cfg.end_date)
    bins = bins[: args.limit]

    if not args.run:
        print("DRY RUN: no Earth Engine calls will be made")
        print(
            f"exports={len(bins)} limit={args.limit} drive_folder={cfg.drive_folder!r}"
        )
        print(
            f"stage={args.stage} scale_m={cfg.stage.scale_m} bbox={cfg.bbox} "
            f"date_range={cfg.start_date}..{cfg.end_date}"
        )
        if bins:
            first, last = bins[0], bins[-1]
            print(f"first_bin={first[0]}..{first[1]} last_bin={last[0]}..{last[1]}")
        print(
            "Would: initialize Earth Engine, build AOI + cropland mask, build risk image per "
            "week, and start Drive GeoTIFF exports."
        )
        return 0

    oauth_creds_present = bool(os.environ.get("GOOGLE_OAUTH_TOKEN_JSON"))
    if not args.ee_project and not oauth_creds_present:
        print(
            "Hint: pass --ee-project <GCP_PROJECT_ID> (or set EE_PROJECT env var), then re-run."
        )
        return 2

    ee = require_ee("weekly risk raster export")
    try:
        _initialize_ee_for_export(ee, ee_project=args.ee_project)
    except Exception as e:
        msg = str(e)
        print(msg)
        if "no project found" in msg.lower():
            print(
                "Hint: pass --ee-project <GCP_PROJECT_ID> (or set EE_PROJECT env var), then re-run."
            )
        return 2

    aoi = build_aoi(cfg.bbox)
    if cfg.use_dynamicworld:
        cropland_mask = cropland_mask_dynamicworld(aoi, cfg.start_date, cfg.end_date)
    else:
        cropland_mask = cropland_mask_worldcover(aoi)

    labels_cfg: dict[str, object] = {}
    if cfg.max_cloud is not None:
        labels_cfg["max_cloud"] = float(cfg.max_cloud)

    total_weeks = len(week_bins(cfg.start_date, cfg.end_date))
    for i, (start, end) in enumerate(bins):
        name = _export_name_for_bin(start)

        img = risk_weekly(
            aoi=aoi,
            start=start,
            end=end,
            cfg=labels_cfg,
            cropland_mask=cropland_mask,
            week_index=i,
            total_weeks=total_weeks,
        )

        task = ee.batch.Export.image.toDrive(
            image=img,
            description=name,
            folder=cfg.drive_folder,
            fileNamePrefix=name,
            region=aoi,
            scale=int(cfg.stage.scale_m),
            maxPixels=1e13,
            fileFormat="GeoTIFF",
        )
        task.start()
        print(f"started: {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
