#!/usr/bin/env python3
"""
Environment Setup Script

This script initializes environment variables for the project using dotenv.
It creates a .env file if one doesn't exist and prompts for necessary credentials.
"""

import os
import re
from pathlib import Path
from datetime import datetime


def validate_aoi(aoi_str):
    """Validate AOI bounding box format."""
    if not aoi_str:
        return True, None
    try:
        parts = [float(x.strip()) for x in aoi_str.split(',')]
        if len(parts) != 4:
            return False, "AOI must have exactly 4 values: lon_min,lat_min,lon_max,lat_max"
        lon_min, lat_min, lon_max, lat_max = parts
        if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180):
            return False, "Longitude values must be between -180 and 180"
        if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
            return False, "Latitude values must be between -90 and 90"
        if lon_min >= lon_max:
            return False, "lon_min must be less than lon_max"
        if lat_min >= lat_max:
            return False, "lat_min must be less than lat_max"
        return True, None
    except ValueError:
        return False, "AOI values must be numeric"


def validate_date(date_str):
    """Validate date format."""
    if not date_str:
        return True, None
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True, None
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format"


def validate_cloud_cover(value_str):
    """Validate cloud cover percentage."""
    if not value_str:
        return True, None
    try:
        value = int(value_str)
        if not (0 <= value <= 100):
            return False, "Cloud cover must be between 0 and 100"
        return True, None
    except ValueError:
        return False, "Cloud cover must be a valid integer"


def setup_environment():
    """Initialize environment variables for Earth Engine API."""
    env_path = Path('.env')
    
    print("=" * 60)
    print("Earth Engine API - Environment Setup")
    print("=" * 60)
    print()
    
    if env_path.exists():
        print("✓ .env file already exists")
        response = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if response != 'y':
            print("Setup cancelled. Using existing .env file.")
            return
    
    print("\nPlease provide the following information:")
    print("(Press Enter to skip optional fields)")
    print()
    
    # Collect environment variables
    env_vars = {}
    
    # Google Earth Engine project
    ee_project = input("Google Earth Engine Project ID (required): ").strip()
    if ee_project:
        env_vars['EE_PROJECT'] = ee_project
    
    # Google API credentials (optional)
    google_api_key = input("Google API Key (optional): ").strip()
    if google_api_key:
        env_vars['GOOGLE_API_KEY'] = google_api_key
    
    # Service account credentials path (optional)
    service_account = input("Path to Service Account JSON (optional): ").strip()
    if service_account:
        # Validate path exists
        if not Path(service_account).exists():
            print(f"⚠ Warning: File not found at {service_account}")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                service_account = ""
        if service_account:
            env_vars['GOOGLE_APPLICATION_CREDENTIALS'] = service_account
    
    # AOI defaults
    while True:
        aoi_bbox = input("Default AOI bounding box [lon_min,lat_min,lon_max,lat_max] (optional): ").strip()
        if not aoi_bbox:
            break
        valid, error = validate_aoi(aoi_bbox)
        if valid:
            env_vars['DEFAULT_AOI'] = aoi_bbox
            break
        else:
            print(f"✗ Invalid AOI: {error}. Please try again.")
    
    # Date range defaults
    while True:
        start_date = input("Default start date (YYYY-MM-DD, optional): ").strip()
        if not start_date:
            break
        valid, error = validate_date(start_date)
        if valid:
            env_vars['DEFAULT_START_DATE'] = start_date
            break
        else:
            print(f"✗ Invalid date: {error}. Please try again.")
    
    while True:
        end_date = input("Default end date (YYYY-MM-DD, optional): ").strip()
        if not end_date:
            break
        valid, error = validate_date(end_date)
        if valid:
            env_vars['DEFAULT_END_DATE'] = end_date
            break
        else:
            print(f"✗ Invalid date: {error}. Please try again.")
    
    # Cloud cover threshold
    while True:
        cloud_cover = input("Max cloud cover percentage (0-100, default: 20): ").strip()
        if not cloud_cover:
            env_vars['MAX_CLOUD_COVER'] = '20'
            break
        valid, error = validate_cloud_cover(cloud_cover)
        if valid:
            env_vars['MAX_CLOUD_COVER'] = cloud_cover
            break
        else:
            print(f"✗ Invalid cloud cover: {error}. Please try again.")
    
    # Write to .env file
    with open(env_path, 'w') as f:
        f.write("# Earth Engine API Configuration\n")
        f.write("# Generated by setup_env.py\n\n")
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print()
    print("=" * 60)
    print("✓ Environment setup complete!")
    print(f"✓ Configuration saved to {env_path.absolute()}")
    print("=" * 60)
    print()
    print("⚠ SECURITY WARNING:")
    print("  The .env file contains sensitive credentials.")
    print("  Ensure it has appropriate file permissions.")
    if os.name != 'nt':  # Unix-like systems
        print("  Run: chmod 600 .env")
    print()
    print("Next steps:")
    print("1. Authenticate with Earth Engine: earthengine authenticate")
    print("2. Run the application: python main.py")
    print()


if __name__ == "__main__":
    try:
        setup_environment()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n✗ Error during setup: {e}")
        exit(1)
