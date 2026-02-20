"""
Configuration Settings

This module provides centralized configuration management using environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application configuration settings."""
    
    # Earth Engine Configuration
    EE_PROJECT = os.getenv('EE_PROJECT', '')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    
    # Default AOI (Area of Interest) - bounding box format: [lon_min, lat_min, lon_max, lat_max]
    DEFAULT_AOI = os.getenv('DEFAULT_AOI', '-122.5,37.7,-122.0,37.9')
    
    # Default date range - updated to 2024
    DEFAULT_START_DATE = os.getenv('DEFAULT_START_DATE', '2024-01-01')
    DEFAULT_END_DATE = os.getenv('DEFAULT_END_DATE', '2024-12-31')
    
    # Cloud cover threshold (0-100)
    MAX_CLOUD_COVER = int(os.getenv('MAX_CLOUD_COVER', '20'))
    
    # Export settings
    EXPORT_SCALE = int(os.getenv('EXPORT_SCALE', '30'))  # meters per pixel
    EXPORT_CRS = os.getenv('EXPORT_CRS', 'EPSG:4326')
    
    @classmethod
    def get_aoi_bbox(cls):
        """Parse AOI from environment variable into list of floats."""
        try:
            return [float(x.strip()) for x in cls.DEFAULT_AOI.split(',')]
        except (ValueError, AttributeError):
            # Return default San Francisco Bay Area
            return [-122.5, 37.7, -122.0, 37.9]
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        if not cls.EE_PROJECT:
            raise ValueError(
                "EE_PROJECT is not set. Please run setup_env.py or set it in your .env file."
            )
        
        # Validate service account credentials path if provided
        if cls.GOOGLE_APPLICATION_CREDENTIALS:
            creds_path = Path(cls.GOOGLE_APPLICATION_CREDENTIALS)
            if not creds_path.exists():
                raise ValueError(
                    f"GOOGLE_APPLICATION_CREDENTIALS file not found: {cls.GOOGLE_APPLICATION_CREDENTIALS}"
                )
        
        return True


# Create settings instance
settings = Settings()
