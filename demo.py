#!/usr/bin/env python3
"""
ActInSpace Orbital Strategists Demo
Demonstration of orbital mechanics calculations and visualizations for the ActInSpace Hackathon.
"""

import sys
from orbital_calculator import OrbitalCalculator
from satellite_visualizer import SatelliteVisualizer


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def demo_orbital_calculations():
    """Demonstrate orbital calculations for different satellite types."""
    print("🛰️  ORBITAL MECHANICS DEMONSTRATION 🛰️")
    print_separator()
    
    # Define common satellite orbits
    satellites = [
        ("ISS (International Space Station)", 408),
        ("Starlink Satellite", 550),
        ("GPS Satellite", 20200),
        ("Geostationary Satellite", 35786),
    ]
    
    for name, altitude in satellites:
        print(f"📡 {name}")
        print("-" * 80)
        calc = OrbitalCalculator(altitude)
        print(calc)
        
        # Additional interesting facts
        velocity = calc.calculate_orbital_velocity()
        period = calc.calculate_orbital_period()
        
        print(f"  Fun Facts:")
        print(f"    - Travels {velocity * 3600:.0f} km every hour")
        print(f"    - Completes {1440 / period:.1f} orbits per day")
        
        if calc.is_geostationary_orbit():
            print(f"    - ⭐ This is a GEOSTATIONARY orbit!")
            print(f"    - Satellite appears stationary relative to Earth")
        
        print_separator()


def demo_orbit_comparison():
    """Demonstrate comparison of different orbits."""
    print("🌍 ORBIT COMPARISON 🌍")
    print_separator()
    
    # Compare LEO, MEO, and GEO orbits
    altitudes = [400, 1500, 20200, 35786]
    orbit_names = ["LEO (Low)", "LEO (High)", "MEO (GPS)", "GEO (Geostationary)"]
    
    print("Comparing different orbital altitudes:\n")
    
    for name, altitude in zip(orbit_names, altitudes):
        calc = OrbitalCalculator(altitude)
        info = calc.get_orbital_info()
        
        print(f"{name}:")
        print(f"  Altitude: {altitude} km")
        print(f"  Velocity: {info['velocity_km_s']:.2f} km/s")
        print(f"  Period: {info['period_minutes']:.1f} minutes ({info['period_minutes']/60:.2f} hours)")
        print()
    
    print_separator()


def demo_visualizations():
    """Demonstrate orbit visualizations."""
    print("📊 GENERATING VISUALIZATIONS 📊")
    print_separator()
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        # Create visualizations for ISS
        print("Creating visualization for ISS orbit...")
        iss_calc = OrbitalCalculator(408)
        iss_viz = SatelliteVisualizer(iss_calc)
        
        # 2D Plot
        fig_2d = iss_viz.plot_2d_orbit()
        fig_2d.savefig('/home/runner/work/ActInSpace-Orbital-Strategists/ActInSpace-Orbital-Strategists/iss_orbit_2d.png', 
                       dpi=150, bbox_inches='tight')
        print("  ✓ Saved: iss_orbit_2d.png")
        plt.close(fig_2d)
        
        # 3D Plot with inclination (ISS has 51.6° inclination)
        fig_3d = iss_viz.plot_3d_orbit(inclination_deg=51.6)
        fig_3d.savefig('/home/runner/work/ActInSpace-Orbital-Strategists/ActInSpace-Orbital-Strategists/iss_orbit_3d.png',
                       dpi=150, bbox_inches='tight')
        print("  ✓ Saved: iss_orbit_3d.png")
        plt.close(fig_3d)
        
        # Orbit comparison
        print("\nCreating comparison of multiple orbits...")
        viz = SatelliteVisualizer(OrbitalCalculator(400))
        altitudes = [400, 1500, 20200, 35786]
        labels = ["ISS (LEO)", "LEO High", "GPS (MEO)", "GEO"]
        fig_compare = viz.compare_orbits(altitudes, labels)
        fig_compare.savefig('/home/runner/work/ActInSpace-Orbital-Strategists/ActInSpace-Orbital-Strategists/orbit_comparison.png',
                           dpi=150, bbox_inches='tight')
        print("  ✓ Saved: orbit_comparison.png")
        plt.close(fig_compare)
        
        print("\n✨ All visualizations generated successfully!")
        
    except ImportError as e:
        print(f"⚠️  Visualization skipped: {e}")
        print("   Install matplotlib to generate visualizations: pip install matplotlib")
    except Exception as e:
        print(f"⚠️  Error generating visualizations: {e}")
    
    print_separator()


def demo_custom_calculation():
    """Allow user to calculate orbit for custom altitude."""
    print("🔧 CUSTOM ORBIT CALCULATOR 🔧")
    print_separator()
    
    print("Calculate orbital parameters for any altitude!")
    print("\nExample altitudes to try:")
    print("  - 200 km  : Minimum stable orbit")
    print("  - 400 km  : International Space Station")
    print("  - 550 km  : Starlink satellites")
    print("  - 35786 km: Geostationary orbit")
    
    try:
        altitude_input = input("\nEnter satellite altitude in km (or press Enter to skip): ").strip()
        
        if altitude_input:
            altitude = float(altitude_input)
            
            if altitude < 100:
                print("\n⚠️  Warning: Altitude below 100 km is below the Kármán line!")
            elif altitude < 160:
                print("\n⚠️  Warning: Orbit would decay rapidly due to atmospheric drag!")
            
            print()
            calc = OrbitalCalculator(altitude)
            print(calc)
            
            # Calculate some interesting derived values
            velocity = calc.calculate_orbital_velocity()
            period = calc.calculate_orbital_period()
            
            print("Additional Information:")
            print(f"  - Ground track velocity at equator: {velocity:.2f} km/s")
            print(f"  - Orbits per day: {1440 / period:.2f}")
            print(f"  - Days to complete 100 orbits: {period * 100 / 1440:.2f}")
            
    except ValueError:
        print("\n⚠️  Invalid input. Skipping custom calculation.")
    except KeyboardInterrupt:
        print("\n\nSkipping custom calculation.")
    except EOFError:
        print("\nSkipping custom calculation.")
    
    print_separator()


def main():
    """Main demo function."""
    print("\n" + "🚀" * 40)
    print("   ACTINSPACE HACKATHON - ORBITAL STRATEGISTS DEMO")
    print("   Quest CNES #2 - Satellite Orbital Mechanics")
    print("🚀" * 40)
    print_separator()
    
    # Run demonstrations
    demo_orbital_calculations()
    demo_orbit_comparison()
    demo_visualizations()
    
    # Interactive custom calculation (skip in non-interactive mode)
    if sys.stdin.isatty():
        demo_custom_calculation()
    
    print("✨ DEMO COMPLETE ✨")
    print("\nThank you for exploring orbital mechanics with us!")
    print("For more information, visit: https://github.com/ben001109/ActInSpace-Orbital-Strategists")
    print()


if __name__ == "__main__":
    main()
