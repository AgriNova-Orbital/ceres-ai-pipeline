#!/usr/bin/env python3
"""
Simple test to validate the orbital calculator functionality
"""

from orbital_calculator import OrbitalCalculator
import math


def test_iss_orbit():
    """Test ISS orbital parameters."""
    print("Testing ISS orbit (408 km altitude)...")
    calc = OrbitalCalculator(408)
    
    velocity = calc.calculate_orbital_velocity()
    period = calc.calculate_orbital_period()
    orbit_type = calc.get_orbit_type()
    
    # Verify reasonable values
    assert 7.0 < velocity < 8.0, f"Velocity {velocity} km/s is out of expected range"
    assert 90 < period < 95, f"Period {period} minutes is out of expected range"
    assert orbit_type == "Low Earth Orbit (LEO)", f"Wrong orbit type: {orbit_type}"
    
    print(f"  ✓ Velocity: {velocity:.3f} km/s")
    print(f"  ✓ Period: {period:.2f} minutes")
    print(f"  ✓ Orbit type: {orbit_type}")
    print()


def test_geostationary_orbit():
    """Test geostationary orbit detection."""
    print("Testing geostationary orbit (35786 km altitude)...")
    calc = OrbitalCalculator(35786)
    
    period = calc.calculate_orbital_period()
    is_geo = calc.is_geostationary_orbit()
    
    # GEO period should be approximately 24 hours (1436 minutes)
    assert 1400 < period < 1450, f"Period {period} minutes is not close to 24 hours"
    assert is_geo, "Should be detected as geostationary"
    
    print(f"  ✓ Period: {period:.2f} minutes ({period/60:.2f} hours)")
    print(f"  ✓ Detected as geostationary: {is_geo}")
    print()


def test_orbital_formula():
    """Test that orbital velocity formula is correct."""
    print("Testing orbital velocity formula...")
    calc = OrbitalCalculator(0)  # At Earth's surface
    
    # v = sqrt(mu/r) where r = Earth radius
    expected_velocity = math.sqrt(calc.EARTH_MU / calc.EARTH_RADIUS_KM)
    actual_velocity = calc.calculate_orbital_velocity()
    
    assert abs(expected_velocity - actual_velocity) < 0.001, "Velocity formula mismatch"
    
    print(f"  ✓ Surface velocity: {actual_velocity:.3f} km/s")
    print()


def test_orbit_types():
    """Test orbit type classification."""
    print("Testing orbit type classification...")
    
    test_cases = [
        (150, "Suborbital/Very Low Earth Orbit (VLEO)"),
        (400, "Low Earth Orbit (LEO)"),
        (1500, "Low Earth Orbit (LEO)"),
        (20200, "Medium Earth Orbit (MEO)"),
        (35786, "Geostationary Orbit (GEO)"),
    ]
    
    for altitude, expected_type in test_cases:
        calc = OrbitalCalculator(altitude)
        orbit_type = calc.get_orbit_type()
        assert orbit_type == expected_type, f"Wrong type for {altitude} km: {orbit_type}"
        print(f"  ✓ {altitude:5d} km -> {orbit_type}")
    
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Running Orbital Calculator Tests")
    print("=" * 70 + "\n")
    
    try:
        test_iss_orbit()
        test_geostationary_orbit()
        test_orbital_formula()
        test_orbit_types()
        
        print("=" * 70)
        print("✨ All tests passed successfully! ✨")
        print("=" * 70 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        return 1


if __name__ == "__main__":
    exit(main())
