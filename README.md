# ActInSpace Orbital Strategists 🛰️

**Demo Project for ActInSpace Hackathon - Quest CNES #2**

A Python-based demonstration of satellite orbital mechanics, featuring calculations and visualizations of various Earth orbits. This project showcases orbital dynamics concepts relevant to space mission planning and satellite deployment strategies.

## 🌟 Features

- **Orbital Mechanics Calculator**: Compute key orbital parameters including velocity, period, and angular velocity
- **Orbit Type Classification**: Automatically identify orbit types (LEO, MEO, GEO, etc.)
- **2D & 3D Visualizations**: Generate beautiful visualizations of satellite orbits around Earth
- **Comparative Analysis**: Compare multiple orbits side-by-side
- **Interactive Demo**: Explore calculations for real satellites (ISS, Starlink, GPS, etc.)

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ben001109/ActInSpace-Orbital-Strategists.git
cd ActInSpace-Orbital-Strategists
```

### Wheat Risk Pipeline (uv)

For detailed documentation on the pipeline scripts (dataset creation, training, etc.), see [docs/WHEAT_RISK_PIPELINE.md](docs/WHEAT_RISK_PIPELINE.md).

```bash
uv sync --dev

# Weekly risk rasters (dry-run by default; add --run to start exports)
uv run scripts/export_weekly_risk_rasters.py --stage 1 --limit 4

# Wheat patch export planning (dry-run)
uv run scripts/export_wheat_patches.py --stage 1 --dry-run

# To actually export (starts Drive export tasks), add --run and required args
# uv run scripts/export_weekly_risk_rasters.py --stage 1 --limit 4 --run --drive-folder EarthEngine
# uv run scripts/export_wheat_patches.py --stage 1 --samples 50 --run --drive-folder EarthEngine

# Model training CLI
uv run scripts/train_wheat_risk_lstm.py --help
```

### Expanding Source Time Range (Operational Checklist)

If you later expand the source data date range (for example from 2025-only to multi-year), use this sequence:

1. Export weekly risk rasters for the new window (dry-run first, then run).
2. Ingest/download the new GeoTIFFs to raw storage.
3. Run date inventory to verify 7-day completeness and check missing dates.
4. Rebuild staged datasets (L1/L2/L4) from the expanded raw set.
5. Re-run staged matrix training and evaluation.
6. Promote the new best checkpoint and threshold.

Example commands:

```bash
# 1) Export planning and execution for expanded dates
uv run scripts/export_weekly_risk_rasters.py \
  --stage 1 \
  --start-date 2024-01-01 \
  --end-date 2026-12-31 \
  --limit 8 \
  --dry-run

# run for real (requires Drive folder)
uv run scripts/export_weekly_risk_rasters.py \
  --stage 1 \
  --start-date 2024-01-01 \
  --end-date 2026-12-31 \
  --drive-folder EarthEngine \
  --run

# 2) Inventory completeness on raw tiffs
uv run scripts/inventory_wheat_dates.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir reports \
  --start-date 2025-01-01 \
  --cadence-days 7

# 3) Rebuild staged datasets
uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L1 \
  --patch-size 64 --step-size 64 --expected-weeks 46 --max-patches 12000

uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L2 \
  --patch-size 32 --step-size 32 --expected-weeks 46 --max-patches 12000

uv run scripts/build_npz_dataset_from_geotiffs.py \
  --input-dir data/raw/france_2025_weekly \
  --output-dir data/wheat_risk/staged/L4 \
  --patch-size 16 --step-size 16 --expected-weeks 46 --max-patches 12000

# 4) Re-train matrix and re-evaluate
uv run scripts/run_staged_training_matrix.py \
  --run --execute-train \
  --levels 1,2,4 --steps 100,500,2000 --base-patch 64 \
  --index-csv-template ./data/wheat_risk/staged/L{level}/index.csv \
  --root-dir-template ./data/wheat_risk/staged/L{level} --device cuda

uv run scripts/eval_staged_training_matrix.py \
  --summary-csv runs/staged_final/summary.csv \
  --index-csv-template ./data/wheat_risk/staged/L{level}/index.csv \
  --root-dir-template ./data/wheat_risk/staged/L{level}
