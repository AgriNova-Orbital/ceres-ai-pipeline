#!/usr/bin/env python3
"""CLI tool to download a Google Drive folder with Pacman-style progress bar.

Usage:
    python scripts/download_drive_folder.py --folder <FOLDER_ID> --save ./data/raw/my_data
    python scripts/download_drive_folder.py --folder <FOLDER_ID> --save ./data/raw/my_data --merge
    python scripts/download_drive_folder.py --folder <FOLDER_ID> --save ./data/raw/my_data --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.drive_oauth import (
    download_file,
    get_drive_service,
    list_folder_files,
)
from modules.download_progress import (
    DownloadProgress,
    bytes_to_human,
    estimate_download_size,
)
from modules.merge_geotiffs import merge_split_geotiffs, has_gdal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download a Google Drive folder with progress bar"
    )
    parser.add_argument(
        "--folder",
        required=True,
        help="Google Drive folder ID (from URL)",
    )
    parser.add_argument(
        "--save",
        default="./downloads",
        help="Output directory (default: ./downloads)",
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="OAuth credentials JSON file",
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="OAuth token cache file",
    )
    parser.add_argument(
        "--pattern",
        default=".tif,.tiff",
        help="Comma-separated file extensions to download (default: .tif,.tiff)",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Auto-merge split GeoTIFFs after download (requires GDAL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading",
    )
    args = parser.parse_args()

    save_dir = Path(args.save)
    creds_path = Path(args.credentials)
    token_path = Path(args.token)

    extensions = tuple(
        ext.strip() if ext.strip().startswith(".") else f".{ext.strip()}"
        for ext in args.pattern.split(",")
    )

    print("Connecting to Google Drive...")
    svc = get_drive_service(
        credentials_json=creds_path,
        token_json=token_path,
    )

    print(f"Listing files in folder {args.folder}...")
    all_files = list_folder_files(svc, folder_id=args.folder)
    target_files = [f for f in all_files if f.name.lower().endswith(extensions)]

    if not target_files:
        print(f"No matching files found (extensions: {extensions})")
        return 1

    total_size = estimate_download_size([{"size": f.size or 0} for f in target_files])

    print(f"\n{'=' * 60}")
    print(f"  Folder:   {args.folder}")
    print(f"  Files:    {len(target_files)} / {len(all_files)} total")
    print(f"  Size:     {bytes_to_human(total_size)}")
    print(f"  Save to:  {save_dir.resolve()}")
    if args.merge:
        print(
            f"  Merge:    Yes (GDAL: {'available' if has_gdal() else 'NOT AVAILABLE'})"
        )
    print(f"{'=' * 60}\n")

    if args.dry_run:
        print("Dry run - files that would be downloaded:")
        for f in target_files:
            sz = bytes_to_human(f.size or 0)
            print(f"  {f.name} ({sz})")
        return 0

    save_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    with DownloadProgress(
        total_bytes=total_size,
        total_files=len(target_files),
    ) as prog:
        for f in target_files:
            dst = save_dir / f.name
            prog.on_file_start(f.name, f.size or 0)
            if dst.exists() and dst.stat().st_size == (f.size or 0):
                prog.on_chunk(f.size or 0)
                prog.on_file_done(f.name, f.size or 0)
                skipped += 1
                continue
            download_file(
                svc,
                file_id=f.id,
                dst_path=dst,
                progress_callback=prog.on_chunk,
            )
            prog.on_file_done(f.name, f.size or 0)
            downloaded += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped (already exist)")

    if args.merge:
        if not has_gdal():
            print("WARNING: GDAL not installed, skipping merge step")
            print("Install with: pip install gdal")
        else:
            print("\nMerging split GeoTIFFs...")
            merged = merge_split_geotiffs(save_dir)
            if merged:
                print(f"Merged {len(merged)} groups into {save_dir / '_merged'}")
            else:
                print("No split files found to merge")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
