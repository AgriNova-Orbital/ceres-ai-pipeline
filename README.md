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
