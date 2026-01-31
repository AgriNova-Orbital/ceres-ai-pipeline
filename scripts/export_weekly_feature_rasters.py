"""Export weekly feature + risk rasters to Google Drive (Earth Engine).

This script exports multi-source features (S2 indices, S1 SAR, meteo, LST) combined
with the risk label as GeoTIFFs. Each weekly bin becomes a single GeoTIFF containing
all bands.

Usage:
    # Dry-run to see what would be exported
    python scripts/export_weekly_feature_rasters.py --stage 1 --drive-folder wheat_data

    # Actually run the exports
    python scripts/export_weekly_feature_rasters.py --stage 1 --drive-folder wheat_data --run

    # With custom date range
    python scripts/export_weekly_feature_rasters.py --stage 1 --drive-folder wheat_data \
        --start-date 2025-03-01 --end-date 2025-06-30 --run

    # With max cloud filter
    python scripts/export_weekly_feature_rasters.py --stage 1 --drive-folder wheat_data \
        --max-cloud 30 --run

Configuration:
    Settings can be set via environment variables or a .env file:
    - EE_PROJECT: GEE project ID
    - DEFAULT_START_DATE: Default start date (YYYY-MM-DD)
    - DEFAULT_END_DATE: Default end date (YYYY-MM-DD)
    - DEFAULT_AOI: Default bounding box (lon_minlon_max,lat_max)
    -,lat_min, MAX_CLOUD_COVER: Max S2 cloud percentage
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from modules.ee_import import require_ee
from modules.wheat_risk.config import PipelineConfig, StagePreset
from modules.wheat_risk.features import build_weekly_features, required_feature_names
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
            "Export weekly feature+risk rasters to Google Drive (Earth Engine). "
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
        default=os.environ.get("EE_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or "",
        help=(
            "GEE project id for ee.Initialize(project=...). If not set, Earth Engine may error "
            "with 'no project found'. Can also be set via EE_PROJECT env var or .env file."
        ),
    )

    p.add_argument(
        "--start-date",
        type=str,
        default=os.environ.get("DEFAULT_START_DATE", ""),
        metavar="YYYY-MM-DD",
        help="Inclusive start date (ISO, overrides preset).",
    )
    p.add_argument(
        "--end-date",
        type=str,
        default=os.environ.get("DEFAULT_END_DATE", ""),
        metavar="YYYY-MM-DD",
        help="Inclusive end date (ISO, overrides preset).",
    )
    p.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=None,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help=(
            "AOI bounding box: MIN_LON MIN_LAT MAX_LON MAX_LAT "
            "(lon in [-180, 180], lat in [-90, 90]). "
            "Can also be set via DEFAULT_AOI env var (.env)."
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
        default=float(os.environ.get("MAX_CLOUD_COVER", ""))
        if os.environ.get("MAX_CLOUD_COVER")
        else None,
        metavar="PCT",
        help="Max S2 cloudy pixel percentage (passed into label builder).",
    )
    p.add_argument(
        "--rain-source",
        type=str,
        choices=["era5", "chirps", "stub"],
        default="era5",
        help="Rainfall data source (default: era5).",
    )
    p.add_argument(
        "--lst-source",
        type=str,
        choices=["modis", "stub"],
        default="modis",
        help="LST data source (default: modis).",
    )

    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Export at most N weekly bins (None = all weeks, default: None)",
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
    return f"fr_wheat_feat_{y}W{w:02d}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be >= 0")

    if args.run and not args.drive_folder:
        parser.error("--drive-folder is required with --run")

    stage = _stage_preset_from_cli(args.stage)
    base = PipelineConfig.default_france_2025(stage)

    bbox: tuple[float, float, float, float] | None = None
    if args.bbox is not None:
        bbox = (args.bbox[0], args.bbox[1], args.bbox[2], args.bbox[3])
    elif os.environ.get("DEFAULT_AOI"):
        try:
            parts = [float(x.strip()) for x in os.environ["DEFAULT_AOI"].split(",")]
            if len(parts) == 4:
                bbox = (parts[0], parts[1], parts[2], parts[3])
        except (ValueError, TypeError):
            pass

    if bbox is None:
        bbox = base.bbox

    start_date = args.start_date if args.start_date else base.start_date
    end_date = args.end_date if args.end_date else base.end_date

    try:
        cfg = PipelineConfig(
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            time_grain=base.time_grain,
            stage=stage,
            drive_folder=args.drive_folder,
            max_cloud=args.max_cloud,
            use_dynamicworld=bool(args.use_dynamicworld),
        )
    except ValueError as e:
        parser.error(str(e))

    bins = week_bins(cfg.start_date, cfg.end_date)
    if args.limit is not None:
        bins = bins[: args.limit]

    feature_names = required_feature_names()
    all_bands = feature_names + ("risk",)

    if not args.run:
        limit_display = args.limit if args.limit is not None else "all"
        print("DRY RUN: no Earth Engine calls will be made")
        print(
            f"exports={len(bins)} limit={limit_display} drive_folder={cfg.drive_folder!r}"
        )
        print(
            f"stage={args.stage} scale_m={cfg.stage.scale_m} bbox={cfg.bbox} "
            f"date_range={cfg.start_date}..{cfg.end_date}"
        )
        print(f"feature_bands={list(feature_names)}")
        print(f"label_band=risk")
        print(f"total_bands={len(all_bands)}")
        if bins:
            first, last = bins[0], bins[-1]
            print(f"first_bin={first[0]}..{first[1]} last_bin={last[0]}..{last[1]}")
        print(
            "Would: initialize Earth Engine, build AOI + cropland mask, build feature stack + risk "
            "per week, and start Drive GeoTIFF exports."
        )
        return 0

    ee = require_ee("weekly feature+risk raster export")
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

    aoi = build_aoi(cfg.bbox)
    if cfg.use_dynamicworld:
        cropland_mask = cropland_mask_dynamicworld(aoi, cfg.start_date, cfg.end_date)
    else:
        cropland_mask = cropland_mask_worldcover(aoi)

    feature_cfg = {
        "max_cloud": float(cfg.max_cloud) if cfg.max_cloud is not None else None,
        "rain_source": args.rain_source,
        "lst_source": args.lst_source,
    }
    feature_cfg = {k: v for k, v in feature_cfg.items() if v is not None}

    labels_cfg: dict[str, object] = {}
    if cfg.max_cloud is not None:
        labels_cfg["max_cloud"] = float(cfg.max_cloud)

    total_weeks = len(week_bins(cfg.start_date, cfg.end_date))
    for i, (start, end) in enumerate(bins):
        name = _export_name_for_bin(start)

        features_img = build_weekly_features(
            aoi=aoi,
            start=start,
            end=end,
            cfg=feature_cfg,
            cropland_mask=cropland_mask,
        )

        risk_img = risk_weekly(
            aoi=aoi,
            start=start,
            end=end,
            cfg=labels_cfg,
            cropland_mask=cropland_mask,
            week_index=i,
            total_weeks=total_weeks,
        )

        combined_img = features_img.addBands(risk_img)
        # Earth Engine export requires consistent band data types.
        combined_img = combined_img.toFloat()

        task = ee.batch.Export.image.toDrive(
            image=combined_img,
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
