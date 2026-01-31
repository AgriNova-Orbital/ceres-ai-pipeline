"""
Satellite Orbit Visualizer
Visualizes satellite orbits around Earth using matplotlib.
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from orbital_calculator import OrbitalCalculator


class SatelliteVisualizer:
    """Visualize satellite orbits in 2D and 3D."""
    
    def __init__(self, orbital_calculator):
        """
        Initialize the visualizer.
        
        Args:
            orbital_calculator: OrbitalCalculator instance
        """
        self.calculator = orbital_calculator
        
    def plot_2d_orbit(self, num_points=360):
        """
        Create a 2D plot of the satellite orbit.
        
        Args:
            num_points: Number of points to plot along the orbit
        """
        # Generate circular orbit points
        angles = np.linspace(0, 2 * np.pi, num_points)
        x = self.calculator.orbital_radius_km * np.cos(angles)
        y = self.calculator.orbital_radius_km * np.sin(angles)
        
        # Create plot
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Plot Earth
        earth_circle = plt.Circle((0, 0), self.calculator.EARTH_RADIUS_KM, 
                                  color='blue', alpha=0.3, label='Earth')
        ax.add_patch(earth_circle)
        
        # Plot orbit
        ax.plot(x, y, 'r-', linewidth=2, label='Satellite Orbit')
        
        # Plot satellite position at angle 0
        ax.plot(x[0], y[0], 'ro', markersize=10, label='Satellite')
        
        # Set equal aspect ratio and labels
        ax.set_aspect('equal')
        ax.set_xlabel('X (km)', fontsize=12)
        ax.set_ylabel('Y (km)', fontsize=12)
        ax.set_title(f'Satellite Orbit - {self.calculator.get_orbit_type()}\n'
                    f'Altitude: {self.calculator.altitude_km:.0f} km', 
                    fontsize=14, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Set limits
        limit = self.calculator.orbital_radius_km * 1.2
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        
        return fig
    
    def plot_3d_orbit(self, inclination_deg=0, num_points=360):
        """
        Create a 3D plot of the satellite orbit.
        
        Args:
            inclination_deg: Orbital inclination in degrees
            num_points: Number of points to plot along the orbit
        """
        # Generate orbit points
        angles = np.linspace(0, 2 * np.pi, num_points)
        inclination_rad = np.radians(inclination_deg)
        
        # Circular orbit in 3D with inclination
        x = self.calculator.orbital_radius_km * np.cos(angles)
        y = self.calculator.orbital_radius_km * np.sin(angles) * np.cos(inclination_rad)
        z = self.calculator.orbital_radius_km * np.sin(angles) * np.sin(inclination_rad)
        
        # Create 3D plot
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot Earth as a sphere
        u = np.linspace(0, 2 * np.pi, 50)
        v = np.linspace(0, np.pi, 50)
        x_earth = self.calculator.EARTH_RADIUS_KM * np.outer(np.cos(u), np.sin(v))
        y_earth = self.calculator.EARTH_RADIUS_KM * np.outer(np.sin(u), np.sin(v))
        z_earth = self.calculator.EARTH_RADIUS_KM * np.outer(np.ones(np.size(u)), np.cos(v))
        ax.plot_surface(x_earth, y_earth, z_earth, color='blue', alpha=0.3)
        
        # Plot orbit
        ax.plot(x, y, z, 'r-', linewidth=2, label='Satellite Orbit')
        
        # Plot satellite position
        ax.scatter([x[0]], [y[0]], [z[0]], color='red', s=100, label='Satellite')
        
        # Set labels and title
        ax.set_xlabel('X (km)', fontsize=10)
        ax.set_ylabel('Y (km)', fontsize=10)
        ax.set_zlabel('Z (km)', fontsize=10)
        ax.set_title(f'3D Satellite Orbit - {self.calculator.get_orbit_type()}\n'
                    f'Altitude: {self.calculator.altitude_km:.0f} km, '
                    f'Inclination: {inclination_deg}°',
                    fontsize=12, fontweight='bold')
        ax.legend()
        
        # Set equal aspect ratio
        limit = self.calculator.orbital_radius_km * 1.1
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        ax.set_zlim(-limit, limit)
        
        return fig
    
    def compare_orbits(self, altitudes_km, labels=None):
        """
        Compare multiple satellite orbits in a single plot.
        
        Args:
            altitudes_km: List of altitudes to compare
            labels: Optional list of labels for each orbit
        """
        if labels is None:
            labels = [f'{alt} km' for alt in altitudes_km]
        
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Plot Earth
        earth_circle = plt.Circle((0, 0), OrbitalCalculator.EARTH_RADIUS_KM, 
                                  color='blue', alpha=0.3, label='Earth')
        ax.add_patch(earth_circle)
        
        # Colors for different orbits
        colors = ['red', 'green', 'orange', 'purple', 'brown']
        
        # Plot each orbit
        max_radius = 0
        for i, (altitude, label) in enumerate(zip(altitudes_km, labels)):
            calc = OrbitalCalculator(altitude)
            radius = calc.orbital_radius_km
            max_radius = max(max_radius, radius)
            
            angles = np.linspace(0, 2 * np.pi, 360)
            x = radius * np.cos(angles)
            y = radius * np.sin(angles)
            
            color = colors[i % len(colors)]
            ax.plot(x, y, color=color, linewidth=2, label=label)
            
            # Plot satellite position
            ax.plot(x[0], y[0], 'o', color=color, markersize=8)
        
        # Set equal aspect ratio and labels
        ax.set_aspect('equal')
        ax.set_xlabel('X (km)', fontsize=12)
        ax.set_ylabel('Y (km)', fontsize=12)
        ax.set_title('Comparison of Satellite Orbits', fontsize=14, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Set limits
        limit = max_radius * 1.2
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        
        return fig
