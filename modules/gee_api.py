"""
Google Earth Engine API Module

This module provides functions for interacting with Google Earth Engine
to fetch and process satellite imagery data.
"""

import ee
from datetime import datetime
from typing import List, Optional, Tuple


def initialize_ee(project_id: Optional[str] = None):
    """
    Initialize Earth Engine with authentication.
    
    Args:
        project_id: Google Earth Engine project ID
        
    Raises:
        Exception: If initialization fails
    """
    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        print("✓ Earth Engine initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize Earth Engine: {e}")
        print("Please run: earthengine authenticate")
        raise


def create_aoi(bbox: List[float]) -> ee.Geometry.Rectangle:
    """
    Create an Area of Interest (AOI) from bounding box coordinates.
    
    Args:
        bbox: Bounding box [lon_min, lat_min, lon_max, lat_max]
        
    Returns:
        Earth Engine Rectangle geometry
    """
    return ee.Geometry.Rectangle(bbox)


def get_sentinel2_collection(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
    max_cloud_cover: int = 20
) -> ee.ImageCollection:
    """
    Fetch Sentinel-2 image collection for given parameters.
    
    Args:
        aoi: Area of Interest geometry
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        max_cloud_cover: Maximum cloud cover percentage (0-100)
        
    Returns:
        Filtered Sentinel-2 image collection
    """
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(aoi)
                  .filterDate(start_date, end_date)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud_cover)))
    
    count = collection.size().getInfo()
    print(f"✓ Found {count} Sentinel-2 images matching criteria")
    
    return collection


def get_median_composite(collection: ee.ImageCollection) -> ee.Image:
    """
    Create a median composite from an image collection.
    
    Args:
        collection: Image collection
        
    Returns:
        Median composite image
    """
    return collection.median()


def get_true_color_visualization(image: ee.Image) -> dict:
    """
    Get visualization parameters for true color (RGB) imagery.
    
    Args:
        image: Input image
        
    Returns:
        Dictionary of visualization parameters
    """
    return {
        'bands': ['B4', 'B3', 'B2'],
        'min': 0,
        'max': 3000,
        'gamma': 1.4
    }


def export_to_drive(
    image: ee.Image,
    description: str,
    folder: str = 'EarthEngine',
    region: Optional[ee.Geometry] = None,
    scale: int = 30,
    crs: str = 'EPSG:4326'
) -> ee.batch.Task:
    """
    Export an image to Google Drive.
    
    Args:
        image: Image to export
        description: Export task description (will be the filename)
        folder: Google Drive folder name
        region: Region to export (if None, uses image footprint)
        scale: Export resolution in meters per pixel
        crs: Coordinate reference system
        
    Returns:
        Export task object
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=1e13
    )
    
    task.start()
    print(f"✓ Export task '{description}' started")
    print(f"  Check status at: https://code.earthengine.google.com/tasks")
    
    return task


def get_image_info(image: ee.Image) -> dict:
    """
    Get information about an image.
    
    Args:
        image: Input image
        
    Returns:
        Dictionary containing image metadata
    """
    info = image.getInfo()
    return {
        'bands': [band['id'] for band in info.get('bands', [])],
        'properties': info.get('properties', {}),
        'type': info.get('type', 'Unknown')
    }


def calculate_ndvi(image: ee.Image) -> ee.Image:
    """
    Calculate Normalized Difference Vegetation Index (NDVI).
    
    For Sentinel-2: NDVI = (B8 - B4) / (B8 + B4)
    
    Args:
        image: Sentinel-2 image
        
    Returns:
        Image with NDVI band added
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)


def get_collection_date_range(collection: ee.ImageCollection) -> Tuple[str, str]:
    """
    Get the date range of images in a collection.
    
    Args:
        collection: Image collection
        
    Returns:
        Tuple of (earliest_date, latest_date) as ISO format strings
    """
    dates = collection.aggregate_array('system:time_start')
    date_list = dates.getInfo()
    
    if not date_list:
        return ("No images", "No images")
    
    earliest = datetime.fromtimestamp(min(date_list) / 1000).strftime('%Y-%m-%d')
    latest = datetime.fromtimestamp(max(date_list) / 1000).strftime('%Y-%m-%d')
    
    return (earliest, latest)