```

WebUI planning reference (including data acquisition interface):
`docs/plans/2026-02-13-wheat-risk-webui-planning.md`

### Wheat Risk WebUI Prototype

Launch the MVP WebUI prototype:

```bash
uv run apps/wheat_risk_webui.py
```

Then open:

```text
http://127.0.0.1:5055
```

Prototype includes:

- Data Downloader actions (preview export / run export / refresh inventory)
- Data and patch image preview endpoints (`/api/preview/raw`, `/api/preview/patch`)
- Dataset build controls (single level / all levels)
- Training matrix dry-run and execute actions
- Evaluation trigger and run history panel

### Ray Cluster (Tailscale or LAN)

Ray/Torch usually need Python 3.11 or 3.12. If you're on Python 3.14 and installs fail:

```bash
uv python install 3.12
uv venv -p 3.12 --clear
uv sync --dev --extra distributed  # head
uv sync --dev --extra distributed --extra ml  # GPU workers
```

Start Ray (prints commands by default; add `--exec` to run):

```bash
uv run scripts/ray_cluster.py head
uv run scripts/ray_cluster.py worker --address <HEAD_IP>:6379 --num-gpus 1
```

### Running the Demo

Run the main demonstration:
```bash
python demo.py
```

This will:
- Calculate orbital parameters for ISS, Starlink, GPS, and geostationary satellites
- Compare different orbit types
- Generate visualization images (saved as PNG files)
- Offer interactive custom orbit calculations

## 📊 Example Output

The demo calculates and displays:

```
📡 ISS (International Space Station)
--------------------------------------------------------------------------------
Orbital Parameters:
  Altitude: 408.00 km
  Orbital Radius: 6779.00 km
  Orbital Velocity: 7.667 km/s
  Orbital Period: 92.68 minutes (1.54 hours)
  Orbit Type: Low Earth Orbit (LEO)

  Fun Facts:
    - Travels 27601 km every hour
    - Completes 15.5 orbits per day
```

## 🎯 Use Cases

This project demonstrates practical applications for:

- **Mission Planning**: Calculate optimal orbital parameters for satellite deployment
- **Space Situational Awareness**: Understand different orbital regimes
- **Educational Tool**: Learn orbital mechanics through interactive examples
- **Orbit Comparison**: Evaluate trade-offs between different orbital altitudes

## 📚 Module Documentation

### OrbitalCalculator

The core calculation engine for orbital mechanics:

```python
from orbital_calculator import OrbitalCalculator

# Create calculator for 400 km altitude
calc = OrbitalCalculator(altitude_km=400)

# Get orbital parameters
velocity = calc.calculate_orbital_velocity()  # km/s
period = calc.calculate_orbital_period()      # minutes
orbit_type = calc.get_orbit_type()            # orbit classification

# Get all info at once
info = calc.get_orbital_info()
print(calc)  # Pretty-printed summary
```

### SatelliteVisualizer

Generate orbit visualizations:

```python
from satellite_visualizer import SatelliteVisualizer

# Create visualizer
viz = SatelliteVisualizer(calc)

# Generate 2D plot
fig_2d = viz.plot_2d_orbit()
fig_2d.savefig('orbit_2d.png')

# Generate 3D plot with 51.6° inclination (like ISS)
fig_3d = viz.plot_3d_orbit(inclination_deg=51.6)
fig_3d.savefig('orbit_3d.png')

# Compare multiple orbits
altitudes = [400, 20200, 35786]
labels = ["LEO", "MEO", "GEO"]
fig_compare = viz.compare_orbits(altitudes, labels)
fig_compare.savefig('comparison.png')
```

## 🔬 Orbital Types Classified

| Type | Altitude Range | Examples |
|------|---------------|----------|
| Very Low Earth Orbit (VLEO) | < 200 km | Experimental satellites |
| Low Earth Orbit (LEO) | 200 - 2,000 km | ISS, Starlink, Hubble |
| Medium Earth Orbit (MEO) | 2,000 - 35,586 km | GPS, Galileo, GLONASS |
| Geostationary Orbit (GEO) | ~35,786 km | Communication satellites |
| High Earth Orbit (HEO) | > 35,986 km | Some scientific satellites |

## 🛠️ Technical Details

### Constants Used

- **Earth Radius**: 6,371 km (mean radius)
- **Earth's Gravitational Parameter (μ)**: 398,600.4418 km³/s²

### Formulas Implemented

- **Orbital Velocity**: v = √(μ/r)
- **Orbital Period**: T = 2π√(r³/μ)
- **Angular Velocity**: ω = 2π/T

Where:
- μ = Earth's gravitational parameter
- r = orbital radius (Earth radius + altitude)

## 🎓 Educational Resources

This demo is designed for the ActInSpace Hackathon and showcases:

1. **Kepler's Laws**: Understanding circular orbit mechanics
2. **Orbital Velocity**: How speed varies with altitude
3. **Orbital Period**: Relationship between altitude and orbit time
4. **Practical Applications**: Real-world satellite examples

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team: Orbital Strategists

Created for **ActInSpace Hackathon - Quest CNES #2**

- Demonstrating orbital mechanics concepts
- Providing tools for space mission analysis
- Supporting education in space technology

## 🤝 Contributing

This is a hackathon demonstration project. Suggestions and improvements are welcome!

## 📞 Contact

For questions about this demo project, please open an issue on GitHub.

---

**🚀 Happy Orbiting! 🌍**
