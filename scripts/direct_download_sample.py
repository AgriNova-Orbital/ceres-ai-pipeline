
import os
import ee
import requests
import numpy as np
import rasterio
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.wheat_risk.config import PipelineConfig, StagePreset
from modules.wheat_risk.features import build_weekly_features
from modules.wheat_risk.labels import risk_weekly
from modules.wheat_risk.masks import build_aoi, cropland_mask_worldcover
from modules.wheat_risk.timebins import week_bins

def download_url(url: str, out_path: Path):
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"Download failed: {r.status_code} {r.text}")
    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path

def main():
    load_dotenv()
    project = os.environ.get("EE_PROJECT")
    if not project:
        raise RuntimeError("EE_PROJECT not set in .env")
        
    print(f"Initializing EE with project: {project}")
    ee.Initialize(project=project)
    
    # Setup for a very small extraction (just to prove it works and get data)
    # We'll use Stage 1 (course scale) to make it fast
    stage = StagePreset.stage1()
    cfg = PipelineConfig.default_france_2025(stage)
    
    # IMPORTANT: Use a nice small AOI to avoid pixel limits on direct download
    # A 10x10km box is plenty for testing
    # Center of France wheat belt roughly
    small_aoi = ee.Geometry.Rectangle([2.0, 48.5, 2.2, 48.7]) 
    
    aoi = small_aoi
    cropland_mask = cropland_mask_worldcover(aoi)
    
    # Target growing season (May/June) where data is more likely/useful
    # Week 20 is approx mid-May
    bins = week_bins(cfg.start_date, cfg.end_date)[20:23]
    
    out_dir = Path("data/manual_download")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting direct download for {len(bins)} weeks (growing season)...")
    
    for i_offset, (start, end) in enumerate(bins):
        # i is the actual week index (0-based) from start of year
        i = 20 + i_offset
        print(f"Processing week {i+1}: {start}..{end}")
        
        # Build features
        features = build_weekly_features(
            aoi=aoi, start=start, end=end,
            # Relax cloud cover to ensure we get pixels for training test
            cfg={"max_cloud": 100},
            cropland_mask=cropland_mask
        )
        
        # Build risk labels
        risk = risk_weekly(
            aoi=aoi, start=start, end=end,
            cfg={"max_cloud": 100},
            cropland_mask=cropland_mask,
            week_index=i, 
            total_weeks=52
        )
        
        # Combine
        combined = features.addBands(risk).toFloat()
        
        # Download URL
        # format='GEO_TIFF'
        name = f"fr_wheat_feat_{start.split('-')[0]}W{i+1:02d}.tif"
        out_file = out_dir / name
        
        if out_file.exists():
            print(f"  Skipping {name} (exists)")
            continue
            
        print(f"  Requesting download URL for {name}...")
        try:
            url = combined.getDownloadURL({
                'name': name,
                'scale': stage.scale_m,
                'crs': 'EPSG:4326',
                'region': aoi,
                'format': 'GEO_TIFF'
            })
            print(f"  Downloading...")
            download_url(url, out_file)
            print(f"  Saved to {out_file}")
            
        except Exception as e:
            print(f"  ERROR: {e}")

    print("Done!")

if __name__ == "__main__":
    main()
