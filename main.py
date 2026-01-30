"""
Main Entry Point for Earth Engine Application

This script demonstrates the core functionality of the Earth Engine API integration.
"""

from config.settings import settings
from modules import gee_api
from utils import visualization


def main():
    """Main execution function."""
    
    # Print welcome banner
    visualization.print_section_header("Earth Engine API - Sentinel-2 Data Fetcher", 60)
    
    try:
        # Validate configuration
        settings.validate()
        print(f"✓ Using Earth Engine project: {settings.EE_PROJECT}")
        
        # Initialize Earth Engine
        gee_api.initialize_ee(settings.EE_PROJECT)
        
        # Get configuration parameters
        bbox = settings.get_aoi_bbox()
        start_date = settings.DEFAULT_START_DATE
        end_date = settings.DEFAULT_END_DATE
        max_cloud_cover = settings.MAX_CLOUD_COVER
        
        print(f"\nConfiguration:")
        print(f"  AOI: {visualization.format_bbox(bbox)}")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Max cloud cover: {max_cloud_cover}%")
        
        # Create Area of Interest
        aoi = gee_api.create_aoi(bbox)
        print(f"\n✓ AOI created")
        
        # Fetch Sentinel-2 data
        visualization.print_section_header("Fetching Sentinel-2 Data")
        collection = gee_api.get_sentinel2_collection(
            aoi=aoi,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=max_cloud_cover
        )
        
        # Get collection info
        collection_size = collection.size().getInfo()
        date_range = gee_api.get_collection_date_range(collection)
        
        # Print summary
        print(visualization.create_summary_report(
            collection_size=collection_size,
            date_range=date_range,
            aoi=bbox,
            cloud_cover=max_cloud_cover
        ))
        
        if collection_size == 0:
            print("\n⚠ No images found matching the criteria.")
            print("Try adjusting the date range or increasing max cloud cover.")
            return
        
        # Create median composite
        visualization.print_section_header("Creating Median Composite")
        composite = gee_api.get_median_composite(collection)
        print("✓ Median composite created")
        
        # Calculate NDVI
        composite_with_ndvi = gee_api.calculate_ndvi(composite)
        print("✓ NDVI calculated and added")
        
        # Get image information
        image_info = gee_api.get_image_info(composite_with_ndvi)
        visualization.print_image_info(image_info)
        
        # Export option
        visualization.print_section_header("Export Options")
        print("\nTo export the composite image to Google Drive:")
        print("  Use the export_to_drive() function from modules.gee_api")
        print()
        print("Example:")
        print("  task = gee_api.export_to_drive(")
        print("      image=composite_with_ndvi,")
        print("      description='sentinel2_composite',")
        print("      folder='EarthEngine',")
        print("      region=aoi,")
        print(f"      scale={settings.EXPORT_SCALE}")
        print("  )")
        print()
        print("Monitor exports at: https://code.earthengine.google.com/tasks")
        
        # Success message
        visualization.print_section_header("Processing Complete")
        print("✓ Successfully processed Sentinel-2 data")
        print("✓ Composite image created with NDVI band")
        print()
        
    except ValueError as e:
        print(f"\n✗ Configuration Error: {e}")
        print("Please run: python setup_env.py")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
