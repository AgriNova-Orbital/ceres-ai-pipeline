"""
Utility functions for data visualization and processing.
"""

from typing import Dict, Any


def print_section_header(title: str, width: int = 60):
    """
    Print a formatted section header.
    
    Args:
        title: Section title
        width: Width of the header line
    """
    print()
    print("=" * width)
    print(title)
    print("=" * width)


def print_image_info(info: Dict[str, Any]):
    """
    Print formatted image information.
    
    Args:
        info: Image information dictionary
    """
    print_section_header("Image Information")
    print(f"Type: {info.get('type', 'Unknown')}")
    print(f"Bands: {', '.join(info.get('bands', []))}")
    
    properties = info.get('properties', {})
    if properties:
        print("\nProperties:")
        for key, value in properties.items():
            print(f"  {key}: {value}")


def format_bbox(bbox: list) -> str:
    """
    Format bounding box coordinates for display.
    
    Args:
        bbox: List of [lon_min, lat_min, lon_max, lat_max]
        
    Returns:
        Formatted string representation
    """
    if len(bbox) != 4:
        return "Invalid bounding box"
    
    return (f"Longitude: [{bbox[0]:.4f}, {bbox[2]:.4f}], "
            f"Latitude: [{bbox[1]:.4f}, {bbox[3]:.4f}]")


def create_summary_report(
    collection_size: int,
    date_range: tuple,
    aoi: list,
    cloud_cover: int
) -> str:
    """
    Create a summary report of the data fetch operation.
    
    Args:
        collection_size: Number of images in collection
        date_range: Tuple of (start_date, end_date)
        aoi: Bounding box list
        cloud_cover: Maximum cloud cover percentage
        
    Returns:
        Formatted summary report string
    """
    report = []
    report.append("\n" + "=" * 60)
    report.append("DATA COLLECTION SUMMARY")
    report.append("=" * 60)
    report.append(f"Images found: {collection_size}")
    report.append(f"Date range: {date_range[0]} to {date_range[1]}")
    report.append(f"AOI: {format_bbox(aoi)}")
    report.append(f"Max cloud cover: {cloud_cover}%")
    report.append("=" * 60)
    
    return "\n".join(report)
