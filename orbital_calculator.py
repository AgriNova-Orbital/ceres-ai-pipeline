"""
Orbital Calculator Module
Calculates orbital parameters for satellites based on altitude and orbital mechanics principles.
"""

import math


class OrbitalCalculator:
    """Calculate orbital parameters for Earth satellites."""
    
    # Constants
    EARTH_RADIUS_KM = 6371.0  # Earth's mean radius in km
    EARTH_MU = 398600.4418  # Earth's gravitational parameter in km^3/s^2
    
    def __init__(self, altitude_km):
        """
        Initialize the orbital calculator.
        
        Args:
            altitude_km: Satellite altitude above Earth's surface in kilometers
        """
        self.altitude_km = altitude_km
        self.orbital_radius_km = self.EARTH_RADIUS_KM + altitude_km
        
    def calculate_orbital_velocity(self):
        """
        Calculate the orbital velocity of the satellite.
        
        Returns:
            Orbital velocity in km/s
        """
        velocity = math.sqrt(self.EARTH_MU / self.orbital_radius_km)
        return velocity
    
    def calculate_orbital_period(self):
        """
        Calculate the orbital period of the satellite.
        
        Returns:
            Orbital period in minutes
        """
        period_seconds = 2 * math.pi * math.sqrt(
            self.orbital_radius_km**3 / self.EARTH_MU
        )
        period_minutes = period_seconds / 60
        return period_minutes
    
    def calculate_angular_velocity(self):
        """
        Calculate the angular velocity of the satellite.
        
        Returns:
            Angular velocity in radians per second
        """
        period_seconds = self.calculate_orbital_period() * 60
        angular_velocity = 2 * math.pi / period_seconds
        return angular_velocity
    
    def is_geostationary_orbit(self, tolerance_km=100):
        """
        Check if the orbit is approximately geostationary.
        
        Args:
            tolerance_km: Tolerance for considering orbit geostationary (default 100 km)
            
        Returns:
            True if orbit is approximately geostationary, False otherwise
        """
        # Geostationary orbit altitude is approximately 35,786 km
        geo_altitude = 35786.0
        return abs(self.altitude_km - geo_altitude) < tolerance_km
    
    def get_orbit_type(self):
        """
        Determine the type of orbit based on altitude.
        
        Returns:
            String describing the orbit type
        """
        if self.altitude_km < 200:
            return "Suborbital/Very Low Earth Orbit (VLEO)"
        elif self.altitude_km < 2000:
            return "Low Earth Orbit (LEO)"
        elif self.altitude_km < 35586:
            return "Medium Earth Orbit (MEO)"
        elif self.is_geostationary_orbit():
            return "Geostationary Orbit (GEO)"
        else:
            return "High Earth Orbit (HEO)"
    
    def get_orbital_info(self):
        """
        Get comprehensive orbital information.
        
        Returns:
            Dictionary containing all orbital parameters
        """
        return {
            'altitude_km': self.altitude_km,
            'orbital_radius_km': self.orbital_radius_km,
            'velocity_km_s': self.calculate_orbital_velocity(),
            'period_minutes': self.calculate_orbital_period(),
            'angular_velocity_rad_s': self.calculate_angular_velocity(),
            'orbit_type': self.get_orbit_type(),
            'is_geostationary': self.is_geostationary_orbit()
        }
    
    def __str__(self):
        """String representation of orbital parameters."""
        info = self.get_orbital_info()
        return (
            f"Orbital Parameters:\n"
            f"  Altitude: {info['altitude_km']:.2f} km\n"
            f"  Orbital Radius: {info['orbital_radius_km']:.2f} km\n"
            f"  Orbital Velocity: {info['velocity_km_s']:.3f} km/s\n"
            f"  Orbital Period: {info['period_minutes']:.2f} minutes "
            f"({info['period_minutes']/60:.2f} hours)\n"
            f"  Orbit Type: {info['orbit_type']}\n"
        )
