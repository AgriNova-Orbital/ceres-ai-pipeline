# ActInSpace-Orbital-Strategists

A Python application for leveraging Google Earth Engine API to fetch and process geospatial satellite data, specifically designed for orbital data analysis using Sentinel-2 imagery.

## Features

- **Google Earth Engine Integration**: Seamless interaction with Earth Engine API for satellite data access
- **Sentinel-2 Data Processing**: Fetch, filter, and process Sentinel-2 imagery
- **Area of Interest (AOI) Filtering**: Support for custom bounding box definitions
- **Cloud Cover Filtering**: Configurable cloud cover thresholds
- **NDVI Calculation**: Automated Normalized Difference Vegetation Index computation
- **Image Compositing**: Create median composites from image collections
- **Export Functionality**: Export processed imagery to Google Drive
- **Environment Management**: Easy setup with environment variable configuration
- **Docker Support**: Containerized deployment option

## Project Structure

```
ActInSpace-Orbital-Strategists/
├── config/                 # Configuration settings
│   ├── __init__.py
│   └── settings.py        # Centralized configuration using environment variables
├── modules/               # Core API implementations
│   ├── __init__.py
│   └── gee_api.py        # Google Earth Engine API functions
├── utils/                 # Utility functions
│   ├── __init__.py
│   └── visualization.py  # Data visualization and formatting utilities
├── main.py               # Application entry point
├── setup_env.py          # Environment setup script
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── .env.example         # Environment variable template
└── README.md            # This file
```

## Prerequisites

- Python 3.8 or higher
- Google Earth Engine account ([Sign up here](https://earthengine.google.com/))
- Google Cloud Project with Earth Engine API enabled

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ben001109/ActInSpace-Orbital-Strategists.git
cd ActInSpace-Orbital-Strategists
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Authenticate with Earth Engine

```bash
earthengine authenticate
```

Follow the prompts to authenticate with your Google account.

### 4. Configure Environment Variables

Run the setup script to create your `.env` file:

```bash
python setup_env.py
```

Or manually copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your favorite editor
```

## Configuration

The application uses environment variables for configuration. Key settings include:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `EE_PROJECT` | Google Earth Engine Project ID | Yes | - |
| `DEFAULT_AOI` | Default bounding box (lon_min,lat_min,lon_max,lat_max) | No | `-122.5,37.7,-122.0,37.9` |
| `DEFAULT_START_DATE` | Default start date (YYYY-MM-DD) | No | `2023-01-01` |
| `DEFAULT_END_DATE` | Default end date (YYYY-MM-DD) | No | `2023-12-31` |
| `MAX_CLOUD_COVER` | Maximum cloud cover percentage (0-100) | No | `20` |
| `GOOGLE_API_KEY` | Google API Key | No | - |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON | No | - |

## Usage

### Basic Usage

Run the main application to fetch and process Sentinel-2 data:

```bash
python main.py
```

This will:
1. Initialize Earth Engine with your credentials
2. Fetch Sentinel-2 images for the configured AOI and date range
3. Filter by cloud cover percentage
4. Create a median composite
5. Calculate NDVI
6. Display processing summary

### Programmatic Usage

You can also use the modules programmatically in your own scripts:

```python
from config.settings import settings
from modules import gee_api

# Initialize Earth Engine
gee_api.initialize_ee(settings.EE_PROJECT)

# Create AOI
aoi = gee_api.create_aoi([-122.5, 37.7, -122.0, 37.9])

# Fetch Sentinel-2 data
collection = gee_api.get_sentinel2_collection(
    aoi=aoi,
    start_date='2023-06-01',
    end_date='2023-06-30',
    max_cloud_cover=10
)

# Create median composite
composite = gee_api.get_median_composite(collection)

# Calculate NDVI
composite_ndvi = gee_api.calculate_ndvi(composite)

# Export to Google Drive
task = gee_api.export_to_drive(
    image=composite_ndvi,
    description='my_export',
    folder='EarthEngine',
    region=aoi,
    scale=30
)
```

### Export to Google Drive

To export processed imagery:

```python
from modules import gee_api

# Create your image (e.g., composite)
# ...

# Export
task = gee_api.export_to_drive(
    image=my_image,
    description='sentinel2_export',
    folder='EarthEngine',
    region=aoi,
    scale=30,  # meters per pixel
    crs='EPSG:4326'
)

# Monitor at: https://code.earthengine.google.com/tasks
```

## Docker Deployment

### Build Docker Image

```bash
docker build -t earth-engine-app .
```

### Run Docker Container

```bash
docker run --env-file .env earth-engine-app
```

Or with custom environment variables:

```bash
docker run -e EE_PROJECT=your-project-id -e MAX_CLOUD_COVER=15 earth-engine-app
```

### Docker Compose (Optional)

Create a `docker-compose.yml`:

```yaml
version: '3.8'
services:
  earth-engine:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

Run with:

```bash
docker-compose up
```

## API Reference

### modules.gee_api

#### `initialize_ee(project_id)`
Initialize Earth Engine with authentication.

#### `create_aoi(bbox)`
Create an Area of Interest from bounding box coordinates.

#### `get_sentinel2_collection(aoi, start_date, end_date, max_cloud_cover)`
Fetch Sentinel-2 image collection for given parameters.

#### `get_median_composite(collection)`
Create a median composite from an image collection.

#### `calculate_ndvi(image)`
Calculate Normalized Difference Vegetation Index.

#### `export_to_drive(image, description, folder, region, scale, crs)`
Export an image to Google Drive.

#### `get_image_info(image)`
Get information about an image.

#### `get_collection_date_range(collection)`
Get the date range of images in a collection.

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

1. Run `earthengine authenticate` again
2. Ensure your `EE_PROJECT` is set correctly
3. Verify your account has access to Earth Engine

### No Images Found

If no images are returned:

1. Check your date range is valid
2. Try increasing `MAX_CLOUD_COVER`
3. Verify your AOI coordinates are correct (lon, lat format)
4. Ensure the AOI is within Sentinel-2 coverage area

### Import Errors

If you get module import errors:

```bash
pip install --upgrade -r requirements.txt
```

## Development

### Adding New Datasets

To add support for other datasets (Landsat, MODIS, etc.), create new functions in `modules/gee_api.py`:

```python
def get_landsat8_collection(aoi, start_date, end_date, max_cloud_cover=20):
    """Fetch Landsat 8 image collection."""
    collection = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                  .filterBounds(aoi)
                  .filterDate(start_date, end_date)
                  .filter(ee.Filter.lt('CLOUD_COVER', max_cloud_cover)))
    return collection
```

### Running Tests

(Tests to be implemented in future updates)

```bash
python -m pytest tests/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

See [LICENSE](LICENSE) file for details.

## Resources

- [Google Earth Engine Documentation](https://developers.google.com/earth-engine)
- [Sentinel-2 Data Information](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR)
- [geemap Documentation](https://geemap.org/)

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review Earth Engine API documentation

## Roadmap

- [ ] Add support for Landsat datasets
- [ ] Add support for MODIS datasets
- [ ] Implement interactive UI for parameter input
- [ ] Add automated testing suite
- [ ] Create visualization dashboard
- [ ] Add time-series analysis tools
- [ ] Implement machine learning integration

## Acknowledgments

- Google Earth Engine Team
- Sentinel-2 Mission (ESA)
- geemap library contributors